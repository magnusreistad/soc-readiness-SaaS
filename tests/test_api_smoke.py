from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_check_is_public():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "version": "1.0.0"}


def test_protected_route_rejects_missing_token():
    resp = client.get("/api/v1/controls")
    assert resp.status_code == 401


def test_protected_route_rejects_malformed_token():
    # Rejected while parsing the header, before any JWKS fetch to Supabase.
    resp = client.get("/api/v1/controls", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid or expired token."
