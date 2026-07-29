"""
app/utils/db_postgres.py

Postgres-backed database layer — drop-in replacement for database.py.
All public function signatures are identical so blueprints need only
change their import line:

    # Before:
    from app.utils.database import get_connection, get_all_vendors, ...

    # After:
    from app.utils.db_postgres import get_all_vendors, ...

Key differences from the SQLite version:
  - psycopg2 with RealDictCursor  (rows behave like dicts)
  - %s placeholders               (not ?)
  - RETURNING id                  (not lastrowid)
  - JSONB columns return Python lists/dicts natively
  - BOOLEAN columns return Python bools natively
  - ThreadedConnectionPool        (safe for Flask's threaded dev server)
  - profiles table                (replaces users — links to Supabase Auth)
  - NOW()                         (not CURRENT_TIMESTAMP)

Auth note:
  User lookup / password functions still exist here for the Flask-Login
  transition period. They read from the `profiles` table. Full Supabase
  Auth replacement happens in step 1d (auth.py rewrite).
"""

import json
import os
from contextlib import contextmanager
from datetime import datetime, date

import psycopg2
import psycopg2.extras
import psycopg2.pool
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        url = os.getenv("SUPABASE_DB_URL")
        if not url:
            raise RuntimeError(
                "SUPABASE_DB_URL is not set. "
                "Add it to your .env file and restart the server."
            )
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=url,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    return _pool


@contextmanager
def get_db():
    """
    Context manager that yields a psycopg2 connection from the pool.
    Commits on clean exit, rolls back on exception, always returns
    the connection to the pool.

    Usage:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ...")
                rows = cur.fetchall()
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def _to_str(val):
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return val


def _normalise_row(row: dict) -> dict:
    if not row:
        return row
    return {k: _to_str(v) for k, v in row.items()}


def _row(cursor) -> dict | None:
    row = cursor.fetchone()
    return _normalise_row(dict(row)) if row else None


def _rows(cursor) -> list[dict]:
    return [_normalise_row(dict(r)) for r in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Compatibility shim — lets old code that calls get_connection() still work
# during the transition. Remove once all imports are updated.
# ---------------------------------------------------------------------------

def get_connection():
    """
    Deprecated shim — returns a raw psycopg2 connection.
    Use the `get_db()` context manager for new code.
    """
    pool = _get_pool()
    conn = pool.getconn()
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn


# ---------------------------------------------------------------------------
# Schema init — no-op for Postgres (migrations handle this)
# Called by app/core/__init__.py on startup — safe to leave in place.
# ---------------------------------------------------------------------------

def initialize_database():
    """No-op — Postgres schema is managed by SQL migration files."""
    pass


# ===========================================================================
# VENDOR helpers
# ===========================================================================

def get_all_vendors(org_id: int | None = None) -> list[dict]:
    """
    Returns all active vendors.
    org_id is required in Postgres; falls back to org 1 if omitted
    (backwards-compat with run_collector.py which doesn't pass org_id yet).
    """
    oid = org_id or 1
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM vendors WHERE org_id = %s AND active = TRUE ORDER BY name",
                (oid,),
            )
            return _rows(cur)


def get_vendor_names_and_aliases(org_id: int = 1) -> list[str]:
    """Flat list of all vendor names + aliases for fuzzy matching."""
    vendors = get_all_vendors(org_id)
    all_names: list[str] = []
    for v in vendors:
        all_names.append(v["name"])
        aliases = v.get("aliases") or []
        if isinstance(aliases, str):
            try:
                aliases = json.loads(aliases)
            except Exception:
                aliases = []
        all_names.extend(aliases)
    return all_names


def get_all_vendors_detail(org_id: int) -> list[dict]:
    """Vendors with incident count — used by the vendors dashboard page."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT v.*,
                       COUNT(i.id) AS incident_count
                FROM vendors v
                LEFT JOIN incidents i
                       ON i.vendor = v.name AND i.org_id = v.org_id
                WHERE v.org_id = %s
                GROUP BY v.id
                ORDER BY v.name
            """, (org_id,))
            return _rows(cur)


def get_vendor_by_id(vendor_id: int, org_id: int) -> dict | None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM vendors WHERE id = %s AND org_id = %s",
                (vendor_id, org_id),
            )
            return _row(cur)


def upsert_vendors_from_json(vendor_list: list[str], org_id: int = 1):
    """Seeds vendors table from a name list. Safe to run multiple times."""
    with get_db() as conn:
        with conn.cursor() as cur:
            for name in vendor_list:
                cur.execute(
                    "INSERT INTO vendors (org_id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (org_id, name),
                )


# ===========================================================================
# INCIDENT helpers
# ===========================================================================

def incident_exists(article_link: str, org_id: int = 1) -> bool:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM incidents WHERE article_link = %s AND org_id = %s",
                (article_link, org_id),
            )
            return cur.fetchone() is not None


def store_incident(
    article_link: str,
    title: str,
    vendor: str,
    summary: str = "",
    source_feed: str = "",
    published_at: str = "",
    severity: str = "unknown",
    incident_type: str = "",
    ai_reason: str = "",
    soc_criteria: str = "[]",
    soc_type: str = "",
    alert_status: str = "new",
    fp_reason: str = "",
    org_id: int = 1,
) -> int | None:
    if incident_exists(article_link, org_id):
        return None

    combined_reason = ai_reason
    if fp_reason:
        combined_reason = f"{ai_reason} [Likely FP: {fp_reason}]".strip()

    # Normalise soc_criteria — accept both JSON string and Python list
    if isinstance(soc_criteria, list):
        soc_criteria_json = json.dumps(soc_criteria)
    else:
        soc_criteria_json = soc_criteria or "[]"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO incidents (
                    org_id, article_link, title, vendor, summary,
                    source_feed, published_at,
                    severity, incident_type, ai_reason,
                    soc_criteria, soc_type, alert_status
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s
                )
                RETURNING id
            """, (
                org_id, article_link, title, vendor, summary,
                source_feed, published_at,
                severity, incident_type, combined_reason,
                soc_criteria_json, soc_type, alert_status,
            ))
            row = cur.fetchone()
            return row["id"] if row else None


def update_alert_status(incident_id: int, status: str, notified_at: str = None):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE incidents
                SET alert_status = %s,
                    notified_at  = %s,
                    updated_at   = NOW()
                WHERE id = %s
            """, (status, notified_at, incident_id))


def get_incidents(
    status: str = None,
    severity: str = None,
    vendor: str = None,
    limit: int = 100,
    org_id: int = 1,
) -> list[dict]:
    """Flexible query — all filters optional."""
    clauses = ["org_id = %s"]
    params: list = [org_id]
    if status:
        clauses.append("alert_status = %s")
        params.append(status)
    if severity:
        clauses.append("severity = %s")
        params.append(severity)
    if vendor:
        clauses.append("vendor = %s")
        params.append(vendor)
    params.append(limit)
    sql = f"SELECT * FROM incidents WHERE {' AND '.join(clauses)} ORDER BY detected_at DESC LIMIT %s"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = _rows(cur)
    # Normalise soc_criteria to JSON string for Jinja templates
    return [_normalise_incident(r) for r in rows]


def get_incidents_filtered(
    org_id: int,
    severity: str = None,
    vendor: str = None,
    status: str = None,
    source: str = None,
    limit: int = 500,
) -> list[dict]:
    """Dashboard-filtered incident list."""
    clauses = ["org_id = %s"]
    params: list = [org_id]
    if severity:
        clauses.append("severity = %s")
        params.append(severity)
    if vendor:
        clauses.append("vendor = %s")
        params.append(vendor)
    if status:
        clauses.append("alert_status = %s")
        params.append(status)
    if source:
        clauses.append("source_feed = %s")
        params.append(source)
    params.append(limit)
    sql = f"SELECT * FROM incidents WHERE {' AND '.join(clauses)} ORDER BY detected_at DESC LIMIT %s"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = _rows(cur)
    return [_normalise_incident(r) for r in rows]


def get_incident_by_id(incident_id: int, org_id: int) -> dict | None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM incidents WHERE id = %s AND org_id = %s",
                (incident_id, org_id),
            )
            row = _row(cur)
    return _normalise_incident(row) if row else None


def update_incident_notes(incident_id: int, notes: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE incidents SET notes = %s, updated_at = NOW() WHERE id = %s",
                (notes, incident_id),
            )


def get_stats(org_id: int) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            stats: dict = {}

            cur.execute("SELECT COUNT(*) AS n FROM incidents WHERE org_id = %s", (org_id,))
            stats["total"] = cur.fetchone()["n"]

            for s in ("new", "notified", "acknowledged", "resolved"):
                cur.execute(
                    "SELECT COUNT(*) AS n FROM incidents WHERE org_id = %s AND alert_status = %s",
                    (org_id, s),
                )
                stats[s] = cur.fetchone()["n"]

            for sev in ("critical", "high", "medium", "low", "unknown"):
                cur.execute(
                    "SELECT COUNT(*) AS n FROM incidents WHERE org_id = %s AND severity = %s",
                    (org_id, sev),
                )
                stats[sev] = cur.fetchone()["n"]

            cur.execute(
                "SELECT DISTINCT vendor FROM incidents WHERE org_id = %s ORDER BY vendor",
                (org_id,),
            )
            stats["vendors"] = [r["vendor"] for r in cur.fetchall()]

            cur.execute(
                "SELECT DISTINCT source_feed FROM incidents WHERE org_id = %s AND source_feed != '' ORDER BY source_feed",
                (org_id,),
            )
            stats["sources"] = [r["source_feed"] for r in cur.fetchall()]

    return stats


def _normalise_incident(row: dict) -> dict:
    """
    Ensures soc_criteria is always a JSON string for template compatibility.
    Datetime conversion is handled upstream by _normalise_row.
    """
    if not row:
        return row
    row = dict(row)
    if isinstance(row.get("soc_criteria"), list):
        row["soc_criteria"] = json.dumps(row["soc_criteria"])
    return row


# ===========================================================================
# FALSE POSITIVE PATTERN helpers
# ===========================================================================

def get_all_patterns(org_id: int) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT fp.*, i.title AS source_title
                FROM false_positive_patterns fp
                LEFT JOIN incidents i ON i.id = fp.created_from_incident_id
                WHERE fp.org_id = %s
                ORDER BY fp.created_at DESC
            """, (org_id,))
            return _rows(cur)


def delete_pattern(pattern_id: int, org_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM false_positive_patterns WHERE id = %s AND org_id = %s",
                (pattern_id, org_id),
            )


def store_fp_pattern(
    org_id: int,
    pattern_type: str,
    cve_id: str = "",
    vendor: str = "",
    source_feed: str = "",
    incident_type: str = "",
    confidence: str = "medium",
    created_from_incident_id: int = None,
):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO false_positive_patterns
                    (org_id, pattern_type, cve_id, vendor, source_feed,
                     incident_type, confidence, created_from_incident_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                org_id, pattern_type, cve_id, vendor, source_feed,
                incident_type, confidence, created_from_incident_id,
            ))


def pattern_exists(
    org_id: int,
    pattern_type: str,
    cve_id: str = "",
    vendor: str = "",
    source_feed: str = "",
    incident_type: str = "",
) -> bool:
    with get_db() as conn:
        with conn.cursor() as cur:
            if pattern_type == "cve_id":
                cur.execute(
                    "SELECT 1 FROM false_positive_patterns WHERE org_id=%s AND pattern_type='cve_id' AND cve_id=%s",
                    (org_id, cve_id),
                )
            elif pattern_type == "vendor_source":
                cur.execute(
                    "SELECT 1 FROM false_positive_patterns WHERE org_id=%s AND pattern_type='vendor_source' AND vendor=%s AND source_feed=%s",
                    (org_id, vendor, source_feed),
                )
            else:
                cur.execute(
                    "SELECT 1 FROM false_positive_patterns WHERE org_id=%s AND pattern_type='vendor_type' AND vendor=%s AND incident_type=%s",
                    (org_id, vendor, incident_type),
                )
            return cur.fetchone() is not None


# ===========================================================================
# CONTROLS helpers
# ===========================================================================

CONTROL_TYPE_LABELS = {
    "automated": "Automated",
    "manual":    "Manual",
    "itdm":      "IT Dependent Manual",
}


def get_all_controls(org_id: int) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM controls WHERE org_id = %s ORDER BY control_id",
                (org_id,),
            )
            return [_normalise_control(r) for r in _rows(cur)]


def get_control_by_id(control_id: int, org_id: int) -> dict | None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM controls WHERE id = %s AND org_id = %s",
                (control_id, org_id),
            )
            row = _row(cur)
    return _normalise_control(row) if row else None


def store_control(
    org_id: int,
    control_id: str,
    title: str,
    description: str = "",
    control_type: str = "manual",
    status: str = "not_tested",
    owner: str = "",
    tsc_criteria: str = "[]",
    ai_suggested_criteria: str = "[]",
    source: str = "manual",
    notes: str = "",
    frequency: str | None = None,
    requires_population: bool = False,
    requires_sample: bool = False,
    suggested_sample_size: int | None = None,
) -> int:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO controls (
                    org_id, control_id, title, description, control_type,
                    status, owner, tsc_criteria, ai_suggested_criteria, source, notes,
                    frequency, requires_population, requires_sample, suggested_sample_size
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                org_id, control_id, title, description, control_type,
                status, owner,
                _ensure_json(tsc_criteria),
                _ensure_json(ai_suggested_criteria),
                source, notes,
                frequency, requires_population, requires_sample, suggested_sample_size,
            ))
            return cur.fetchone()["id"]


def update_control(id: int, org_id: int, **fields) -> bool:
    allowed = {
        "control_id", "title", "description", "control_type",
        "status", "owner", "tsc_criteria", "ai_suggested_criteria",
        "source", "notes",
        # Classification fields
        "frequency", "requires_population", "requires_sample", "suggested_sample_size",
        "narrative", "narrative_approved_at", "narrative_flags",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False

    json_fields = {"tsc_criteria", "ai_suggested_criteria"}
    set_parts = []
    values = []
    for col, val in updates.items():
        if col in json_fields:
            set_parts.append(f"{col} = %s")
            values.append(_ensure_json(val))
        else:
            set_parts.append(f"{col} = %s")
            values.append(val)

    set_parts.append("updated_at = NOW()")
    values.extend([id, org_id])
    sql = f"UPDATE controls SET {', '.join(set_parts)} WHERE id = %s AND org_id = %s"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, values)
            return cur.rowcount > 0


def delete_control(id: int, org_id: int) -> bool:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM controls WHERE id = %s AND org_id = %s",
                (id, org_id),
            )
            return cur.rowcount > 0




def _normalise_control(row: dict) -> dict:
    if not row:
        return row
    row = dict(row)
    for field in ("tsc_criteria", "ai_suggested_criteria"):
        if isinstance(row.get(field), list):
            row[field] = json.dumps(row[field])
    return row


# ===========================================================================
# ORGANISATION helpers
# ===========================================================================

VALID_TSC_SCOPE_CATEGORIES = {
    "Security", "Availability", "Confidentiality", "Processing Integrity", "Privacy"
}


def get_org_tsc_scope(org_id: int) -> list[str]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tsc_scope FROM organizations WHERE id = %s",
                (org_id,),
            )
            row = _row(cur)
    if not row:
        return ["Security"]
    scope = row["tsc_scope"]
    if isinstance(scope, list) and scope:
        return scope
    if isinstance(scope, str):
        try:
            result = json.loads(scope)
            if isinstance(result, list) and result:
                return result
        except Exception:
            pass
    return ["Security"]


def update_org_tsc_scope(org_id: int, categories: list[str]) -> bool:
    if not all(c in VALID_TSC_SCOPE_CATEGORIES for c in categories):
        return False
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE organizations SET tsc_scope = %s WHERE id = %s",
                (json.dumps(categories), org_id),
            )
            return cur.rowcount > 0


def get_or_create_default_org() -> int:
    """Migration bridge — returns org 1, creating it if absent."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM organizations ORDER BY id ASC LIMIT 1")
            row = _row(cur)
            if row:
                return row["id"]
            cur.execute(
                "INSERT INTO organizations (name, slug) VALUES (%s, %s) RETURNING id",
                ("Default Organization", "default"),
            )
            return cur.fetchone()["id"]


# ===========================================================================
# USER / PROFILE helpers  (transition layer — replaced fully in step 1d)
# ===========================================================================

def get_users_by_org(org_id: int) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, full_name AS name, email, role,
                       active AS is_active, created_at, last_login_at AS last_login
                FROM profiles
                WHERE org_id = %s
                ORDER BY created_at DESC
            """, (org_id,))
            return _rows(cur)


def get_user_by_email(email: str) -> dict | None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, org_id, full_name AS name, email,
                       password_hash, role, active AS is_active,
                       last_login_at AS last_login, created_at
                FROM profiles
                WHERE email = %s
                LIMIT 1
            """, (email,))
            return _row(cur)


def get_user_by_id(user_id, org_id: int) -> dict | None:
    """Accepts both int and UUID string for user_id (transition period)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, full_name AS name, email, role,
                       active AS is_active, created_at, last_login_at AS last_login
                FROM profiles
                WHERE id = %s AND org_id = %s
            """, (str(user_id), org_id))
            return _row(cur)


def create_user_in_org(
    org_id: int,
    name: str,
    email: str,
    hashed_password: str,
    role: str,
) -> str:
    import uuid
    user_uuid = uuid.uuid4()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO profiles 
                    (id, org_id, full_name, email, password_hash, role, active)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id
            """, (str(user_uuid), org_id, name, email, hashed_password, role))
            return str(cur.fetchone()["id"])


def update_user_role(user_id, org_id: int, role: str) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE profiles SET role = %s WHERE id = %s AND org_id = %s",
                (role, str(user_id), org_id),
            )


def set_user_active(user_id, org_id: int, is_active: bool) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE profiles SET active = %s WHERE id = %s AND org_id = %s",
                (is_active, str(user_id), org_id),
            )


# ===========================================================================
# READINESS helpers
# ===========================================================================

def create_assessment(org_id: int, report_type: str, tsc_scope: str) -> int:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO readiness_assessments (org_id, report_type, tsc_scope)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (org_id, report_type, _ensure_json(tsc_scope)))
            return cur.fetchone()["id"]


def get_assessments(org_id: int) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM readiness_assessments WHERE org_id = %s ORDER BY created_at DESC",
                (org_id,),
            )
            return _rows(cur)


def get_assessment_by_id(assessment_id: int, org_id: int) -> dict | None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM readiness_assessments WHERE id = %s AND org_id = %s",
                (assessment_id, org_id),
            )
            return _row(cur)


def get_latest_assessment(org_id: int) -> dict | None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM readiness_assessments WHERE org_id = %s ORDER BY created_at DESC LIMIT 1",
                (org_id,),
            )
            return _row(cur)


def upsert_response(
    assessment_id: int,
    org_id: int,
    criteria_code: str,
    has_process: int,
    is_documented: int,
    is_consistent: int,
    notes: str,
) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO readiness_responses
                    (assessment_id, org_id, criteria_code,
                     has_process, is_documented, is_consistent, notes, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (assessment_id, criteria_code) DO UPDATE SET
                    has_process   = EXCLUDED.has_process,
                    is_documented = EXCLUDED.is_documented,
                    is_consistent = EXCLUDED.is_consistent,
                    notes         = EXCLUDED.notes,
                    updated_at    = NOW()
            """, (
                assessment_id, org_id, criteria_code,
                bool(has_process), bool(is_documented), bool(is_consistent), notes,
            ))


def get_responses(assessment_id: int, org_id: int) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM readiness_responses WHERE assessment_id = %s AND org_id = %s",
                (assessment_id, org_id),
            )
            return {r["criteria_code"]: dict(r) for r in cur.fetchall()}


def upsert_result(
    assessment_id: int,
    org_id: int,
    criteria_code: str,
    status: str,
    source: str,
    control_ids: str,
    ai_recommendation: str,
) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO readiness_results
                    (assessment_id, org_id, criteria_code, status, source,
                     control_ids, ai_recommendation, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (assessment_id, criteria_code) DO UPDATE SET
                    status            = EXCLUDED.status,
                    source            = EXCLUDED.source,
                    control_ids       = EXCLUDED.control_ids,
                    ai_recommendation = EXCLUDED.ai_recommendation,
                    updated_at        = NOW()
            """, (
                assessment_id, org_id, criteria_code, status, source,
                _ensure_json(control_ids), ai_recommendation,
            ))


def get_results(assessment_id: int, org_id: int) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM readiness_results WHERE assessment_id = %s AND org_id = %s",
                (assessment_id, org_id),
            )
            return {r["criteria_code"]: dict(r) for r in cur.fetchall()}


def update_assessment_score(
    assessment_id: int, org_id: int, score: float, status: str
) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE readiness_assessments
                SET overall_score = %s,
                    status        = %s,
                    updated_at    = NOW(),
                    completed_at  = CASE WHEN %s = 'completed' THEN NOW() ELSE completed_at END
                WHERE id = %s AND org_id = %s
            """, (score, status, status, assessment_id, org_id))


def get_criteria_for_scope(tsc_scope: list[str]) -> list[str]:
    """Imported from soc_mapper but mirrored here for convenience."""
    from app.utils.soc_mapper import get_criteria_for_scope as _get
    return _get(tsc_scope)


# ===========================================================================
# AI CACHE helpers
# ===========================================================================

def get_cached_ai_response(content_hash: str, org_id: int) -> dict | None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT result_json FROM ai_response_cache WHERE org_id = %s AND content_hash = %s",
                (org_id, content_hash),
            )
            row = _row(cur)
    if not row:
        return None
    result = row["result_json"]
    return result if isinstance(result, dict) else json.loads(result)


def store_cached_ai_response(
    content_hash: str, model: str, result: dict, org_id: int
) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ai_response_cache (org_id, content_hash, model, result_json)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (org_id, content_hash) DO NOTHING
            """, (org_id, content_hash, model, json.dumps(result)))


# ===========================================================================
# Internal helpers
# ===========================================================================

def _ensure_json(value) -> str:
    """Coerce a value to a JSON string. Accepts str, list, or dict."""
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    if isinstance(value, str):
        try:
            json.loads(value)
            return value
        except Exception:
            return "[]"
    return "[]"


# ===========================================================================
# Create org_id when new profile signs up
# ===========================================================================

def create_org_with_profile(
    org_name: str,
    admin_name: str,
    email: str,
    auth_uid: str,
    role: str = "admin",
) -> int:
    """
    Creates a new organization row and a profiles row for the first admin.
    Returns the new org_id (bigint).
    Runs as a single transaction — rolls back both if either insert fails.
    """
    import re
    import time
    import json

    base_slug = re.sub(r"[^a-z0-9-]", "", org_name.lower().replace(" ", "-"))
    slug = f"{base_slug}-{int(time.time())}"

    with get_db() as conn:
        with conn.cursor() as cur:
            # 1. Insert org
            cur.execute(
                """
                INSERT INTO organizations (name, slug, tsc_scope)
                VALUES (%s, %s, %s::jsonb)
                RETURNING id
                """,
                (org_name, slug, json.dumps(["Security"])),
            )
            org_id = cur.fetchone()["id"]

            # 2. Insert profiles row using Supabase auth UUID as PK
            cur.execute(
                """
                INSERT INTO profiles (id, org_id, full_name, email, role, active)
                VALUES (%s, %s, %s, %s, %s, true)
                """,
                (auth_uid, org_id, admin_name, email, role),
            )

    return org_id