"""
api/routers/auth.py

Public authentication endpoints — no JWT required.

Endpoints:
    POST /api/v1/auth/signup    Create a new org + admin user
"""

import re
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from api.dependencies import block_demo_signup
from app.utils.supabase_admin import create_auth_user
from app.utils.db_postgres import create_org_with_profile, get_user_by_email

router = APIRouter()


class SignupIn(BaseModel):
    org_name: str = Field(min_length=2, max_length=100)
    admin_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=10)
    confirm_password: str

    def validate_passwords_match(self) -> None:
        if self.password != self.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Passwords do not match.",
            )


class SignupOut(BaseModel):
    message: str
    org_name: str
    email: str


@router.post(
    "/auth/signup",
    response_model=SignupOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(block_demo_signup)],
)
def signup(body: SignupIn):
    """
    Creates a new organisation and its first admin user.
    Steps:
      1. Validate passwords match
      2. Check email not already in profiles
      3. Create Supabase Auth user (sets password, confirms email)
      4. Create org + profiles row in Postgres (single transaction)
    """
    body.validate_passwords_match()

    # Check profiles — catches duplicate orgs from the same admin email
    if get_user_by_email(str(body.email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Create Supabase Auth user — raises 409/502 on failure
    auth_uid = create_auth_user(
        email=str(body.email),
        password=body.password,
        name=body.admin_name,
    )

    # Create org + profile row
    create_org_with_profile(
        org_name=body.org_name,
        admin_name=body.admin_name,
        email=str(body.email),
        auth_uid=auth_uid,
        role="admin",
    )

    return SignupOut(
        message=f"Workspace '{body.org_name}' created. You can now sign in.",
        org_name=body.org_name,
        email=str(body.email),
    )