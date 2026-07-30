"""
api/dependencies.py

Shared FastAPI dependencies injected via Depends().

Key exports:
    get_current_user  — verifies Supabase JWT, returns CurrentUser
    require_admin     — same + asserts role == 'admin'
    require_analyst   — same + asserts role in ('admin', 'analyst')

How Supabase JWT auth works here:
    1. Client logs in via Supabase Auth (supabase.auth.signInWithPassword)
    2. Supabase returns a JWT access token
    3. Client sends: Authorization: Bearer <token>
    4. get_current_user() verifies the JWT signature using Supabase's
       JWKS endpoint (cached on first call)
    5. A custom_access_token_hook (configured in the Supabase dashboard,
       not version-controlled — see README) has already embedded org_id
       + role into the JWT claims, so no extra DB lookup is needed per
       request. Both this API and Supabase Auth read from the same
       `profiles` table in Postgres.
"""

import logging
import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
import httpx
import jwt as pyjwt
from jwt.exceptions import InvalidTokenError

# ---------------------------------------------------------------------------
# Supabase JWT config
# ---------------------------------------------------------------------------

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

# ---------------------------------------------------------------------------
# Demo mode config
#
# When DEMO_MODE=true, all mutating requests (POST/PATCH/DELETE) against the
# org identified by DEMO_ORG_ID are blocked with a friendly 403. Read (GET)
# requests are unaffected. Both env vars are unset in a normal deployment, so
# this is a no-op unless explicitly configured — see scripts/seed_demo_data.py.
# ---------------------------------------------------------------------------

DEMO_MODE   = os.getenv("DEMO_MODE", "false").strip().lower() == "true"
DEMO_ORG_ID = int(os.getenv("DEMO_ORG_ID", "0") or 0)

DEMO_READONLY_MESSAGE = "This is a read-only demo. Sign up to try this with your own data."

logger  = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=True)


# ---------------------------------------------------------------------------
# CurrentUser — what get_current_user() returns to route handlers
# ---------------------------------------------------------------------------

class CurrentUser(BaseModel):
    user_id: str       # UUID from auth.users / profiles.id
    org_id: int        # from JWT custom claim
    email: str         # from JWT sub claim
    role: str          # from JWT custom claim: admin | analyst | auditor

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_auditor(self) -> bool:
        return self.role == "auditor"

    @property
    def can_write(self) -> bool:
        return self.role in ("admin", "analyst")


# ---------------------------------------------------------------------------
# JWT verification
# ---------------------------------------------------------------------------

_jwks_client = None

def _get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        _jwks_client = pyjwt.PyJWKClient(jwks_url)
    return _jwks_client


def _verify_supabase_token(token: str) -> dict:
    if not SUPABASE_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_URL is not configured on the server.",
        )
    try:
        # Read the algorithm from the token itself
        header = pyjwt.get_unverified_header(token)
        alg    = header.get("alg", "RS256")

        client      = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)

        payload = pyjwt.decode(
            token,
            signing_key.key,
            algorithms=[alg],
            options={"verify_aud": False},
        )
        return payload
    except InvalidTokenError as e:
        logger.warning("JWT verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Core dependency
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> CurrentUser:
    """
    Verifies the Bearer JWT and extracts user identity.

    Injects into route handlers via:
        current_user: Annotated[CurrentUser, Depends(get_current_user)]
    """
    payload = _verify_supabase_token(credentials.credentials)

    # Extract standard claims
    user_id = payload.get("sub")
    email   = payload.get("email", "")

    # Extract custom claims (injected by custom_access_token_hook)
    org_id = payload.get("org_id")
    role   = payload.get("role", "analyst")

    if not user_id or not org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing required claims (user_id or org_id). "
                   "Ensure the custom_access_token_hook is configured in Supabase.",
        )

    return CurrentUser(
        user_id=user_id,
        org_id=int(org_id),
        email=email,
        role=role,
    )


# ---------------------------------------------------------------------------
# Demo-mode gate — single place that blocks writes to the demo org
# ---------------------------------------------------------------------------

def block_demo_writes(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """
    Raises 403 if DEMO_MODE is on and this user belongs to the demo org.

    Composed into require_analyst / require_admin below, so every endpoint
    that already requires an analyst or admin role — i.e. every
    create/update/delete endpoint in the app — is covered automatically.
    Also usable directly (via WriteUser) for the rare mutating endpoint that
    only requires AuthUser, e.g. profile self-service actions.
    """
    if DEMO_MODE and DEMO_ORG_ID and current_user.org_id == DEMO_ORG_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=DEMO_READONLY_MESSAGE,
        )
    return current_user


# ---------------------------------------------------------------------------
# Role-gated dependencies — compose on top of get_current_user
# ---------------------------------------------------------------------------

def require_admin(
    current_user: Annotated[CurrentUser, Depends(block_demo_writes)],
) -> CurrentUser:
    """Allows only admin role. Use for user management, org settings."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required.",
        )
    return current_user


def require_analyst(
    current_user: Annotated[CurrentUser, Depends(block_demo_writes)],
) -> CurrentUser:
    """Allows admin and analyst roles. Blocks auditors from write endpoints."""
    if not current_user.can_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analyst or admin role required.",
        )
    return current_user


# ---------------------------------------------------------------------------
# Convenience type aliases for route signatures
# ---------------------------------------------------------------------------

AuthUser    = Annotated[CurrentUser, Depends(get_current_user)]
AdminUser   = Annotated[CurrentUser, Depends(require_admin)]
AnalystUser = Annotated[CurrentUser, Depends(require_analyst)]
WriteUser   = Annotated[CurrentUser, Depends(block_demo_writes)]