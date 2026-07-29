"""
Unified incident classifier — app/ai/incident_classifier.py

Replaces the two-call pattern (incident_filter.py + vendor_extractor.py) with a
single GPT call that simultaneously determines whether an article describes a real
cybersecurity incident and extracts any company names mentioned.

The SOC2_CRITERIA_FULL string is placed at the very top of the system prompt to
enable OpenAI prompt prefix caching — the static prefix must be long and stable.
"""

import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from app.utils.secure_ai_cache import get_cached, store_cached
from app.utils.soc_mapper import SOC2_CRITERIA_FULL

load_dotenv()

_MODEL = "gpt-4.1-mini"

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

_SYSTEM_PROMPT = SOC2_CRITERIA_FULL + """

---

You are a cybersecurity analyst assistant. For each article you receive, do two things:

1. INCIDENT CLASSIFICATION — decide whether the article describes a real cybersecurity
   incident affecting a company or organisation. A real incident includes events such as:
   data breaches, ransomware attacks, exploited vulnerabilities, credential compromise,
   unauthorised access, malware infections, DDoS attacks, or supply chain attacks.
   It does NOT include: security tips, product announcements, industry commentary,
   research reports, or general threat-landscape summaries.

2. COMPANY EXTRACTION — extract any company or organisation names mentioned in the
   article that are relevant to the incident (victim, attacker infrastructure owner,
   or affected vendor).

Return ONLY valid JSON — no markdown fences, no prose — with exactly these three fields:
{
  "is_incident": true | false,
  "companies":   ["Company A", "Company B"],
  "reason":      "One-sentence explanation of the classification decision."
}
"""

_SAFE_DEFAULT: dict = {
    "is_incident": False,
    "companies":   [],
    "reason":      "parse error",
}


def classify_and_extract(title: str, summary: str) -> dict:
    """
    Determines whether the article describes a real cybersecurity incident and
    extracts company names — using a single GPT call.

    Returns a dict with keys:
        is_incident : bool
        companies   : list[str]
        reason      : str

    Results are cached by content hash. On API or parse failure, returns a safe
    default so callers never have to handle exceptions from this function.
    """
    cached = get_cached(0, 'incident_classification', title + summary[:200])
    if cached is not None:
        return cached

    user_content = f"Article title: {title}\n\nArticle summary: {summary}"

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_content},
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content or ""
    except Exception as exc:
        print(f"  [classifier] API error: {exc}")
        return _SAFE_DEFAULT.copy()

    # Strip markdown code fences if the model wraps the JSON anyway
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.DOTALL)

    try:
        result = json.loads(cleaned)
        # Normalise keys to the expected shape
        out = {
            "is_incident": bool(result.get("is_incident", False)),
            "companies":   list(result.get("companies", [])),
            "reason":      str(result.get("reason", "")),
        }
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"  [classifier] JSON parse error: {exc}\n  Raw response: {raw!r}")
        return _SAFE_DEFAULT.copy()

    store_cached(0, 'incident_classification', title + summary[:200], out)
    return out
