import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# Feed URLs
# ---------------------------------------------------------------------------

CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

# NVD API — returns CVEs published or modified in the last N days
# We default to 7 days; can be overridden via fetch_nvd_cves(days=N)
NVD_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

# Only pull CVEs at or above this CVSS base score from NVD
NVD_MIN_SCORE = 7.0   # 7.0+ = High, 9.0+ = Critical

REQUEST_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def fetch_cve_articles(days: int = 7) -> list[dict]:
    """
    Fetches CVEs from CISA KEV and NVD and returns them as a flat list
    of article dicts in the same shape as rss_collector.fetch_articles().

    Each dict has:
        title       : str  — human-readable headline
        summary     : str  — description of the vulnerability
        link        : str  — reference URL
        source      : str  — 'CISA KEV' or 'NVD'
        published   : str  — published/added date
        cve_id      : str  — CVE identifier e.g. 'CVE-2024-12345'
        cvss_score  : float or None
        vendor_hint : str  — vendor/product name from the CVE data (used for matching)
    """
    articles = []
    seen_cve_ids = set()

    print("  [cve] Fetching CISA KEV feed...")
    cisa_articles = _fetch_cisa_kev(days=days)
    for a in cisa_articles:
        if a["cve_id"] not in seen_cve_ids:
            seen_cve_ids.add(a["cve_id"])
            articles.append(a)
    print(f"  [cve] CISA KEV: {len(cisa_articles)} entries fetched")

    print(f"  [cve] Fetching NVD feed (last {days} days, CVSS >= {NVD_MIN_SCORE})...")
    nvd_articles = _fetch_nvd_cves(days=days)
    added = 0
    for a in nvd_articles:
        if a["cve_id"] not in seen_cve_ids:
            seen_cve_ids.add(a["cve_id"])
            articles.append(a)
            added += 1
    print(f"  [cve] NVD: {added} new entries after dedup with CISA KEV")

    return articles


# ---------------------------------------------------------------------------
# CISA KEV
# ---------------------------------------------------------------------------

def _fetch_cisa_kev(days: int = 30) -> list[dict]:
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date()

    try:
        req = urllib.request.Request(
            CISA_KEV_URL,
            headers={"User-Agent": "VendorThreatMonitor/1.0"},
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        articles = []
        for vuln in data.get("vulnerabilities", []):
            # Only include entries added within our lookback window
            date_added_str = vuln.get("dateAdded", "")
            try:
                date_added = datetime.strptime(date_added_str, "%Y-%m-%d").date()
                if date_added < cutoff:
                    continue
            except ValueError:
                continue

            cve_id      = vuln.get("cveID", "")
            vendor_name = vuln.get("vendorProject", "")
            product     = vuln.get("product", "")
            description = vuln.get("shortDescription", "")
            due_date    = vuln.get("dueDate", "")
            action      = vuln.get("requiredAction", "")

            title   = f"{vendor_name} {product} — {cve_id} (CISA KEV: actively exploited)"
            summary = description
            if action:
                summary += f" Required action: {action}"
            if due_date:
                summary += f" Remediation due: {due_date}."

            articles.append({
                "title":       title,
                "summary":     summary,
                "link":        f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                "source":      "CISA KEV",
                "published":   date_added_str,
                "cve_id":      cve_id,
                "cvss_score":  None,
                "vendor_hint": vendor_name,
            })

        return articles

    except Exception as e:
        print(f"  [cve] CISA KEV fetch failed: {e}")
        return []


# ---------------------------------------------------------------------------
# NVD
# ---------------------------------------------------------------------------

def _fetch_nvd_cves(days: int = 7) -> list[dict]:
    try:
        now       = datetime.now(timezone.utc)
        start     = now - timedelta(days=days)
        pub_start = start.strftime("%Y-%m-%dT%H:%M:%S.000")
        pub_end   = now.strftime("%Y-%m-%dT%H:%M:%S.000")

        params = {
            "pubStartDate": pub_start,
            "pubEndDate":   pub_end,
            "resultsPerPage": 100,
        }

        url = f"{NVD_BASE_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "VendorThreatMonitor/1.0"},
        )

        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        articles = []
        for item in data.get("vulnerabilities", []):
            cve     = item.get("cve", {})
            cve_id  = cve.get("id", "")

            # Description — prefer English
            descriptions = cve.get("descriptions", [])
            description  = next(
                (d["value"] for d in descriptions if d.get("lang") == "en"),
                ""
            )

            # CVSS score — try v3.1 first, then v3.0, then v2
            cvss_score   = None
            cvss_version = None
            metrics      = cve.get("metrics", {})

            for version_key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                metric_list = metrics.get(version_key, [])
                if metric_list:
                    cvss_data  = metric_list[0].get("cvssData", {})
                    cvss_score = cvss_data.get("baseScore")
                    cvss_version = version_key
                    break

            # Skip CVEs below our minimum score threshold
            if cvss_score is not None and cvss_score < NVD_MIN_SCORE:
                continue

            # Affected vendor/product from CPE data
            vendor_hint = _extract_vendor_from_cpe(cve)

            # Severity label from CVSS score
            severity_label = _cvss_to_severity(cvss_score)

            # Published date
            published = cve.get("published", "")[:10]   # trim to YYYY-MM-DD

            # Reference URL — first available
            refs  = cve.get("references", [])
            link  = refs[0]["url"] if refs else f"https://nvd.nist.gov/vuln/detail/{cve_id}"

            score_str = f"CVSS {cvss_score}" if cvss_score else "score N/A"
            title     = f"{vendor_hint} — {cve_id} [{severity_label.upper()}, {score_str}]"

            articles.append({
                "title":        title,
                "summary":      description,
                "link":         link,
                "source":       "NVD",
                "published":    published,
                "cve_id":       cve_id,
                "cvss_score":   cvss_score,
                "vendor_hint":  vendor_hint,
            })

        return articles

    except Exception as e:
        print(f"  [cve] NVD fetch failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_vendor_from_cpe(cve: dict) -> str:
    """
    Extracts the most likely vendor/product string from CPE configuration data.
    CPE format: cpe:2.3:a:vendor:product:version:...
    Returns a readable 'Vendor Product' string, or empty string if not found.
    """
    try:
        configs = cve.get("configurations", [])
        for config in configs:
            for node in config.get("nodes", []):
                for cpe_match in node.get("cpeMatch", []):
                    cpe = cpe_match.get("criteria", "")
                    parts = cpe.split(":")
                    if len(parts) >= 5:
                        vendor  = parts[3].replace("_", " ").title()
                        product = parts[4].replace("_", " ").title()
                        if vendor and vendor != "*":
                            return f"{vendor} {product}".strip()
    except Exception:
        pass
    return ""


def _cvss_to_severity(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"