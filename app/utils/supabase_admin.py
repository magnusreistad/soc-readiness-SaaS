"""
app/utils/supabase_admin.py

Shared Supabase Auth Admin API helpers.
Uses the service role key — server-side only, never expose to clients.
"""

import logging
import os
import httpx
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


def _headers() -> dict:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_SERVICE_ROLE_KEY is not configured.",
        )
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def create_auth_user(email: str, password: str, name: str) -> str:
    """
    Creates a Supabase Auth user with email already confirmed.
    Returns the auth UUID string.
    Raises 409 if email already exists, 502 on Supabase unreachable.
    """
    url = f"{os.getenv('SUPABASE_URL')}/auth/v1/admin/users"
    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {"name": name},
    }

    try:
        resp = httpx.post(url, json=payload, headers=_headers(), timeout=10.0)
    except httpx.RequestError as exc:
        logger.error("Supabase Auth unreachable in create_auth_user: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach the authentication service. Please try again.",
        )

    if resp.status_code in (400, 422):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already registered.",
        )
    if not resp.is_success:
        logger.error("Supabase Auth error in create_auth_user (%s): %s", resp.status_code, resp.text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to complete this request right now. Please try again or contact support.",
        )

    return resp.json()["id"]


def reset_auth_password(auth_uid: str, new_password: str) -> None:
    """Updates a user's password via the Supabase Auth Admin API."""
    url = f"{os.getenv('SUPABASE_URL')}/auth/v1/admin/users/{auth_uid}"

    try:
        resp = httpx.put(
            url,
            json={"password": new_password},
            headers=_headers(),
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        logger.error("Supabase Auth unreachable in reset_auth_password: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach the authentication service. Please try again.",
        )

    if not resp.is_success:
        logger.error("Supabase Auth error in reset_auth_password (%s): %s", resp.status_code, resp.text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to complete this request right now. Please try again or contact support.",
        )


def delete_auth_user(auth_uid: str) -> None:
    """
    Permanently deletes a user from Supabase Auth.

    This is irreversible. The profiles row should be deleted first (or rely on
    a CASCADE foreign key), so the auth user is the last thing removed.
    Supabase returns 200 with an empty body on success, or 404 if not found
    (treated as a no-op — idempotent).
    """
    url = f"{os.getenv('SUPABASE_URL')}/auth/v1/admin/users/{auth_uid}"

    try:
        resp = httpx.delete(url, headers=_headers(), timeout=10.0)
    except httpx.RequestError as exc:
        logger.error("Supabase Auth unreachable in delete_auth_user: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach the authentication service. Please try again.",
        )

    # 404 is fine — auth user may already be gone; treat as success
    if resp.status_code == 404:
        return

    if not resp.is_success:
        logger.error("Supabase Auth error in delete_auth_user (%s): %s", resp.status_code, resp.text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to complete this request right now. Please try again or contact support.",
        )