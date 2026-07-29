"""
Keyword filter for vendor threat articles.

passes_keyword_filter() gates articles before expensive AI classification.
If none of the curated cybersecurity keywords appear in the title+summary,
the article is almost certainly noise and can be skipped.

The check is intentionally broad (simple substring, case-insensitive).
False negatives (missing real incidents) are worse than false positives
(sending a borderline article through to AI), so the list errs on the
side of inclusion.
"""

KEYWORDS: list[str] = [
    # Incident categories
    "breach",
    "data breach",
    "data leak",
    "data exposure",
    "ransomware",
    "malware",
    "spyware",
    "adware",
    "trojan",
    "worm",
    "botnet",
    "rootkit",
    "keylogger",
    "backdoor",
    # Attack techniques
    "exploit",
    "exploited",
    "exploitation",
    "zero-day",
    "zeroday",
    "phishing",
    "credential",
    "unauthorized",
    "exfiltration",
    "intrusion",
    "lateral movement",
    "privilege escalation",
    "command and control",
    "supply chain attack",
    "social engineering",
    "ddos",
    "denial of service",
    # Generic threat terms
    "cyberattack",
    "attack",
    "vulnerability",
    "cve",
    "compromised",
    "incident",
    "hacked",
    "hacking",
    "stolen",
    "extortion",
    # Known threat actor / tooling names
    "lockbit",
    "darkside",
    "conti",
    "cobalt strike",
]


def passes_keyword_filter(title: str, summary: str) -> bool:
    """
    Returns True if the combined title+summary contains at least one
    keyword from the curated cybersecurity incident keyword list.

    The check is case-insensitive substring matching. A single space
    is used as a separator so multi-word keywords (e.g. "data breach")
    can match across the boundary between title and summary.
    """
    combined = (title + " " + summary).lower()
    return any(kw in combined for kw in KEYWORDS)


if __name__ == "__main__":
    tests = [
        (
            "Acme Corp suffers data breach exposing 2 million records",
            "",
            True,
        ),
        (
            "Company releases Q3 earnings report ahead of schedule",
            "Revenue grew 12% year-over-year driven by strong product sales.",
            False,
        ),
        (
            "Critical CVE-2024-1234 exploited in the wild against major cloud provider",
            "Attackers are leveraging an unpatched vulnerability to gain unauthorized access.",
            True,
        ),
    ]

    all_passed = True
    for title, summary, expected in tests:
        result = passes_keyword_filter(title, summary)
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"[{status}] expected={expected}, got={result}")
        print(f"       title: {title!r}")

    print()
    print("All tests passed." if all_passed else "Some tests FAILED.")
