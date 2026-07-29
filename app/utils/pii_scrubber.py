"""
app/utils/pii_scrubber.py

Strips PII from document text before it is sent to any external AI API.
Replaces identified entities with neutral placeholders so the AI can still
reason about structure and content without receiving personal data.

Patterns removed:
    - Email addresses
    - Phone numbers (US + international)
    - Social Security Numbers
    - Credit card numbers
    - IPv4 addresses
    - Names preceded by common title patterns (Mr, Ms, Dr, etc.)
    - Street addresses (basic heuristic)
    - Dates of birth patterns
"""

import re

# ---------------------------------------------------------------------------
# Replacement tokens — descriptive so the AI still understands context
# ---------------------------------------------------------------------------
_REPLACEMENTS: list[tuple[re.Pattern, str]] = [
    # Email addresses
    (re.compile(
        r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b',
        re.IGNORECASE
    ), '[EMAIL]'),

    # US phone numbers: (555) 123-4567 / 555-123-4567 / +1-555-123-4567
    (re.compile(
        r'(\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b'
    ), '[PHONE]'),

    # Social Security Numbers: 123-45-6789 / 123 45 6789
    (re.compile(
        r'\b\d{3}[\s\-]\d{2}[\s\-]\d{4}\b'
    ), '[SSN]'),

    # Credit card numbers (13-19 digits, optionally spaced or dashed)
    (re.compile(
        r'\b(?:\d[ \-]?){13,19}\b'
    ), '[CARD]'),

    # IPv4 addresses
    (re.compile(
        r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    ), '[IP_ADDRESS]'),

    # Titled names: Mr. John Smith / Dr. Jane Doe / Ms. Alice Brown
    (re.compile(
        r'\b(Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',
        re.IGNORECASE
    ), '[PERSON]'),

    # Street addresses: 123 Main Street / 456 Oak Ave Apt 7
    (re.compile(
        r'\b\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+'
        r'(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|'
        r'Court|Ct|Place|Pl|Way|Circle|Cir)\.?\b',
        re.IGNORECASE
    ), '[ADDRESS]'),

    # Date of birth patterns: DOB: 01/15/1985 / Born: January 15, 1985
    (re.compile(
        r'(DOB|Date of Birth|Born)[:\s]+\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}',
        re.IGNORECASE
    ), '[DOB]'),

    (re.compile(
        r'(DOB|Date of Birth|Born)[:\s]+'
        r'(January|February|March|April|May|June|July|August|September|'
        r'October|November|December)\s+\d{1,2},?\s+\d{4}',
        re.IGNORECASE
    ), '[DOB]'),
]

# Maximum characters to process — prevents abuse via enormous documents
_MAX_CHARS = 50_000


def scrub(text: str) -> tuple[str, list[str]]:
    """
    Removes PII from text and returns (scrubbed_text, list_of_redaction_types).

    Args:
        text: Raw extracted document text.

    Returns:
        scrubbed:   Text with PII replaced by placeholder tokens.
        redactions: List of redaction types applied e.g. ['EMAIL', 'PHONE'].
                    Empty list means no PII was found.
    """
    if not text:
        return '', []

    # Truncate to prevent oversized payloads
    text = text[:_MAX_CHARS]

    redacted_types: set[str] = set()
    scrubbed = text

    for pattern, placeholder in _REPLACEMENTS:
        new_text, count = pattern.subn(placeholder, scrubbed)
        if count > 0:
            # Extract the token name from e.g. '[EMAIL]' → 'EMAIL'
            redacted_types.add(placeholder.strip('[]'))
            scrubbed = new_text

    return scrubbed, sorted(redacted_types)


def scrub_dict(data: dict) -> dict:
    """
    Recursively scrubs all string values in a dict.
    Useful for scrubbing structured data before logging or caching.
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key], _ = scrub(value)
        elif isinstance(value, dict):
            result[key] = scrub_dict(value)
        elif isinstance(value, list):
            result[key] = [
                scrub(v)[0] if isinstance(v, str) else v
                for v in value
            ]
        else:
            result[key] = value
    return result