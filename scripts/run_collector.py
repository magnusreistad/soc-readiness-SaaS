import sys
import os
import json
import re
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.collectors.rss_collector import fetch_articles
from app.collectors.cve_collector import fetch_cve_articles
from app.ai.incident_classifier import classify_and_extract
from app.ai.severity_scorer import score_incident
from app.utils.keyword_filter import passes_keyword_filter
from app.utils.vendor_matcher import match_vendors, format_match_log
from app.utils.db_postgres import (
    initialize_database,
    store_incident,
    update_alert_status,
    get_all_vendors,
)
from app.alerts.alert_manager import create_alert, send_digest, ALERT_MODE


def main():
    initialize_database()

    vendor_records = get_all_vendors(org_id=1)
    print(f"\nMonitoring {len(vendor_records)} vendors")
    print(f"Alert mode: {ALERT_MODE}\n")

    # ── Collect from all sources ─────────────────────────────────────────────
    print("=== Collecting RSS articles ===")
    rss_articles = fetch_articles()
    print(f"  RSS: {len(rss_articles)} articles\n")

    print("=== Collecting CVE data ===")
    cve_articles = fetch_cve_articles(days=7)
    print(f"  CVE total: {len(cve_articles)} entries\n")

    all_articles = rss_articles + cve_articles
    print(f"Total articles to process: {len(all_articles)}\n")

    matched_count = 0
    alerted_count = 0
    skipped_count = 0
    digest_queue  = []

    for article in all_articles:
        title        = article.get("title", "")
        summary      = article.get("summary", "")
        link         = article.get("link", "")
        source       = article.get("source", "Unknown")
        published_at = article.get("published", "")
        is_cve       = source in ("CISA KEV", "NVD")

        # ── Vendor matching ──────────────────────────────────────────────────
        # CVE articles: match on vendor_hint field directly (no GPT needed)
        # RSS articles: use GPT to extract companies, then fuzzy match
        if is_cve:
            matches = _match_cve_article(article, vendor_records)
        else:
            matches = _match_rss_article(article, vendor_records)

        if not matches:
            skipped_count += 1
            continue

        # ── Scoring ──────────────────────────────────────────────────────────
        # CVE articles: derive severity directly from CVSS score (no GPT needed)
        # RSS articles: use GPT severity scorer
        if is_cve:
            scores = _score_cve_article(article)
        else:
            scores = score_incident(title, summary)

        print(f"\n[+] {'CVE' if is_cve else 'RSS'} incident: {title[:75]}")
        print(f"    Vendor matches:")
        print(format_match_log(matches))
        print(f"    Severity      : {scores['severity'].upper()}")
        print(f"    Incident type : {scores['incident_type']}")
        print(f"    SOC criteria  : {scores['soc_criteria']}")

        # ── Step 5: Store + alert for each matched vendor ────────────────────
        for match in matches:
            matched_count += 1

            enriched_article = {
                **article,
                "source":        source,
                "severity":      scores["severity"],
                "incident_type": scores["incident_type"],
                "ai_reason":     scores["ai_reason"],
                "soc_criteria":  scores["soc_criteria"],
            }

            # ── False positive check ─────────────────────────────────────────
            from app.utils.fp_learner import check_false_positive_patterns
            fp_match = check_false_positive_patterns(
                title         = title,
                vendor        = match["vendor"],
                source_feed   = source,
                incident_type = scores["incident_type"],
            )

            if fp_match:
                print(f"    [FP] Likely false positive ({fp_match['confidence']} confidence): "
                    f"{fp_match['reason']}")
                # Store but pre-label — don't send alert
                store_incident(
                    article_link  = link,
                    title         = title,
                    vendor        = match["vendor"],
                    summary       = summary,
                    source_feed   = source,
                    published_at  = published_at,
                    severity      = scores["severity"],
                    incident_type = scores["incident_type"],
                    ai_reason     = scores["ai_reason"],
                    soc_criteria  = scores["soc_criteria"],
                    alert_status  = "likely_false_positive",
                    fp_reason     = fp_match["reason"],
                    org_id        = 1,
                )
                continue  # skip alerting

            incident_id = store_incident(
                article_link  = link,
                title         = title,
                vendor        = match["vendor"],
                summary       = summary,
                source_feed   = source,
                published_at  = published_at,
                severity      = scores["severity"],
                incident_type = scores["incident_type"],
                ai_reason     = scores["ai_reason"],
                soc_criteria  = scores["soc_criteria"],
                org_id        = 1,
            )

            if incident_id is None:
                print(f"    [skip] Already stored: {match['vendor']}")
                continue

            if ALERT_MODE == "digest":
                digest_queue.append({
                    "vendor":      match["vendor"],
                    "article":     enriched_article,
                    "incident_id": incident_id,
                })
                alerted_count += 1
            else:
                alert_sent = create_alert(match["vendor"], enriched_article, incident_id)
                if alert_sent:
                    alerted_count += 1
                    update_alert_status(
                        incident_id,
                        status     = "notified",
                        notified_at= datetime.now(timezone.utc).isoformat(),
                    )

        print("-" * 50)

    # ── Send digest ───────────────────────────────────────────────────────────
    if ALERT_MODE == "digest" and digest_queue:
        print(f"\nSending digest for {len(digest_queue)} new incident(s)...")
        digest_sent = send_digest(digest_queue)
        if digest_sent:
            for item in digest_queue:
                update_alert_status(
                    item["incident_id"],
                    status="notified",
                    notified_at=datetime.now(timezone.utc).isoformat(),
                )

    # ── Run summary ───────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  Run complete")
    print(f"  Alert mode         : {ALERT_MODE}")
    print(f"  RSS articles       : {len(rss_articles)}")
    print(f"  CVE entries        : {len(cve_articles)}")
    print(f"  Incidents matched  : {matched_count}")
    print(f"  Alerts sent        : {alerted_count}")
    print(f"  Skipped            : {skipped_count}")
    print(f"{'='*50}\n")


# ---------------------------------------------------------------------------
# CVE-specific helpers (bypass GPT — data is already structured)
# ---------------------------------------------------------------------------

def _match_cve_article(article: dict, vendor_records: list[dict]) -> list[dict]:
    """
    For CVE articles, match using vendor_hint from the CVE data directly.
    Also tries the title as a fallback.
    """
    vendor_hint = article.get("vendor_hint", "")
    title       = article.get("title", "")

    candidates = []
    if vendor_hint:
        candidates.append(vendor_hint)

    # Also extract any additional names from the title
    for part in re.split(r"[—\-,]", title):
        part = part.strip()
        if part and part not in candidates:
            candidates.append(part)

    return match_vendors(candidates, vendor_records)


def _score_cve_article(article: dict) -> dict:
    import json as _json
    from app.utils.soc_mapper import get_criteria_for_incident_type

    cvss_score = article.get("cvss_score")
    source     = article.get("source", "")

    if cvss_score is not None:
        if cvss_score >= 9.0:   severity = "critical"
        elif cvss_score >= 7.0: severity = "high"
        elif cvss_score >= 4.0: severity = "medium"
        else:                   severity = "low"
    else:
        severity = "high" if source == "CISA KEV" else "unknown"

    incident_type = "exploited vulnerability"

    if cvss_score:
        ai_reason = f"CVSS score {cvss_score} — {severity} severity vulnerability."
    elif source == "CISA KEV":
        ai_reason = "Listed in CISA Known Exploited Vulnerabilities — actively exploited in the wild."
    else:
        ai_reason = "Vulnerability reported via NVD."

    # Use shared mapper instead of hardcoded criteria
    soc_criteria = _json.dumps(get_criteria_for_incident_type(incident_type))

    return {
        "severity":      severity,
        "incident_type": incident_type,
        "ai_reason":     ai_reason,
        "soc_criteria":  soc_criteria,
    }


def _match_rss_article(article: dict, vendor_records: list[dict]) -> list[dict]:
    """
    For RSS articles, use GPT to extract companies then fuzzy match.
    Includes the incident classification check.
    """
    title   = article.get("title", "")
    summary = article.get("summary", "")

    if not passes_keyword_filter(title, summary):
        return []

    result = classify_and_extract(title, summary)
    if not result["is_incident"]:
        return []

    return match_vendors(result["companies"], vendor_records)


if __name__ == "__main__":
    main()