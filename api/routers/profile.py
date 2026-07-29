"""
api/routers/profile.py
"""

import logging
import os
import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from api.dependencies import AuthUser
from app.utils.supabase_admin import reset_auth_password

router = APIRouter()
logger = logging.getLogger(__name__)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


@router.post("/profile/change-password", response_model=dict)
def change_password(body: ChangePasswordIn, current_user: AuthUser):

    # 1. Basic validations
    if len(body.new_password) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password must be at least 10 characters.",
        )
    if body.new_password != body.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Passwords do not match.",
        )
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password must be different from your current password.",
        )

    # 2. Verify current password by attempting sign-in
    verify_url = f"{os.getenv('SUPABASE_URL')}/auth/v1/token?grant_type=password"
    try:
        resp = httpx.post(
            verify_url,
            json={"email": current_user.email, "password": body.current_password},
            headers={
                "apikey": os.getenv("SUPABASE_ANON_KEY", ""),
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        logger.error("Supabase Auth unreachable during password verify: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to verify your password right now. Please try again.",
        )

    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    # 3. All checks passed — update password
    reset_auth_password(auth_uid=current_user.user_id, new_password=body.new_password)

    return {"message": "Password updated successfully."}