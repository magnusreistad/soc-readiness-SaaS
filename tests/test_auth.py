"""
JWT verification in api/dependencies.py.

Tokens are signed with a throwaway EC P-256 key generated per test session.
The JWKS client is a real PyJWKClient whose fetch_data() returns that key, so
kid lookup runs for real but nothing touches the network.
"""

import base64
import hashlib
import hmac
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from jwt.exceptions import PyJWKClientConnectionError

from api import dependencies
from api.main import app

KID = "test-key"
RSA_KID = "test-rsa-key"
ISSUER = f"{dependencies.SUPABASE_URL}/auth/v1"


@pytest.fixture(scope="session")
def private_key():
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture(scope="session")
def rsa_private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def jwks_client(private_key, rsa_private_key, monkeypatch):
    ec_jwk = jwt.algorithms.ECAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    ec_jwk.update({"kid": KID, "alg": "ES256", "use": "sig"})
    rsa_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(rsa_private_key.public_key(), as_dict=True)
    rsa_jwk.update({"kid": RSA_KID, "alg": "RS256", "use": "sig"})

    client = jwt.PyJWKClient(f"{ISSUER}/.well-known/jwks.json")
    monkeypatch.setattr(client, "fetch_data", lambda: {"keys": [ec_jwk, rsa_jwk]})
    monkeypatch.setattr(dependencies, "_jwks_client", client)
    return client


def _claims(**overrides):
    claims = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "email": "user@example.com",
        "org_id": 1,
        "role": "analyst",
        "aud": "authenticated",
        "iss": ISSUER,
        "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)
    return claims


def _sign(private_key, **overrides):
    return jwt.encode(_claims(**overrides), private_key, algorithm="ES256", headers={"kid": KID})


def _b64(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def _unsigned(alg: str) -> bytes:
    header = _b64(json.dumps({"alg": alg, "typ": "JWT", "kid": KID}).encode())
    return header + b"." + _b64(json.dumps(_claims()).encode())


def _assert_401(token: str):
    with pytest.raises(HTTPException) as exc:
        dependencies._verify_supabase_token(token)
    assert exc.value.status_code == 401


def test_valid_es256_token_passes(jwks_client, private_key):
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=_sign(private_key))
    user = dependencies.get_current_user(creds)
    assert user.org_id == 1
    assert user.role == "analyst"
    assert user.email == "user@example.com"


def test_valid_rs256_token_passes(jwks_client, rsa_private_key):
    token = jwt.encode(_claims(), rsa_private_key, algorithm="RS256", headers={"kid": RSA_KID})
    payload = dependencies._verify_supabase_token(token)
    assert payload["org_id"] == 1


def test_rs256_token_pointing_at_ec_key_is_rejected(jwks_client, rsa_private_key):
    # RS256 is allowed, but the kid selects the ES256 key: PyJWT binds the
    # token's alg to the key's alg, so this must not verify.
    _assert_401(jwt.encode(_claims(), rsa_private_key, algorithm="RS256", headers={"kid": KID}))


def test_forged_hs256_token_is_rejected(jwks_client, private_key):
    # Classic algorithm confusion: HMAC-sign with the public key as the secret.
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    signing_input = _unsigned("HS256")
    signature = _b64(hmac.new(public_pem, signing_input, hashlib.sha256).digest())
    _assert_401((signing_input + b"." + signature).decode())


def test_alg_none_token_is_rejected(jwks_client):
    _assert_401((_unsigned("none") + b".").decode())


def test_wrong_audience_is_rejected(jwks_client, private_key):
    _assert_401(_sign(private_key, aud="service_role"))


def test_wrong_issuer_is_rejected(jwks_client, private_key):
    _assert_401(_sign(private_key, iss="https://attacker.example/auth/v1"))


def test_expired_token_is_rejected(jwks_client, private_key):
    _assert_401(_sign(private_key, exp=int(time.time()) - 60))


def test_forged_token_returns_401_not_500_through_api(jwks_client):
    resp = TestClient(app).get(
        "/api/v1/controls",
        headers={"Authorization": f"Bearer {(_unsigned('none') + b'.').decode()}"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid or expired token."


def test_jwks_outage_is_not_reported_as_invalid_token(jwks_client, private_key, monkeypatch):
    def _unreachable():
        raise PyJWKClientConnectionError("JWKS endpoint unreachable")

    monkeypatch.setattr(jwks_client, "fetch_data", _unreachable)
    with pytest.raises(PyJWKClientConnectionError):
        dependencies._verify_supabase_token(_sign(private_key))
