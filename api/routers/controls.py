"""
api/routers/controls.py

Controls API — SOC 2 control inventory CRUD.
The list endpoint now enriches each control with evidence health data
(evidence_count, worst_verdict, phases_present, audit_bucket, next_action)
so the frontend can render the execution dashboard without extra requests.

Endpoints:
    GET    /api/v1/controls                  list all controls + evidence health
    POST   /api/v1/controls                  create a control
    GET    /api/v1/controls/{id}             single control
    PATCH  /api/v1/controls/{id}             update a control
    DELETE /api/v1/controls/{id}             delete a control
"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from api.dependencies import AnalystUser, AuthUser
from api.schemas.shared import (
    ControlIn,
    ControlOut,
    ControlUpdateIn,
)
from app.utils.db_postgres import (
    delete_control,
    get_control_by_id,
    store_control,
    update_control,
    get_db,
)
from app.utils.soc_mapper import SOC_LABELS
from app.utils.control_classification import (
    derive_testing_requirements,
    explain_testing_approach,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_control_id(org_id: int, first_criteria_code: str) -> str:
    prefix = first_criteria_code if first_criteria_code else "CTL"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM controls WHERE org_id = %s AND control_id LIKE %s",
                (org_id, f"{prefix}%"),
            )
            count = cur.fetchone()["n"]
    return f"{prefix}-{count + 1:03d}"


def _parse_criteria(val) -> list[str]:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return []
    return []


def _derive_audit_bucket(
    evidence_count: int,
    worst_verdict: Optional[str],
    phases_present: list[str],
    requires_population: bool = True,
    requires_sample: bool = True,
) -> str:
    """
    Maps evidence health into one of four action buckets:
      audit_ready   — required phases present, all ready_to_submit
      at_risk       — has evidence with needs_work verdict or incomplete required phases
      blocked       — has evidence with do_not_submit verdict
      no_evidence   — no evidence files at all

    Respects requires_population and requires_sample so that automated and
    annual manual controls can reach audit_ready with walkthrough evidence only.
    """
    if evidence_count == 0:
        return 'no_evidence'
    if worst_verdict == 'do_not_submit':
        return 'blocked'

    phases_set = set(phases_present or [])

    # Build the set of phases this control actually needs
    required: set[str] = {'walkthrough'}
    if requires_population:
        required |= {'testing_population', 'testing_ipe'}
    if requires_sample:
        required.add('testing_sample')

    if phases_set >= required and worst_verdict == 'ready_to_submit':
        return 'audit_ready'
    return 'at_risk'


def _derive_next_action(
    audit_bucket: str,
    phases_present: list[str],
    requires_population: bool = True,
    requires_sample: bool = True,
) -> str:
    """
    Returns a concrete, prescriptive next step for this control.
    Written as a direct instruction so GRC teams know exactly what to do.
    """
    if audit_bucket == 'audit_ready':
        return 'Ready for auditor review'

    phases_set = set(phases_present or [])

    if audit_bucket == 'no_evidence':
        return 'Upload walkthrough evidence to begin'

    if 'walkthrough' not in phases_set:
        return 'Upload walkthrough evidence first'

    if requires_population:
        if 'testing_population' not in phases_set and 'testing_ipe' not in phases_set:
            return 'Upload population export and IPE validation'
        if 'testing_population' not in phases_set:
            return 'Upload population export'
        if 'testing_ipe' not in phases_set:
            return 'Add IPE validation to population evidence'

    if requires_sample and 'testing_sample' not in phases_set:
        return 'Upload sample evidence'

    if audit_bucket == 'blocked':
        return 'Fix Do Not Submit findings in evidence'

    return 'Address weak evidence findings'


def _to_control_out(row: dict) -> ControlOut:
    evidence_count  = int(row.get('evidence_count') or 0)
    worst_verdict   = row.get('worst_verdict') or None
    phases_raw      = row.get('phases_present') or []
    phases_present  = [p for p in (phases_raw if isinstance(phases_raw, list) else []) if p]

    requires_population = bool(row.get('requires_population', False))
    requires_sample     = bool(row.get('requires_sample', False))

    audit_bucket = _derive_audit_bucket(
        evidence_count, worst_verdict, phases_present,
        requires_population=requires_population,
        requires_sample=requires_sample,
    )
    next_action = _derive_next_action(
        audit_bucket, phases_present,
        requires_population=requires_population,
        requires_sample=requires_sample,
    )

    last_evidence_at = row.get('last_evidence_at')
    control_type     = row.get('control_type', 'manual')
    frequency        = row.get('frequency') or None

    # narrative_flags can be a list (from JSONB) or JSON string
    narrative_flags_raw = row.get('narrative_flags') or []
    if isinstance(narrative_flags_raw, str):
        try:
            narrative_flags_raw = json.loads(narrative_flags_raw)
        except Exception:
            narrative_flags_raw = []

    return ControlOut(
        id=row["id"],
        org_id=row["org_id"],
        control_id=row["control_id"],
        title=row["title"],
        description=row.get("description", ""),
        control_type=control_type,
        status=row.get("status", "not_tested"),
        owner=row.get("owner", ""),
        tsc_criteria=_parse_criteria(row.get("tsc_criteria")),
        ai_suggested_criteria=_parse_criteria(row.get("ai_suggested_criteria")),
        source=row.get("source", "manual"),
        notes=row.get("notes", ""),
        created_at=str(row.get("created_at", "")),
        updated_at=str(row.get("updated_at", "")),
        # Classification
        frequency=frequency,
        requires_population=requires_population,
        requires_sample=requires_sample,
        suggested_sample_size=row.get("suggested_sample_size"),
        narrative=row.get("narrative"),
        narrative_approved_at=str(row["narrative_approved_at"]) if row.get("narrative_approved_at") else None,
        narrative_flags=narrative_flags_raw,
        # Computed on read
        testing_approach=explain_testing_approach(control_type, frequency),
        # Evidence health
        evidence_count=evidence_count,
        worst_verdict=worst_verdict,
        phases_present=phases_present,
        last_evidence_at=str(last_evidence_at) if last_evidence_at else None,
        audit_bucket=audit_bucket,
        next_action=next_action,
    )


def _get_controls_with_evidence_health(org_id: int) -> list[dict]:
    """
    Single query that returns all controls enriched with evidence health.
    Uses LEFT JOIN + GROUP BY so controls with no evidence still appear.
    Worst verdict is derived via CASE priority in SQL.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.*,
                    COUNT(ef.id)                        AS evidence_count,
                    MAX(ef.evaluated_at)                AS last_evidence_at,
                    ARRAY_AGG(DISTINCT ef.phase)
                        FILTER (WHERE ef.phase IS NOT NULL)
                                                        AS phases_present,
                    CASE
                        WHEN COUNT(ef.id) = 0
                            THEN NULL
                        WHEN COUNT(ef.id) FILTER (
                            WHERE ef.evaluation->>'verdict' = 'do_not_submit'
                        ) > 0
                            THEN 'do_not_submit'
                        WHEN COUNT(ef.id) FILTER (
                            WHERE ef.evaluation->>'verdict' = 'needs_work'
                        ) > 0
                            THEN 'needs_work'
                        WHEN COUNT(ef.id) FILTER (
                            WHERE ef.evaluation->>'verdict' = 'ready_to_submit'
                        ) = COUNT(ef.id)
                            THEN 'ready_to_submit'
                        ELSE 'needs_work'
                    END                                 AS worst_verdict
                FROM controls c
                LEFT JOIN evidence_files ef
                    ON ef.control_id = c.id
                    AND ef.org_id    = c.org_id
                WHERE c.org_id = %s
                GROUP BY c.id
                ORDER BY c.control_id
                """,
                (org_id,),
            )
            return [dict(row) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# GET /api/v1/controls
# ---------------------------------------------------------------------------

@router.get("/controls", response_model=list[ControlOut])
def list_controls(current_user: AuthUser):
    rows = _get_controls_with_evidence_health(current_user.org_id)
    return [_to_control_out(r) for r in rows]


# ---------------------------------------------------------------------------
# POST /api/v1/controls
# ---------------------------------------------------------------------------

@router.post("/controls", response_model=ControlOut, status_code=status.HTTP_201_CREATED)
def create_control(body: ControlIn, current_user: AnalystUser):
    valid_criteria = [c for c in body.tsc_criteria if c in SOC_LABELS]
    first_code = valid_criteria[0] if valid_criteria else ""
    control_id = _next_control_id(current_user.org_id, first_code)

    # Derive testing requirements server-side — never trust client-supplied values
    reqs = derive_testing_requirements(body.control_type, body.frequency)

    new_id = store_control(
        org_id                = current_user.org_id,
        control_id            = control_id,
        title                 = body.title,
        description           = body.description,
        control_type          = body.control_type,
        status                = body.status or 'not_tested',
        owner                 = body.owner,
        tsc_criteria          = json.dumps(valid_criteria),
        notes                 = body.notes,
        source                = "manual",
        frequency             = body.frequency,
        requires_population   = reqs['requires_population'],
        requires_sample       = reqs['requires_sample'],
        suggested_sample_size = reqs['suggested_sample_size'],
    )
    row = get_control_by_id(new_id, current_user.org_id)
    return _to_control_out({**row, 'evidence_count': 0, 'last_evidence_at': None,
                             'phases_present': [], 'worst_verdict': None})


# ---------------------------------------------------------------------------
# GET /api/v1/controls/{control_id}
# ---------------------------------------------------------------------------

@router.get("/controls/{control_id}", response_model=ControlOut)
def get_control(control_id: int, current_user: AuthUser):
    row = get_control_by_id(control_id, current_user.org_id)
    if not row:
        raise HTTPException(status_code=404, detail="Control not found.")
    return _to_control_out({**row, 'evidence_count': 0, 'last_evidence_at': None,
                             'phases_present': [], 'worst_verdict': None})


# ---------------------------------------------------------------------------
# PATCH /api/v1/controls/{control_id}
# ---------------------------------------------------------------------------

@router.patch("/controls/{control_id}", response_model=ControlOut)
def update_control_endpoint(
    control_id: int,
    body: ControlUpdateIn,
    current_user: AnalystUser,
):
    row = get_control_by_id(control_id, current_user.org_id)
    if not row:
        raise HTTPException(status_code=404, detail="Control not found.")

    updates = body.model_dump(exclude_none=True)
    if "tsc_criteria" in updates:
        updates["tsc_criteria"] = json.dumps(
            [c for c in updates["tsc_criteria"] if c in SOC_LABELS]
        )

    # If control_type or frequency changed, re-derive testing requirements
    if "control_type" in updates or "frequency" in updates:
        new_type = updates.get("control_type", row.get("control_type", "manual"))
        new_freq = updates.get("frequency", row.get("frequency"))
        reqs = derive_testing_requirements(new_type, new_freq)
        updates["requires_population"]   = reqs["requires_population"]
        updates["requires_sample"]       = reqs["requires_sample"]
        updates["suggested_sample_size"] = reqs["suggested_sample_size"]

    if updates:
        update_control(control_id, current_user.org_id, **updates)

    updated = get_control_by_id(control_id, current_user.org_id)
    return _to_control_out({**updated, 'evidence_count': 0, 'last_evidence_at': None,
                             'phases_present': [], 'worst_verdict': None})


# ---------------------------------------------------------------------------
# DELETE /api/v1/controls/{control_id}
# ---------------------------------------------------------------------------

@router.delete("/controls/{control_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_control(control_id: int, current_user: AnalystUser):
    row = get_control_by_id(control_id, current_user.org_id)
    if not row:
        raise HTTPException(status_code=404, detail="Control not found.")
    delete_control(control_id, current_user.org_id)
