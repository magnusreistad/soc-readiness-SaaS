"""
api/routers/admin.py

Admin API — user management and org settings.

Endpoints:
    GET    /api/v1/admin/org                       org details + TSC scope (admin only)
    PATCH  /api/v1/admin/org/tsc-scope             update TSC scope (admin only)
    PATCH  /api/v1/admin/org/examination-type      update examination type (admin only)
    GET    /api/v1/org/settings                    read-only org config (any authenticated user)
    GET    /api/v1/org/users                       read-only user list (any authenticated user)
    GET    /api/v1/admin/users                     full user list (admin only)
    POST   /api/v1/admin/users/invite              invite a new user (admin only)
    PATCH  /api/v1/admin/users/{id}/role           change user role (admin only)
    PATCH  /api/v1/admin/users/{id}/toggle         activate/deactivate (admin only)
    POST   /api/v1/admin/users/{id}/reset-password generate temp password (admin only)
    DELETE /api/v1/admin/users/{id}                permanently delete user (admin only)
"""

import secrets
import string
import json

from fastapi import APIRouter, HTTPException, status

from api.dependencies import AdminUser, AuthUser
from api.schemas.shared import (
    OrgOut,
    TscScopeUpdateIn,
    ExamTypeUpdateIn,
    UserInviteIn,
    UserOut,
    UserRoleUpdateIn,
)
from app.utils.db_postgres import (
    get_org_tsc_scope,
    get_user_by_email,
    get_user_by_id,
    get_users_by_org,
    set_user_active,
    update_org_tsc_scope,
    update_user_role,
    get_db,
)
from app.utils.supabase_admin import create_auth_user, reset_auth_password, delete_auth_user

router = APIRouter()

VALID_CATEGORIES = {
    "Security", "Availability", "Confidentiality", "Processing Integrity", "Privacy"
}


# ---------------------------------------------------------------------------
# GET /api/v1/admin/org
# ---------------------------------------------------------------------------

@router.get("/admin/org", response_model=OrgOut)
def get_org(current_user: AdminUser):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, name, slug, tsc_scope, examination_type,
                   plan, subscription_status, trial_ends_at
                   FROM organizations WHERE id = %s""",
                (current_user.org_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Organisation not found.")

    tsc = row["tsc_scope"]
    if isinstance(tsc, str):
        try:
            tsc = json.loads(tsc)
        except Exception:
            tsc = ["Security"]

    return OrgOut(
        id=row["id"],
        name=row["name"],
        slug=row.get("slug", ""),
        tsc_scope=tsc,
        examination_type=row.get("examination_type", "type2"),
        plan=row.get("plan", "free"),
        subscription_status=row.get("subscription_status", "trialing"),
        trial_ends_at=str(row["trial_ends_at"]) if row.get("trial_ends_at") else None,
    )


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/org/tsc-scope
# ---------------------------------------------------------------------------

@router.patch("/admin/org/tsc-scope", response_model=OrgOut)
def update_tsc_scope(body: TscScopeUpdateIn, current_user: AdminUser):
    categories = [c for c in body.categories if c in VALID_CATEGORIES]
    if "Security" not in categories:
        categories.insert(0, "Security")

    if len(categories) != len(body.categories):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid categories. Valid: {sorted(VALID_CATEGORIES)}",
        )

    update_org_tsc_scope(current_user.org_id, categories)
    return get_org(current_user)


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/org/examination-type
# ---------------------------------------------------------------------------

@router.patch("/admin/org/examination-type", response_model=OrgOut)
def update_examination_type(body: ExamTypeUpdateIn, current_user: AdminUser):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE organizations SET examination_type = %s WHERE id = %s",
                (body.examination_type, current_user.org_id),
            )
    return get_org(current_user)


# ---------------------------------------------------------------------------
# GET /api/v1/org/settings  — any authenticated user
# ---------------------------------------------------------------------------

@router.get("/org/settings")
def get_org_settings_public(current_user: AuthUser):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tsc_scope, examination_type FROM organizations WHERE id = %s",
                (current_user.org_id,),
            )
            row = cur.fetchone()
    if not row:
        return {"tsc_scope": ["Security"], "examination_type": "type2"}
    tsc = row["tsc_scope"]
    if isinstance(tsc, str):
        try:
            tsc = json.loads(tsc)
        except Exception:
            tsc = ["Security"]
    return {
        "tsc_scope": tsc,
        "examination_type": row.get("examination_type", "type2"),
    }


# ---------------------------------------------------------------------------
# GET /api/v1/org/users  — any authenticated user (read-only)
# Used by the Settings > Users page for non-admin roles.
# ---------------------------------------------------------------------------

@router.get("/org/users", response_model=list[UserOut])
def list_users_public(current_user: AuthUser):
    rows = get_users_by_org(current_user.org_id)
    return [_to_user_out(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /api/v1/admin/users  — admin only
# ---------------------------------------------------------------------------

@router.get("/admin/users", response_model=list[UserOut])
def list_users(current_user: AdminUser):
    rows = get_users_by_org(current_user.org_id)
    return [_to_user_out(r) for r in rows]


# ---------------------------------------------------------------------------
# POST /api/v1/admin/users/invite
# ---------------------------------------------------------------------------

@router.post(
    "/admin/users/invite",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
def invite_user(body: UserInviteIn, current_user: AdminUser):
    """
    Invite flow (two-step, atomic-ish):
      1. Check no duplicate in profiles
      2. Create Supabase Auth user with temp password + email_confirm=true
      3. Upsert profiles row using the returned auth UUID
    """
    existing = get_user_by_email(str(body.email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email {body.email} already exists.",
        )

    alphabet = string.ascii_letters + string.digits + "!@#$%"
    temp_password = "".join(secrets.choice(alphabet) for _ in range(14))

    auth_uid = create_auth_user(
        email=str(body.email),
        password=temp_password,
        name=body.name,
    )

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO profiles (id, org_id, full_name, email, role, active)
                VALUES (%s, %s, %s, %s, %s, true)
                ON CONFLICT (id) DO UPDATE SET
                    org_id    = EXCLUDED.org_id,
                    full_name = EXCLUDED.full_name,
                    role      = EXCLUDED.role,
                    active    = true
                """,
                (auth_uid, current_user.org_id, body.name, str(body.email), body.role),
            )

    return {
        "message":       f"User {body.name} created successfully.",
        "email":         str(body.email),
        "role":          body.role,
        "temp_password": temp_password,
        "warning":       "Share this temporary password via a secure channel. "
                         "It will not be shown again.",
    }


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/users/{user_id}/role
# ---------------------------------------------------------------------------

@router.patch("/admin/users/{user_id}/role", response_model=UserOut)
def change_role(user_id: str, body: UserRoleUpdateIn, current_user: AdminUser):
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role.",
        )

    user = get_user_by_id(user_id, current_user.org_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    update_user_role(user_id, current_user.org_id, body.role)
    updated = get_user_by_id(user_id, current_user.org_id)
    return _to_user_out(updated)


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/users/{user_id}/toggle
# ---------------------------------------------------------------------------

@router.patch("/admin/users/{user_id}/toggle", response_model=UserOut)
def toggle_user(user_id: str, current_user: AdminUser):
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )

    user = get_user_by_id(user_id, current_user.org_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    new_state = not bool(user.get("is_active", True))
    set_user_active(user_id, current_user.org_id, new_state)
    updated = get_user_by_id(user_id, current_user.org_id)
    return _to_user_out(updated)


# ---------------------------------------------------------------------------
# POST /api/v1/admin/users/{user_id}/reset-password
# ---------------------------------------------------------------------------

@router.post("/admin/users/{user_id}/reset-password", response_model=dict)
def reset_password(user_id: str, current_user: AdminUser):
    user = get_user_by_id(user_id, current_user.org_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    alphabet = string.ascii_letters + string.digits + "!@#$%"
    temp_password = "".join(secrets.choice(alphabet) for _ in range(14))

    reset_auth_password(auth_uid=user_id, new_password=temp_password)

    return {
        "message":       f"Password reset for {user.get('name', user_id)}.",
        "temp_password": temp_password,
        "warning":       "Share this temporary password via a secure channel.",
    }


# ---------------------------------------------------------------------------
# DELETE /api/v1/admin/users/{user_id}
# ---------------------------------------------------------------------------

@router.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, current_user: AdminUser):
    """
    Permanently removes a user from the workspace.

    Order of operations:
      1. Guard: cannot delete yourself
      2. Guard: cannot delete the last admin in the org
      3. Delete profiles row
      4. Delete Supabase Auth user (revokes all active sessions)

    A dangling Auth user with no profile is harmless — they get 401 on every
    API call since the JWT hook can't find an org_id claim for them.
    """
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )

    user = get_user_by_id(user_id, current_user.org_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.get("role") == "admin":
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS n FROM profiles WHERE org_id = %s AND role = 'admin'",
                    (current_user.org_id,),
                )
                admin_count = cur.fetchone()["n"]
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last admin. Assign another admin first.",
            )

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM profiles WHERE id = %s AND org_id = %s",
                (user_id, current_user.org_id),
            )

    delete_auth_user(auth_uid=user_id)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _to_user_out(row: dict) -> UserOut:
    return UserOut(
        id=str(row["id"]),
        org_id=row.get("org_id", 0),
        name=row.get("name") or row.get("full_name", ""),
        email=row.get("email", ""),
        role=row.get("role", "analyst"),
        is_active=bool(row.get("is_active", True)),
        created_at=str(row.get("created_at", "")),
        last_login=str(row["last_login"]) if row.get("last_login") else None,
    )