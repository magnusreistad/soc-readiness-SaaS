"""
api/routers/vendors.py

Vendors API — CRUD for the monitored vendor list.

Endpoints:
    GET    /api/v1/vendors           list all vendors with incident counts
    POST   /api/v1/vendors           add a vendor
    PATCH  /api/v1/vendors/{id}      update name / aliases / category / active
    DELETE /api/v1/vendors/{id}      remove a vendor
"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from api.dependencies import AnalystUser, AuthUser
from api.schemas.shared import VendorIn, VendorOut, VendorUpdateIn
from app.utils.db_postgres import (
    get_all_vendors_detail,
    get_vendor_by_id,
    get_db,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_vendor_out(row: dict) -> VendorOut:
    aliases = row.get("aliases", [])
    if isinstance(aliases, str):
        try:
            aliases = json.loads(aliases)
        except Exception:
            aliases = []
    return VendorOut(
        id=row["id"],
        org_id=row["org_id"],
        name=row["name"],
        aliases=aliases,
        category=row.get("category", ""),
        active=bool(row.get("active", True)),
        created_at=str(row.get("created_at", "")),
        incident_count=row.get("incident_count", 0),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/vendors
# ---------------------------------------------------------------------------

@router.get("/vendors", response_model=list[VendorOut])
def list_vendors(current_user: AuthUser):
    """Returns all vendors for the org with their incident counts."""
    rows = get_all_vendors_detail(current_user.org_id)
    return [_to_vendor_out(r) for r in rows]


# ---------------------------------------------------------------------------
# POST /api/v1/vendors
# ---------------------------------------------------------------------------

@router.post("/vendors", response_model=VendorOut, status_code=status.HTTP_201_CREATED)
def create_vendor(body: VendorIn, current_user: AnalystUser):
    """Add a vendor to the monitored list."""
    with get_db() as conn:
        with conn.cursor() as cur:
            # Check for duplicate within this org
            cur.execute(
                "SELECT id FROM vendors WHERE org_id = %s AND name = %s",
                (current_user.org_id, body.name.strip()),
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Vendor '{body.name}' already exists in your organisation.",
                )

            cur.execute(
                """
                INSERT INTO vendors (org_id, name, aliases, category, active)
                VALUES (%s, %s, %s, %s, TRUE)
                RETURNING id
                """,
                (
                    current_user.org_id,
                    body.name.strip(),
                    json.dumps(body.aliases),
                    body.category.strip(),
                ),
            )
            new_id = cur.fetchone()["id"]

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT *, 0 AS incident_count FROM vendors WHERE id = %s",
                (new_id,),
            )
            row = cur.fetchone()

    return _to_vendor_out(dict(row))


# ---------------------------------------------------------------------------
# PATCH /api/v1/vendors/{vendor_id}
# ---------------------------------------------------------------------------

@router.patch("/vendors/{vendor_id}", response_model=VendorOut)
def update_vendor(
    vendor_id:    int,
    body:         VendorUpdateIn,
    current_user: AnalystUser,
):
    """Update vendor name, aliases, category, or active status."""
    row = get_vendor_by_id(vendor_id, current_user.org_id)
    if not row:
        raise HTTPException(status_code=404, detail="Vendor not found.")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields provided to update.",
        )

    set_parts = []
    values    = []
    for col, val in updates.items():
        if col == "aliases":
            set_parts.append("aliases = %s")
            values.append(json.dumps(val))
        else:
            set_parts.append(f"{col} = %s")
            values.append(val)

    # vendors table has no updated_at column — omit it
    set_parts = [p for p in set_parts if p]
    values.extend([vendor_id, current_user.org_id])

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE vendors SET {', '.join(set_parts)} "
                f"WHERE id = %s AND org_id = %s",
                values,
            )

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT v.*, COUNT(i.id) AS incident_count "
                "FROM vendors v LEFT JOIN incidents i ON i.vendor = v.name AND i.org_id = v.org_id "
                "WHERE v.id = %s GROUP BY v.id",
                (vendor_id,),
            )
            updated = cur.fetchone()

    return _to_vendor_out(dict(updated))


# ---------------------------------------------------------------------------
# DELETE /api/v1/vendors/{vendor_id}
# ---------------------------------------------------------------------------

@router.delete("/vendors/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vendor(vendor_id: int, current_user: AnalystUser):
    """Remove a vendor from the monitored list."""
    row = get_vendor_by_id(vendor_id, current_user.org_id)
    if not row:
        raise HTTPException(status_code=404, detail="Vendor not found.")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM vendors WHERE id = %s AND org_id = %s",
                (vendor_id, current_user.org_id),
            )