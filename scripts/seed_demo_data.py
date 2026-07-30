#!/usr/bin/env python3
"""
scripts/seed_demo_data.py

Seeds a public-demo organization — "Meridian Health Partners", a fictional
healthcare company — with realistic SOC 2 controls, vendors, and incidents.

SAFETY: this is meant to run against a SEPARATE Supabase project dedicated
to the public demo, never against your real dev/production database. It
reads its config from DEMO_-prefixed environment variables ONLY — there is
no fallback to SUPABASE_URL / SUPABASE_DB_URL / SUPABASE_SERVICE_ROLE_KEY,
so it cannot accidentally run against your main project even if your real
.env is also loaded in the shell. It also refuses to run if the demo DB URL
matches your real .env's SUPABASE_DB_URL, in case of copy-paste mistakes.

Required env vars (put these in .env.demo — do NOT add them to .env):
    DEMO_SUPABASE_URL               https://<demo-project-ref>.supabase.co
    DEMO_SUPABASE_SERVICE_ROLE_KEY  service role key for the DEMO project
    DEMO_SUPABASE_DB_URL            Postgres connection string for the DEMO project

Before running this for the first time, apply the base schema and
supabase/migrations/*.sql to the demo project so the tables exist — this
script only inserts rows, it does not create tables.

Usage:
    python scripts/seed_demo_data.py                    # reads .env.demo
    python scripts/seed_demo_data.py --env-file .env.other

Idempotent: deletes any existing "Meridian Health Partners" demo org (and
everything under it) and re-inserts fresh data. Safe to re-run any time —
see also the nightly-reset discussion in the PR description.
"""

import argparse
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import psycopg2
import psycopg2.extras
from dotenv import dotenv_values

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.utils.control_classification import derive_testing_requirements

REPO_ROOT = Path(__file__).resolve().parent.parent

DEMO_ORG_NAME     = "Meridian Health Partners"
DEMO_ORG_SLUG     = "meridian-health-partners-demo"
DEMO_TSC_SCOPE    = ["Security", "Availability"]

DEMO_USER_EMAIL    = "demo@meridianhealthpartners-demo.com"
DEMO_USER_PASSWORD = "DemoReadOnly2026!"
DEMO_USER_NAME     = "Demo Viewer"
DEMO_USER_ROLE     = "admin"   # DEMO_MODE blocks writes regardless of role; admin gives the fullest read-only tour


# =============================================================================
# Fictional demo data
# =============================================================================

# control_id, title, description, control_type, frequency, status, owner, tsc_criteria
CONTROLS = [
    ("CC1-001", "Annual Board-Level Risk Assessment Review",
     "The Board of Directors and executive leadership conduct an annual review of "
     "the entity's risk assessment process, including emerging risks to patient data "
     "confidentiality and platform availability, and document updates to the risk register.",
     "manual", "annual", "cleared", "VP Compliance", ["CC1.2", "CC3.1"]),

    ("CC3-001", "Annual Penetration Test",
     "An independent third-party firm performs an annual penetration test against "
     "production infrastructure and the patient portal application. Findings are "
     "tracked to remediation and re-tested prior to closure.",
     "manual", "annual", "exception_noted", "Director of Security",
     ["CC7.1", "CC3.4"]),

    ("A1-001", "Annual Business Continuity / Disaster Recovery Test",
     "Management performs a full annual failover test of the production environment "
     "to the disaster recovery site, validating recovery time and recovery point "
     "objectives against the documented BC/DR plan.",
     "manual", "annual", "tested_no_exceptions", "Director of Infrastructure",
     ["A1.3", "CC9.1"]),

    ("CC9-001", "Vendor Risk Assessment",
     "Security reviews and re-assesses the risk tier of each critical vendor "
     "(SOC 2 report review, security questionnaire, breach history) on a "
     "semi-annual basis and updates the vendor risk register.",
     "manual", "semi_annual", "tested_no_exceptions", "GRC Analyst",
     ["CC9.2"]),

    ("CC6-001", "Quarterly User Access Review — Production Systems",
     "System owners review the full list of active user accounts with access to "
     "production systems each quarter, confirming access remains appropriate to "
     "job function and revoking any access that is no longer required.",
     "manual", "quarterly", "cleared", "IT Manager",
     ["CC6.2", "CC6.3"]),

    ("CC6-002", "Quarterly Privileged Access Review",
     "Security reviews all accounts holding administrative or privileged access to "
     "production databases and infrastructure each quarter to confirm least-privilege "
     "and segregation-of-duties principles are maintained.",
     "manual", "quarterly", "not_tested", "Director of Security",
     ["CC6.1", "CC6.3"]),

    ("CC6-003", "Quarterly Physical Access Review — Data Center Badge Access",
     "Facilities and Security jointly review the badge-access list for the co-located "
     "data center each quarter, removing access for anyone who no longer requires it.",
     "manual", "quarterly", "cleared", "Facilities Manager",
     ["CC6.4"]),

    ("CC6-004", "Monthly Terminated Employee Access Revocation Review",
     "HR provides a monthly list of terminated employees to IT, who confirm that all "
     "system access (SSO, email, VPN, physical badge) was revoked within 24 hours of "
     "separation and document any exceptions.",
     "manual", "monthly", "tested_no_exceptions", "IT Manager",
     ["CC6.2", "CC6.3"]),

    ("CC6-005", "Monthly Firewall and Network Rule Review",
     "Network Engineering reviews all active firewall and security group rules each "
     "month, confirming each rule maps to a documented business justification and "
     "removing rules that are no longer needed.",
     "manual", "monthly", "not_tested", "Network Engineer",
     ["CC6.6"]),

    ("CC8-001", "Change Management Approval Testing",
     "For a sample of production changes each quarter, Change Management confirms "
     "the change ticket includes documented approval, testing evidence, and a "
     "rollback plan prior to deployment, sourced from the change-tracking system.",
     "itdm", "quarterly", "cleared", "Release Manager",
     ["CC8.1"]),

    ("A1-002", "Backup Restoration Test",
     "IT Operations restores a sample of production database backups to an isolated "
     "environment each month and validates data integrity against the source system, "
     "with results logged in the backup management system.",
     "itdm", "monthly", "tested_no_exceptions", "Director of Infrastructure",
     ["A1.2", "A1.3"]),

    ("CC7-001", "Vulnerability Scan Remediation Tracking",
     "Security runs authenticated vulnerability scans against production systems each "
     "month; a sample of identified critical/high findings is reviewed to confirm "
     "remediation occurred within the SLA defined in the vulnerability management policy.",
     "itdm", "monthly", "not_tested", "Director of Security",
     ["CC7.1"]),

    ("CC6-006", "New Hire Access Provisioning Review",
     "For a sample of new hires each quarter, IT confirms that system access granted "
     "matches the access request approved by the hiring manager, sourced from the "
     "identity management system's provisioning log.",
     "itdm", "quarterly", "cleared", "IT Manager",
     ["CC6.2"]),

    ("CC6-007", "Automated Account Lockout Enforcement",
     "The identity provider automatically locks user accounts after five consecutive "
     "failed authentication attempts, without any manual intervention required.",
     "automated", "continuous", "tested_no_exceptions", "Director of Security",
     ["CC6.1"]),

    ("CC6-008", "Automated Encryption of Data at Rest and in Transit",
     "All production databases and object storage enforce encryption at rest (AES-256), "
     "and all external network traffic is required to use TLS 1.2 or higher, enforced "
     "by infrastructure configuration.",
     "automated", "continuous", "cleared", "Director of Infrastructure",
     ["CC6.1", "C1.1"]),

    ("CC7-002", "Automated Endpoint Detection and Response",
     "EDR agents deployed on all production endpoints automatically detect and "
     "quarantine known malware signatures and anomalous process behavior in real time.",
     "automated", "continuous", "not_tested", "Director of Security",
     ["CC6.8", "CC7.1"]),

    ("A1-003", "Automated Backup Job Execution Monitoring",
     "Automated backup jobs run nightly for all production databases, with job "
     "success/failure automatically logged and alerting the on-call engineer on "
     "any failure without requiring manual daily checks.",
     "automated", "daily", "cleared", "Director of Infrastructure",
     ["A1.2"]),

    ("CC7-003", "Security Incident Response Execution",
     "When a security event is escalated to an incident, the on-call security "
     "responder executes the documented incident response plan, including "
     "containment, eradication, and post-incident review, as needed.",
     "manual", "adhoc", "not_tested", "Director of Security",
     ["CC7.3", "CC7.4", "CC7.5"]),
]

# name, aliases, category (risk framing folded into category — this schema
# has no dedicated risk_tier column; see write-up)
VENDORS = [
    ("Amazon Web Services", ["AWS"], "Cloud Infrastructure — Critical Risk"),
    ("Okta", ["Okta Inc"], "Identity & Access Management — Critical Risk"),
    ("Stripe", ["Stripe Inc", "Stripe Payments"], "Payment Processing — Critical Risk"),
    ("Snowflake", ["Snowflake Computing"], "Data Warehouse — High Risk"),
    ("Salesforce", ["Salesforce.com", "SFDC"], "CRM / Customer Data — High Risk"),
    ("Datadog", ["Datadog Inc"], "Monitoring & Observability — High Risk"),
    ("Zendesk", ["Zendesk Inc"], "Customer Support Platform — Medium Risk"),
    ("Slack", ["Slack Technologies"], "Internal Communication — Medium Risk"),
    ("DocuSign", ["DocuSign Inc"], "Document Signing — Medium Risk"),
    ("Mailgun", ["Mailgun Technologies", "Sinch Mailgun"], "Email Delivery — Low Risk"),
]

# vendor, title, severity, incident_type, source_feed, alert_status,
# event_classification, days_ago
INCIDENTS = [
    ("Stripe", "Stripe discloses brief API key exposure in webhook debug logs",
     "medium", "api exposure", "Vendor Security Bulletin",
     "resolved", "system_event", 118),

    ("Okta", "Okta warns customers of credential-stuffing campaign targeting admin consoles",
     "high", "credential compromise", "The Hacker News",
     "acknowledged", "system_incident", 95),

    ("Amazon Web Services", "Misconfigured public S3 bucket exposes partner integrator data",
     "critical", "data leak", "BleepingComputer",
     "resolved", "system_incident", 80),

    ("Salesforce", "Compromised npm package in Salesforce integration toolchain",
     "critical", "supply chain attack", "CISA KEV",
     "new", "system_incident", 70),

    ("Slack", "Phishing campaign impersonating IT helpdesk targets employee workspace",
     "medium", "phishing campaign", "Internal SOC Alert",
     "acknowledged", "system_event", 65),

    ("Datadog", "Anomalous login flagged for Datadog admin account outside business hours",
     "low", "unauthorized access", "Internal SOC Alert",
     "false_positive", "unclassified", 60),

    ("Snowflake", "Credential-stuffing wave targets Snowflake customer instances without MFA",
     "high", "credential compromise", "The Hacker News",
     "resolved", "system_incident", 55),

    ("Zendesk", "Misconfigured macro exposes customer PII in support tickets",
     "medium", "data leak", "Vendor Security Bulletin",
     "resolved", "system_event", 40),

    ("DocuSign", "Impersonation phishing kit targets finance team using DocuSign branding",
     "medium", "phishing campaign", "BleepingComputer",
     "new", "system_event", 30),

    ("Amazon Web Services", "Actively exploited vulnerability in AWS-hosted VPN appliance",
     "critical", "exploited vulnerability", "CISA KEV",
     "acknowledged", "system_incident", 20),

    ("Mailgun", "Employees report phishing emails relayed through Mailgun infrastructure",
     "low", "phishing campaign", "Internal SOC Alert",
     "false_positive", "unclassified", 15),

    ("Stripe", "Denial-of-service activity observed against Stripe status page",
     "low", "denial of service", "The Hacker News",
     "resolved", "system_event", 10),

    ("Okta", "Departed contractor found with active session during offboarding audit",
     "high", "insider threat", "Internal SOC Alert",
     "new", "system_incident", 3),
]


# =============================================================================
# Config loading + safety checks
# =============================================================================

def load_demo_config(env_file: str) -> dict:
    env_path = REPO_ROOT / env_file
    file_values = dotenv_values(env_path) if env_path.exists() else {}

    def require(key: str) -> str:
        val = file_values.get(key) or os.environ.get(key)
        if not val:
            print(f"ERROR: {key} is not set. Add it to {env_file} (see script docstring).")
            sys.exit(1)
        return val

    config = {
        "db_url":       require("DEMO_SUPABASE_DB_URL"),
        "supabase_url": require("DEMO_SUPABASE_URL").rstrip("/"),
        "service_key":  require("DEMO_SUPABASE_SERVICE_ROLE_KEY"),
    }

    # Guard rail: refuse to run if the demo DB URL matches the real project's
    # DB URL, in case DEMO_SUPABASE_DB_URL was accidentally copy-pasted from .env.
    real_env_path = REPO_ROOT / ".env"
    if real_env_path.exists():
        real_values = dotenv_values(real_env_path)
        real_db_url = real_values.get("SUPABASE_DB_URL")
        if real_db_url and real_db_url == config["db_url"]:
            print(
                "ERROR: DEMO_SUPABASE_DB_URL is identical to SUPABASE_DB_URL in your "
                "real .env. Refusing to run — this looks like it would seed demo data "
                "into your real project. Point DEMO_SUPABASE_DB_URL at a separate "
                "Supabase project."
            )
            sys.exit(1)

    return config


# =============================================================================
# Supabase Auth Admin API — demo user upsert
# =============================================================================

def upsert_demo_auth_user(supabase_url: str, service_key: str) -> str:
    """Creates the demo auth user if absent, or resets its password if present.
    Returns the auth UUID either way."""
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }

    # List existing users and match by email client-side — more robust across
    # GoTrue versions than relying on server-side query-param filtering.
    resp = httpx.get(
        f"{supabase_url}/auth/v1/admin/users",
        params={"per_page": 1000},
        headers=headers,
        timeout=15.0,
    )
    resp.raise_for_status()
    existing = next(
        (u for u in resp.json().get("users", []) if u.get("email") == DEMO_USER_EMAIL),
        None,
    )

    if existing:
        uid = existing["id"]
        resp = httpx.put(
            f"{supabase_url}/auth/v1/admin/users/{uid}",
            json={
                "password": DEMO_USER_PASSWORD,
                "email_confirm": True,
                "user_metadata": {"name": DEMO_USER_NAME},
            },
            headers=headers,
            timeout=15.0,
        )
        resp.raise_for_status()
        print(f"  Reset password for existing demo auth user ({uid}).")
        return uid

    resp = httpx.post(
        f"{supabase_url}/auth/v1/admin/users",
        json={
            "email": DEMO_USER_EMAIL,
            "password": DEMO_USER_PASSWORD,
            "email_confirm": True,
            "user_metadata": {"name": DEMO_USER_NAME},
        },
        headers=headers,
        timeout=15.0,
    )
    resp.raise_for_status()
    uid = resp.json()["id"]
    print(f"  Created demo auth user ({uid}).")
    return uid


# =============================================================================
# Seeding
# =============================================================================

def wipe_org_children(cur, org_id: int) -> None:
    """Deletes everything under the org EXCEPT the organizations row itself,
    so org_id stays stable across re-runs (see get_or_create_org)."""
    for table in (
        "evidence_files",
        "false_positive_patterns",
        "readiness_responses",
        "readiness_results",
        "readiness_assessments",
        "ai_response_cache",
        "incidents",
        "controls",
        "vendors",
        "profiles",
    ):
        cur.execute(f"DELETE FROM {table} WHERE org_id = %s", (org_id,))


def get_or_create_org(cur) -> int:
    """
    Finds the demo org by its stable slug and updates it in place, or creates
    it if this is the first run. Never deletes/re-inserts the organizations
    row, so org_id is fixed across re-runs — callers (e.g. DEMO_ORG_ID on the
    demo API deployment) don't need to be updated every time you re-seed.
    """
    cur.execute("SELECT id FROM organizations WHERE slug = %s", (DEMO_ORG_SLUG,))
    row = cur.fetchone()

    if row:
        org_id = row["id"]
        print(f"  Found existing demo org (id={org_id}) — resetting its data...")
        cur.execute(
            """
            UPDATE organizations
            SET name = %s, tsc_scope = %s::jsonb, examination_type = %s
            WHERE id = %s
            """,
            (DEMO_ORG_NAME, json.dumps(DEMO_TSC_SCOPE), "type2", org_id),
        )
        wipe_org_children(cur, org_id)
        return org_id

    print("  No existing demo org found — creating it...")
    cur.execute(
        """
        INSERT INTO organizations (name, slug, tsc_scope, examination_type)
        VALUES (%s, %s, %s::jsonb, %s)
        RETURNING id
        """,
        (DEMO_ORG_NAME, DEMO_ORG_SLUG, json.dumps(DEMO_TSC_SCOPE), "type2"),
    )
    return cur.fetchone()["id"]


def seed_demo_profile(cur, org_id: int, auth_uid: str) -> None:
    cur.execute(
        """
        INSERT INTO profiles (id, org_id, full_name, email, role, active)
        VALUES (%s, %s, %s, %s, %s, TRUE)
        """,
        (auth_uid, org_id, DEMO_USER_NAME, DEMO_USER_EMAIL, DEMO_USER_ROLE),
    )


def seed_controls(cur, org_id: int) -> None:
    for control_id, title, description, control_type, frequency, status, owner, criteria in CONTROLS:
        reqs = derive_testing_requirements(control_type, frequency)
        cur.execute(
            """
            INSERT INTO controls (
                org_id, control_id, title, description, control_type, status,
                owner, tsc_criteria, ai_suggested_criteria, source, notes,
                frequency, requires_population, requires_sample, suggested_sample_size
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s::jsonb, '[]'::jsonb, 'manual', '',
                %s, %s, %s, %s
            )
            """,
            (
                org_id, control_id, title, description, control_type, status,
                owner, json.dumps(criteria),
                frequency, reqs["requires_population"], reqs["requires_sample"],
                reqs["suggested_sample_size"],
            ),
        )


def seed_vendors(cur, org_id: int) -> None:
    for name, aliases, category in VENDORS:
        cur.execute(
            """
            INSERT INTO vendors (org_id, name, aliases, category, active)
            VALUES (%s, %s, %s::jsonb, %s, TRUE)
            """,
            (org_id, name, json.dumps(aliases), category),
        )


def seed_incidents(cur, org_id: int) -> None:
    from app.utils.soc_mapper import get_criteria_for_incident_type, get_trust_categories

    now = datetime.now(timezone.utc)
    for vendor, title, severity, incident_type, source_feed, alert_status, event_classification, days_ago in INCIDENTS:
        detected_at = now - timedelta(days=days_ago, hours=random.randint(0, 23))
        soc_criteria = get_criteria_for_incident_type(incident_type)
        soc_type = ", ".join(get_trust_categories(incident_type))

        acknowledged_at = None
        acknowledged_by = ""
        notified_at = None
        if alert_status in ("acknowledged", "resolved"):
            acknowledged_at = detected_at + timedelta(hours=random.randint(1, 12))
            acknowledged_by = "demo-analyst@meridianhealthpartners-demo.com"
        if alert_status != "new":
            notified_at = detected_at + timedelta(minutes=random.randint(5, 90))

        cur.execute(
            """
            INSERT INTO incidents (
                org_id, article_link, title, vendor, summary, source_feed,
                published_at, severity, incident_type, ai_reason,
                soc_criteria, soc_type, alert_status, event_classification,
                notified_at, acknowledged_by, acknowledged_at, notes,
                detected_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s::jsonb, %s, %s, %s,
                %s, %s, %s, '',
                %s, %s
            )
            """,
            (
                org_id,
                f"https://example-demo-feed.invalid/articles/{vendor.lower().replace(' ', '-')}-{days_ago}",
                title, vendor, title, source_feed,
                detected_at.date().isoformat(), severity, incident_type,
                f"Flagged via {source_feed} monitoring — matched vendor '{vendor}' "
                f"and incident type '{incident_type}'.",
                json.dumps(soc_criteria), soc_type, alert_status, event_classification,
                notified_at, acknowledged_by, acknowledged_at,
                detected_at, detected_at,
            ),
        )


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env.demo",
                         help="Env file (relative to repo root) with DEMO_ vars. Default: .env.demo")
    args = parser.parse_args()

    config = load_demo_config(args.env_file)

    print(f"Seeding demo org '{DEMO_ORG_NAME}' into {config['supabase_url']} ...")

    print("Upserting demo login user via Supabase Auth Admin API...")
    auth_uid = upsert_demo_auth_user(config["supabase_url"], config["service_key"])

    conn = psycopg2.connect(config["db_url"], cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        with conn:
            with conn.cursor() as cur:
                org_id = get_or_create_org(cur)
                seed_demo_profile(cur, org_id, auth_uid)
                seed_controls(cur, org_id)
                seed_vendors(cur, org_id)
                seed_incidents(cur, org_id)
        print(f"Done. Seeded org_id={org_id} with {len(CONTROLS)} controls, "
              f"{len(VENDORS)} vendors, {len(INCIDENTS)} incidents.")
        print(f"Demo login: {DEMO_USER_EMAIL} / {DEMO_USER_PASSWORD}")
        print(f"Set DEMO_ORG_ID={org_id} in the demo API's environment to enable DEMO_MODE gating.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
