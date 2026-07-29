"""
False Positive Learning — app/utils/fp_learner.py

When an incident is marked as a false positive, this module:
  1. Extracts patterns from the incident (CVE ID, vendor+source, vendor+type)
  2. Stores them in the false_positive_patterns table
  3. Provides a check function used by run_collector.py to pre-label
     similar future incidents as 'likely_false_positive'

Three pattern types (in order of confidence):
  cve_id          : exact same CVE ID appeared again — highest confidence
  vendor_source   : same vendor + same source feed — medium confidence
  vendor_type     : same vendor + same incident type — lowest confidence
"""

import re
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from app.utils.db_postgres import get_connection


# ---------------------------------------------------------------------------
# Learn from a false positive
# ---------------------------------------------------------------------------

def learn_from_false_positive(incident: dict, org_id: int = 1) -> list[dict]:
    """
    Called when an incident is marked as false_positive.
    Extracts up to three patterns and stores them.
    Returns the list of patterns created.
    """
    incident_id   = incident.get("id")
    vendor        = incident.get("vendor", "").strip()
    source_feed   = incident.get("source_feed", "").strip()
    incident_type = incident.get("incident_type", "").strip()
    title         = incident.get("title", "")

    patterns_created = []

    conn = get_connection()
    cursor = conn.cursor()

    # ── Pattern 1: CVE ID match ──────────────────────────────────────────────
    cve_id = _extract_cve_id(title)
    if cve_id:
        if not _pattern_exists(cursor, "cve_id", cve_id=cve_id, org_id=org_id):
            cursor.execute("""
                INSERT INTO false_positive_patterns
                    (pattern_type, cve_id, vendor, confidence, created_from_incident_id, org_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, ("cve_id", cve_id, vendor, "high", incident_id, org_id))
            patterns_created.append({
                "type":        "cve_id",
                "description": f"CVE ID match: {cve_id}",
                "confidence":  "high",
            })

    # ── Pattern 2: Vendor + source feed ─────────────────────────────────────
    if vendor and source_feed:
        if not _pattern_exists(cursor, "vendor_source",
                               vendor=vendor, source_feed=source_feed, org_id=org_id):
            # Only create this pattern after 2+ false positives for the same
            # vendor/source combo — avoids over-learning from a single case
            cursor.execute("""
                SELECT COUNT(*) FROM false_positive_patterns
                WHERE pattern_type = 'vendor_source'
                AND vendor = %s AND source_feed = %s AND org_id = %s
            """, (vendor, source_feed, org_id))
            existing = cursor.fetchone()[0]

            # Also check how many FPs from this combo exist in incidents table
            cursor.execute("""
                SELECT COUNT(*) FROM incidents
                WHERE vendor = %s AND source_feed = %s
                AND alert_status = 'false_positive' AND org_id = %s
            """, (vendor, source_feed, org_id))
            fp_count = cursor.fetchone()[0]

            if fp_count >= 2:
                cursor.execute("""
                    INSERT INTO false_positive_patterns
                        (pattern_type, vendor, source_feed, confidence,
                         created_from_incident_id, org_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, ("vendor_source", vendor, source_feed, "medium", incident_id, org_id))
                patterns_created.append({
                    "type":        "vendor_source",
                    "description": f"Vendor+source: {vendor} / {source_feed}",
                    "confidence":  "medium",
                })

    # ── Pattern 3: Vendor + incident type ───────────────────────────────────
    if vendor and incident_type:
        cursor.execute("""
            SELECT COUNT(*) FROM incidents
            WHERE vendor = %s AND incident_type = %s
            AND alert_status = 'false_positive' AND org_id = %s
        """, (vendor, incident_type, org_id))
        fp_type_count = cursor.fetchone()[0]

        if fp_type_count >= 3:
            if not _pattern_exists(cursor, "vendor_type",
                                   vendor=vendor, incident_type=incident_type, org_id=org_id):
                cursor.execute("""
                    INSERT INTO false_positive_patterns
                        (pattern_type, vendor, incident_type,
                         confidence, created_from_incident_id, org_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, ("vendor_type", vendor, incident_type, "low", incident_id, org_id))
                patterns_created.append({
                    "type":        "vendor_type",
                    "description": f"Vendor+type: {vendor} / {incident_type}",
                    "confidence":  "low",
                })

    conn.commit()
    conn.close()
    return patterns_created


# ---------------------------------------------------------------------------
# Check a new incident against patterns
# ---------------------------------------------------------------------------

def check_false_positive_patterns(
    title: str,
    vendor: str,
    source_feed: str,
    incident_type: str,
) -> dict | None:
    """
    Checks a new incident against stored false positive patterns.

    Returns a match dict if a pattern fires:
        {
            pattern_type : str,
            confidence   : 'high' | 'medium' | 'low',
            reason       : str,
        }
    Returns None if no pattern matches.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Load all patterns once
    cursor.execute("SELECT * FROM false_positive_patterns")
    patterns = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not patterns:
        return None

    cve_id = _extract_cve_id(title)

    for p in patterns:
        ptype = p["pattern_type"]

        # High confidence: exact CVE match
        if ptype == "cve_id" and cve_id and p.get("cve_id") == cve_id:
            return {
                "pattern_type": "cve_id",
                "confidence":   "high",
                "reason":       f"CVE {cve_id} was previously marked as a false positive.",
            }

        # Medium confidence: same vendor + source feed
        if (ptype == "vendor_source"
                and p.get("vendor") == vendor
                and p.get("source_feed") == source_feed):
            return {
                "pattern_type": "vendor_source",
                "confidence":   "medium",
                "reason":       (f"Multiple false positives detected for "
                                 f"{vendor} from {source_feed}."),
            }

        # Low confidence: same vendor + incident type
        if (ptype == "vendor_type"
                and p.get("vendor") == vendor
                and p.get("incident_type") == incident_type):
            return {
                "pattern_type": "vendor_type",
                "confidence":   "low",
                "reason":       (f"Multiple false positives detected for "
                                 f"{vendor} / {incident_type} incidents."),
            }

    return None


# ---------------------------------------------------------------------------
# Pattern management
# ---------------------------------------------------------------------------

def get_all_patterns(org_id: int = 1) -> list[dict]:
    """Returns all stored false positive patterns for the UI, scoped to an org."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fp.*, i.title as source_title
        FROM false_positive_patterns fp
        LEFT JOIN incidents i ON i.id = fp.created_from_incident_id
        WHERE fp.org_id = %s
        ORDER BY fp.created_at DESC
    """, (org_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_pattern(pattern_id: int, org_id: int = 1):
    """Removes a false positive pattern — use when a pattern is too aggressive."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM false_positive_patterns WHERE id = %s AND org_id = %s", (pattern_id, org_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_cve_id(text: str) -> str | None:
    """Extracts the first CVE ID from a string, e.g. 'CVE-2024-12345'."""
    match = re.search(r"CVE-\d{4}-\d{4,7}", text, re.IGNORECASE)
    return match.group(0).upper() if match else None


def _pattern_exists(cursor, pattern_type: str, **kwargs) -> bool:
    """Checks if an identical pattern already exists."""
    query  = "SELECT 1 FROM false_positive_patterns WHERE pattern_type = %s"
    params = [pattern_type]
    for k, v in kwargs.items():
        query  += f" AND {k} = %s"
        params.append(v)
    cursor.execute(query, params)
    return cursor.fetchone() is not None