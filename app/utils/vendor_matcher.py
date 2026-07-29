import json
from rapidfuzz import fuzz, process


def _parse_json(val, default=None):
    if default is None:
        default = []
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return default
    return default

# ---------------------------------------------------------------------------
# Matching config
# ---------------------------------------------------------------------------

FUZZY_THRESHOLD = 85   # minimum similarity score (0-100) to count as a match
                       # 85 catches 'Google LLC' → 'Google' but rejects 'Go' → 'Google'
                       # Raise to 90+ for stricter matching, lower to 80 for looser


def match_vendors(extracted_companies: list[str], vendor_records: list[dict]) -> list[dict]:
    """
    Given a list of company names extracted from an article, and a list of
    vendor records from the DB, return a list of matches.

    Each match dict contains:
        vendor      : canonical vendor name (from DB)
        matched_on  : the extracted company name that triggered the match
        method      : 'exact', 'alias', or 'fuzzy'
        score       : similarity score (100 for exact/alias, float for fuzzy)

    Deduplicates — a vendor only appears once even if matched multiple ways.
    """
    if not extracted_companies or not vendor_records:
        return []

    # Build lookup structures
    # exact_map  : lowercase name/alias → canonical vendor name
    # alias_map  : canonical name → list of all aliases (for reporting)
    exact_map = {}
    for record in vendor_records:
        canonical = record["name"]
        exact_map[canonical.lower()] = canonical

        aliases = _parse_json(record.get("aliases"))

        for alias in aliases:
            exact_map[alias.lower()] = canonical

    # All canonical names for fuzzy matching
    canonical_names = [r["name"] for r in vendor_records]

    matched   = {}   # canonical name → match dict (deduped)

    for company in extracted_companies:
        if not company or not isinstance(company, str):
            continue

        company_clean = company.strip()
        company_lower = company_clean.lower()

        # ── Layer 1a: exact name match ───────────────────────────────────────
        if company_lower in exact_map:
            canonical = exact_map[company_lower]
            if canonical not in matched:
                matched[canonical] = {
                    "vendor":     canonical,
                    "matched_on": company_clean,
                    "method":     "exact",
                    "score":      100,
                }
            continue

        # ── Layer 1b: substring alias match ─────────────────────────────────
        # Catches 'Google Chrome' matching alias 'Google' via containment
        alias_hit = None
        for alias_lower, canonical in exact_map.items():
            if alias_lower in company_lower or company_lower in alias_lower:
                alias_hit = (canonical, alias_lower)
                break

        if alias_hit:
            canonical, alias_lower = alias_hit
            if canonical not in matched:
                matched[canonical] = {
                    "vendor":     canonical,
                    "matched_on": company_clean,
                    "method":     "alias",
                    "score":      100,
                }
            continue

        # ── Layer 2: fuzzy match against canonical names ─────────────────────
        result = process.extractOne(
            company_clean,
            canonical_names,
            scorer=fuzz.token_sort_ratio,   # handles word-order variation
        )

        if result:
            best_match, score, _ = result
            if score >= FUZZY_THRESHOLD:
                if best_match not in matched:
                    matched[best_match] = {
                        "vendor":     best_match,
                        "matched_on": company_clean,
                        "method":     "fuzzy",
                        "score":      round(score, 1),
                    }

    return list(matched.values())


def format_match_log(matches: list[dict]) -> str:
    """Returns a readable log string for terminal output."""
    if not matches:
        return "  No vendor matches."
    lines = []
    for m in matches:
        method = m["method"].upper()
        score  = f"{m['score']}%" if m["method"] == "fuzzy" else "exact"
        lines.append(f"  → {m['vendor']} (matched '{m['matched_on']}' · {method} · {score})")
    return "\n".join(lines)