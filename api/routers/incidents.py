"""
api/routers/incidents.py

Incidents API router — mirrors the Flask threat_monitor blueprint
but returns JSON instead of rendering Jinja2 templates.

Endpoints:
    GET    /api/v1/incidents              list + filter
    GET    /api/v1/incidents/stats        dashboard stat counts
    GET    /api/v1/incidents/{id}         single incident
    PATCH  /api/v1/incidents/{id}/action  triage (ack, resolve, FP, classify)
    PATCH  /api/v1/incidents/{id}/notes   update notes
"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from api.dependencies import AnalystUser, AuthUser
from api.schemas.shared import (
    IncidentActionIn,
    IncidentListOut,
    IncidentNotesIn,
    IncidentOut,
    IncidentStatsOut,
)
from app.utils.db_postgres import (
    get_db,
    get_incident_by_id,
    get_incidents_filtered,
    get_stats,
    update_incident_notes,
)
from app.utils.fp_learner import learn_from_false_positive

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_incident_out(row: dict) -> IncidentOut:
    """
    Converts a db row dict to IncidentOut, ensuring soc_criteria is a list.
    In db_postgres.py JSONB columns already return lists, but the
    _normalise_incident() shim may have re-serialised to a string for
    Flask template compatibility. Both are handled here.
    """
    soc = row.get("soc_criteria", [])
    if isinstance(soc, str):
        try:
            soc = json.loads(soc)
        except Exception:
            soc = []

    return IncidentOut(
        id=row["id"],
        org_id=row["org_id"],
        article_link=row.get("article_link", ""),
        title=row.get("title", ""),
        summary=row.get("summary", ""),
        source_feed=row.get("source_feed", ""),
        published_at=row.get("published_at", ""),
        vendor=row.get("vendor", ""),
        vendor_id=row.get("vendor_id"),
        severity=row.get("severity", "unknown"),
        incident_type=row.get("incident_type", ""),
        ai_reason=row.get("ai_reason", ""),
        soc_criteria=soc,
        soc_type=row.get("soc_type", ""),
        alert_status=row.get("alert_status", "new"),
        event_classification=row.get("event_classification", "unclassified"),
        notified_at=row.get("notified_at"),
        acknowledged_by=row.get("acknowledged_by", ""),
        acknowledged_at=row.get("acknowledged_at"),
        notes=row.get("notes", ""),
        detected_at=str(row.get("detected_at", "")),
        updated_at=str(row.get("updated_at", "")),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/incidents
# ---------------------------------------------------------------------------

@router.get("/incidents", response_model=IncidentListOut)
def list_incidents(
    current_user: AuthUser,
    severity: Optional[str] = Query(None),
    vendor:   Optional[str] = Query(None),
    status:   Optional[str] = Query(None),
    source:   Optional[str] = Query(None),
    limit:    int           = Query(500, ge=1, le=5000),
):
    """
    Returns filtered incidents for the current user's org.
    All query params are optional — omit to return all.
    """
    rows = get_incidents_filtered(
        org_id   = current_user.org_id,
        severity = severity,
        vendor   = vendor,
        status   = status,
        source   = source,
        limit    = limit,
    )
    items = [_to_incident_out(r) for r in rows]
    return IncidentListOut(items=items, total=len(items))


# ---------------------------------------------------------------------------
# GET /api/v1/incidents/stats
# ---------------------------------------------------------------------------

@router.get("/incidents/stats", response_model=IncidentStatsOut)
def incident_stats(current_user: AuthUser):
    """Dashboard summary counts — total, by severity, by status."""
    s = get_stats(current_user.org_id)
    return IncidentStatsOut(**s)


# ---------------------------------------------------------------------------
# GET /api/v1/incidents/{incident_id}
# ---------------------------------------------------------------------------

@router.get("/incidents/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: int, current_user: AuthUser):
    row = get_incident_by_id(incident_id, current_user.org_id)
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return _to_incident_out(row)


# ---------------------------------------------------------------------------
# PATCH /api/v1/incidents/{incident_id}/action
# ---------------------------------------------------------------------------

VALID_ACTIONS = {
    "acknowledge", "resolve", "false_positive",
    "reopen", "system_event", "system_incident", "unclassified",
}

STATUS_MAP = {
    "acknowledge":   "acknowledged",
    "resolve":       "resolved",
    "false_positive": "false_positive",
    "reopen":        "new",
}

CLASSIFICATION_MAP = {
    "system_event":    "system_event",
    "system_incident": "system_incident",
    "unclassified":    "unclassified",
}


@router.patch(
    "/incidents/{incident_id}/action",
    response_model=IncidentOut,
)
def incident_action(
    incident_id:  int,
    body:         IncidentActionIn,
    current_user: AnalystUser,
):
    """
    Triage an incident — change alert status or event classification.
    Auditors are blocked (require_analyst dependency).
    """
    if body.action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid action '{body.action}'. "
                   f"Valid actions: {sorted(VALID_ACTIONS)}",
        )

    row = get_incident_by_id(incident_id, current_user.org_id)
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found.")

    with get_db() as conn:
        with conn.cursor() as cur:

            # Status-changing actions
            if body.action in STATUS_MAP:
                new_status = STATUS_MAP[body.action]
                extra_fields = ""
                params: list = [new_status]

                if body.action == "acknowledge":
                    extra_fields = ", acknowledged_by = %s, acknowledged_at = NOW()"
                    params.append(current_user.email)

                cur.execute(
                    f"UPDATE incidents SET alert_status = %s{extra_fields}, "
                    f"updated_at = NOW() WHERE id = %s AND org_id = %s",
                    (*params, incident_id, current_user.org_id),
                )

                # Learn FP pattern when analyst marks as false positive
                if body.action == "false_positive":
                    learn_from_false_positive(row, org_id=current_user.org_id)

            # Classification-only actions
            elif body.action in CLASSIFICATION_MAP:
                cur.execute(
                    "UPDATE incidents SET event_classification = %s, "
                    "updated_at = NOW() WHERE id = %s AND org_id = %s",
                    (CLASSIFICATION_MAP[body.action], incident_id, current_user.org_id),
                )

            # Update notes if provided
            if body.notes is not None:
                cur.execute(
                    "UPDATE incidents SET notes = %s, updated_at = NOW() "
                    "WHERE id = %s AND org_id = %s",
                    (body.notes, incident_id, current_user.org_id),
                )

    updated = get_incident_by_id(incident_id, current_user.org_id)
    return _to_incident_out(updated)


# ---------------------------------------------------------------------------
# PATCH /api/v1/incidents/{incident_id}/notes
# ---------------------------------------------------------------------------

@router.patch("/incidents/{incident_id}/notes", response_model=IncidentOut)
def update_notes(
    incident_id:  int,
    body:         IncidentNotesIn,
    current_user: AnalystUser,
):
    """Update the free-text notes field on an incident."""
    row = get_incident_by_id(incident_id, current_user.org_id)
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found.")

    update_incident_notes(incident_id, body.notes)
    updated = get_incident_by_id(incident_id, current_user.org_id)
    return _to_incident_out(updated)