import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Import shared SOC mapping
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from app.utils.soc_mapper import (
    SOC2_CRITERIA_FULL,
    INCIDENT_SOC_MAP,
    get_criteria_for_incident_type,
    criteria_as_json,
)

# ---------------------------------------------------------------------------
# Incident type taxonomy
# ---------------------------------------------------------------------------

INCIDENT_TYPES = list(INCIDENT_SOC_MAP.keys())


def score_incident(title: str, summary: str) -> dict:
    """
    Given an article title and summary, returns a dict with:
        severity      : 'critical' | 'high' | 'medium' | 'low'
        incident_type : one of INCIDENT_TYPES
        ai_reason     : one-sentence explanation
        soc_criteria  : JSON string list of SOC 2 criteria codes

    The SOC criteria are derived from the incident type using the shared
    soc_mapper module — not left to GPT to invent freely — ensuring
    consistent, audit-grounded mappings across all incidents.
    """

    # Build a summary of the incident-type→criteria mapping for the prompt
    # so GPT understands the framework it's working within
    mapping_summary = "\n".join(
        f"  {itype}: {', '.join(data['criteria'][:4])}{'...' if len(data['criteria']) > 4 else ''}"
        f" [{', '.join(data['trust_categories'])}]"
        for itype, data in INCIDENT_SOC_MAP.items()
        if itype != "other"
    )

    prompt = f"""
You are a cybersecurity analyst specializing in SOC 2 audits.

The AICPA frames cyber threats as risks to service commitments — not isolated IT problems.
A cyber event threatening or causing failure to meet a commitment directly impacts SOC 2 criteria.

Analyze this cybersecurity incident and return a JSON object with exactly these four fields:

1. "severity" — one of: critical, high, medium, low
   Scoring guide:
   - critical : confirmed breach with data exfiltration, ransomware encrypting production,
                nation-state attack, or incident affecting >100k records
   - high     : confirmed unauthorized access, active exploitation of a CVE,
                credential compromise with evidence of misuse
   - medium   : unconfirmed breach, vulnerability disclosed but not yet exploited,
                phishing campaign detected
   - low      : minor misconfiguration, low-impact vulnerability, no evidence of exploitation

2. "incident_type" — one of: {", ".join(INCIDENT_TYPES)}
   Choose the type that best describes the PRIMARY nature of this incident.

3. "ai_reason" — one sentence (max 20 words) explaining your severity rating

4. "soc_criteria" — return ONLY the criteria codes from this incident-type mapping:
{mapping_summary}

   Use the codes for the incident_type you identified above.
   Do NOT invent criteria outside these mappings.
   Return only the codes (e.g. "CC6.1"), not descriptions.

Article title: {title}
Article summary: {summary}

Return ONLY valid JSON. No preamble, no markdown.

Example:
{{
  "severity": "high",
  "incident_type": "data breach",
  "ai_reason": "Confirmed unauthorized access to production database with customer PII exposed.",
  "soc_criteria": ["CC3.2", "CC6.1", "CC6.6", "CC7.2", "CC7.3", "CC7.4", "CC9.2"]
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )

        raw     = response.choices[0].message.content
        cleaned = re.sub(r"```json|```", "", raw).strip()
        result  = json.loads(cleaned)

        # Validate severity
        severity = result.get("severity", "unknown").lower()
        if severity not in ("critical", "high", "medium", "low"):
            severity = "unknown"

        # Validate incident type
        incident_type = result.get("incident_type", "other").lower()
        if incident_type not in INCIDENT_TYPES:
            incident_type = "other"

        ai_reason = str(result.get("ai_reason", "")).strip()

        # Use GPT's criteria list but validate each code against our known map
        # If GPT returns something unexpected, fall back to the canonical mapping
        raw_criteria = result.get("soc_criteria", [])
        canonical    = get_criteria_for_incident_type(incident_type)

        if isinstance(raw_criteria, list) and len(raw_criteria) > 0:
            # Accept GPT's list if it looks valid (all codes match known pattern)
            valid = [
                c for c in raw_criteria
                if isinstance(c, str) and re.match(r"^[A-Z]{1,3}\d+\.\d+$", c)
            ]
            soc_criteria = valid if valid else canonical
        else:
            soc_criteria = canonical

        return {
            "severity":      severity,
            "incident_type": incident_type,
            "ai_reason":     ai_reason,
            "soc_criteria":  json.dumps(soc_criteria),
        }

    except Exception as e:
        print(f"  [scorer] GPT scoring failed: {e}")
        return _safe_defaults()


def _safe_defaults() -> dict:
    return {
        "severity":      "unknown",
        "incident_type": "other",
        "ai_reason":     "",
        "soc_criteria":  criteria_as_json("other"),
    }