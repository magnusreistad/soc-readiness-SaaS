"""
Pipeline smoke test — scripts/test_pipeline.py

Tests the keyword filter and unified classifier in isolation.
Run from the project root:

    python scripts/test_pipeline.py
"""

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Cache debug logging removed — ai_cache replaced by secure_ai_cache

from app.utils.keyword_filter import passes_keyword_filter
from app.ai.incident_classifier import classify_and_extract

# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

KEYWORD_CASES = [
    (
        "Okta suffers credential breach affecting 1000 customers",
        "",
        True,
        "clear incident — should PASS",
    ),
    (
        "Top 10 tips for better password hygiene",
        "",
        False,
        "advisory content — should FAIL",
    ),
    (
        "Microsoft patches critical vulnerability in Exchange",
        "",
        True,
        "edge case: patch news containing 'vulnerability' — should PASS",
    ),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _label(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _check(condition: bool, description: str) -> bool:
    status = _label(condition)
    print(f"  [{status}] {description}")
    return condition

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Ensure the DB schema (including ai_response_cache) is up to date

    results: list[bool] = []

    # ── 1. Keyword filter ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("1. Keyword filter")
    print("=" * 60)

    titles_for_classifier: list[tuple[str, str]] = []

    for title, summary, expected, note in KEYWORD_CASES:
        actual = passes_keyword_filter(title, summary)
        ok     = actual == expected
        results.append(ok)
        _check(ok, f"{note}")
        print(f"       title:    {title!r}")
        print(f"       expected: {expected}  got: {actual}")
        if actual:
            titles_for_classifier.append((title, summary))

    # ── 2. Classifier — first call (expect MISS → API call) ──────────────────
    print("\n" + "=" * 60)
    print("2. classify_and_extract  (first call — expect cache MISS)")
    print("=" * 60)

    classifier_outputs: list[dict] = []

    for title, summary in titles_for_classifier:
        print(f"\n  Title: {title!r}")
        result = classify_and_extract(title, summary)
        classifier_outputs.append(result)
        print(f"  Result: {result}")

        has_keys = (
            "is_incident" in result
            and "companies"  in result
            and "reason"     in result
        )
        results.append(_check(has_keys, "result has all three expected keys"))
        results.append(_check(
            isinstance(result["is_incident"], bool),
            "is_incident is bool"
        ))
        results.append(_check(
            isinstance(result["companies"], list),
            "companies is list"
        ))

    # ── 3. Cache verification — second call (expect HIT) ────────────────────
    print("\n" + "=" * 60)
    print("3. Cache check  (second call — expect cache HIT, no API call)")
    print("=" * 60)

    for (title, summary), first_result in zip(titles_for_classifier, classifier_outputs):
        print(f"\n  Title: {title!r}")
        second_result = classify_and_extract(title, summary)
        matches = second_result == first_result
        results.append(_check(matches, "cached result matches first call"))

    # ── Summary ──────────────────────────────────────────────────────────────
    passed = sum(results)
    total  = len(results)
    print("\n" + "=" * 60)
    print(f"Summary: {passed}/{total} checks passed")
    if passed == total:
        print("All checks passed.")
    else:
        print(f"{total - passed} check(s) FAILED.")
    print("=" * 60 + "\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
