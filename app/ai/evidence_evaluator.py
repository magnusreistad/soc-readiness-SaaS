"""
app/ai/evidence_evaluator.py

AI-powered evidence evaluator for SOC 2 compliance.

Evaluates uploaded evidence in the context of:
    1. A specific internal control (title, description, type)
    2. A TSC criterion (code, description, AICPA testing attributes)
    3. An audit phase (walkthrough / testing_population / testing_ipe / testing_sample)

The phase distinction is critical:
    - Walkthrough evidence must prove the control EXISTS and is SUITABLY DESIGNED.
      The auditor question is: "Would this control prevent or detect a failure if it
      operated as described?" Design effectiveness — point in time.

    - Testing (population) evidence must prove the COMPLETE POPULATION of items the
      control operated on during the test period. The auditor question is:
      "Show me everything this control should have touched — all of it, for the
      full period."

    - Testing (IPE) evidence must prove the POPULATION ITSELF IS RELIABLE.
      IPE = Information Produced by the Entity. The auditor question is:
      "You produced this export — how do I know it's accurate and complete?"
      This is a separate, distinct audit step that most GRC tools ignore.

    - Testing (sample) evidence must prove the control OPERATED FOR A SPECIFIC ITEM
      selected from the population. The auditor question is: "Show me that this
      control fired for THIS transaction / user / event — contemporaneous evidence only."

Security guarantees (unchanged from prior version):
    - Evidence text is NEVER cached (enforced by secure_ai_cache design)
    - PII is stripped before the content reaches OpenAI
    - Content is wrapped in untrusted-data delimiters
    - Raw file bytes are never passed to this module — caller extracts text first
    - Caller is responsible for storing EvaluationResult.to_dict() to the DB
      (changed from prior version: results CAN now be stored, because they are
       attached to a control row rather than returned and discarded)
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Literal, Optional

from dotenv import load_dotenv
from openai import OpenAI

from app.utils.pii_scrubber import scrub
from app.utils.prompt_guard import sanitize, wrap_for_prompt
from app.utils.soc_mapper import SOC2_CRITERIA_FULL, SOC_LABELS

load_dotenv()
logger = logging.getLogger(__name__)

_MODEL  = 'gpt-4.1'
_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# ---------------------------------------------------------------------------
# Phase type alias
# ---------------------------------------------------------------------------

Phase = Literal[
    'walkthrough',
    'testing_population',
    'testing_ipe',
    'testing_sample',
]

VALID_PHASES: set[str] = {
    'walkthrough',
    'testing_population',
    'testing_ipe',
    'testing_sample',
}

PHASE_LABELS = {
    'walkthrough':          'Walkthrough — Design Effectiveness',
    'testing_population':   'Testing — Population Evidence',
    'testing_ipe':          'Testing — IPE Validation',
    'testing_sample':       'Testing — Sample Evidence',
}


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class EvaluationResult:
    # ── Universal fields ──────────────────────────────────────────────────

    # Pre-clearance verdict (replaces old SATISFIES / PARTIALLY / DOES_NOT_SATISFY)
    verdict: Literal['ready_to_submit', 'needs_work', 'do_not_submit']

    # One-signal risk assessment — this is the top-line answer GRC teams need
    rejection_risk: Literal['low', 'medium', 'high']
    rejection_risk_reason: str      # One sentence: WHY is this risky?

    # Phase and context
    phase: str                      # One of VALID_PHASES
    control_title: str              # The control this was evaluated against
    criteria_code: str
    criteria_description: str

    # Detailed attribute breakdown
    # satisfied_attributes: written as named AICPA attributes that are met
    # gap_attributes: written as challenges the auditor would raise — not abstract
    satisfied_attributes: list[str] = field(default_factory=list)
    gap_attributes: list[str]       = field(default_factory=list)

    # The most important output: concrete, numbered instructions
    # Max 3 items. Written as instructions, not observations or recommendations.
    # BAD: "Consider adding a timestamp"
    # GOOD: "Add a screenshot of the MFA config panel with system name and date
    #        visible in the browser title bar or URL."
    what_to_fix: list[str]          = field(default_factory=list)

    # Quality and auditor reasoning
    evidence_quality: Literal['strong', 'adequate', 'weak', 'insufficient'] = 'insufficient'
    auditor_notes: str = ''         # Written as a senior auditor briefing their team

    # ── Phase-specific fields ─────────────────────────────────────────────

    # Walkthrough
    design_verdict: Optional[str] = None
    # 'Suitably designed' | 'Not suitably designed' | 'Inconclusive'

    # Testing — Population
    period_coverage: Optional[str] = None
    # 'Full period covered' | 'Partial — <detail>' | 'Not evidenced'
    record_count_visible: Optional[bool] = None
    source_system_identified: Optional[bool] = None
    filter_criteria_documented: Optional[bool] = None
    # Were the query/report parameters used to generate the export visible?

    # Testing — IPE
    ipe_reliability: Optional[str] = None
    # 'Reliable — independent reconciliation present'
    # 'Questionable — entity-prepared, limited corroboration'
    # 'Unreliable — manually prepared spreadsheet, no system provenance'
    reconciliation_present: Optional[bool] = None
    report_parameters_visible: Optional[bool] = None

    # Testing — Sample
    sample_reference: Optional[str] = None     # Which population item this covers
    is_contemporaneous: Optional[bool] = None  # Was evidence created when control ran?
    exception_noted: Optional[bool] = None
    exception_detail: Optional[str] = None

    # ── Security / meta ───────────────────────────────────────────────────
    pii_redacted: bool = False
    injection_detected: bool = False
    was_truncated: bool = False

    def to_dict(self) -> dict:
        """Serialise to dict for JSONB storage in evidence_files.evaluation."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Safe default — returned on any unrecoverable error
# ---------------------------------------------------------------------------

def _safe_default(
    phase: str,
    control_title: str,
    criteria_code: str,
    criteria_description: str,
    pii_redacted: bool = False,
    injection_detected: bool = False,
    was_truncated: bool = False,
) -> EvaluationResult:
    return EvaluationResult(
        verdict='do_not_submit',
        rejection_risk='high',
        rejection_risk_reason=(
            'Evaluation could not be completed. '
            'Re-upload the document or contact support.'
        ),
        phase=phase,
        control_title=control_title,
        criteria_code=criteria_code,
        criteria_description=criteria_description,
        satisfied_attributes=[],
        gap_attributes=['Evaluation failed — no attributes could be assessed.'],
        what_to_fix=['Re-upload the document and try again.'],
        evidence_quality='insufficient',
        auditor_notes=(
            'The AI evaluator encountered an error processing this document. '
            'Manual review required.'
        ),
        pii_redacted=pii_redacted,
        injection_detected=injection_detected,
        was_truncated=was_truncated,
    )


# ---------------------------------------------------------------------------
# Phase-specific system prompts
# ---------------------------------------------------------------------------

_COMMON_PREAMBLE = f"""
You are a senior SOC 2 auditor at a Big 4 public accounting firm.
You are conducting an independent service auditor examination under AT-C Section 205.
You have reviewed hundreds of SOC 2 engagements and know exactly what evidence
passes fieldwork and what gets flagged.

Your reference framework is the AICPA 2017 Trust Services Criteria:
{SOC2_CRITERIA_FULL}

OUTPUT RULES — follow these exactly:
- verdict must be one of: ready_to_submit, needs_work, do_not_submit
- rejection_risk must be one of: low, medium, high
- rejection_risk_reason: one sentence explaining the primary risk
- gap_attributes: write each gap as an auditor challenge — the exact question
  or comment the auditor would raise. Never abstract.
  BAD:  "Missing period evidence"
  GOOD: "No evidence this control operated between Jan–Dec 2024. Auditor will
         request a log extract or approval record showing at least one execution
         per [expected cadence] across the full period."
- what_to_fix: maximum 3 items, written as direct instructions to the preparer.
  BAD:  "Consider adding a timestamp."
  GOOD: "Add a screenshot of the MFA configuration panel with the system name
         and current date visible in the browser title bar or URL."
- auditor_notes: write as if briefing your audit junior — direct, skeptical,
  specific. Say what you actually saw and what it does or doesn't prove.
- Never hallucinate content. Only assess what is actually present in the evidence.
- If PII tokens like [EMAIL] or [PERSON] appear, note they were redacted but do
  not let this affect your substantive assessment.
- Return ONLY valid JSON — no markdown fences, no prose outside the object.
"""

_WALKTHROUGH_PROMPT = _COMMON_PREAMBLE + """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE: WALKTHROUGH — DESIGN EFFECTIVENESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your objective is to determine whether this evidence demonstrates that the
control EXISTS and is SUITABLY DESIGNED to achieve its stated objective.

Ask yourself:
  1. Does this evidence confirm the control is actually in place?
  2. Is there documentation showing how the control is designed to operate
     (a policy, procedure, system configuration, or process description)?
  3. Does the control, as described and designed, address the TSC criterion?
  4. If this control operated exactly as designed, would it prevent or detect
     a failure relevant to the criterion?
  5. Is the design documented to a level where another person could perform
     the control without additional guidance?

You are NOT assessing operating effectiveness or whether the control ran
over a period. Design only — a single point-in-time review.

Watch for these common walkthrough deficiencies:
  - Policy exists but doesn't mention the specific system or scope
  - Configuration screenshot exists but no evidence management approved it
  - The control description is so vague it is not testable
  - The documented procedure does not logically achieve the criterion's objective
  - No evidence of the date the design was established or last reviewed

Return this JSON object:
{
  "verdict": "ready_to_submit" | "needs_work" | "do_not_submit",
  "rejection_risk": "low" | "medium" | "high",
  "rejection_risk_reason": "<one sentence>",
  "satisfied_attributes": ["<attribute name: what the evidence proves>"],
  "gap_attributes": ["<auditor challenge, written as the exact comment they would raise>"],
  "what_to_fix": ["<instruction 1>", "<instruction 2>"],
  "evidence_quality": "strong" | "adequate" | "weak" | "insufficient",
  "auditor_notes": "<senior auditor briefing tone>",
  "design_verdict": "Suitably designed" | "Not suitably designed" | "Inconclusive"
}
"""

_POPULATION_PROMPT = _COMMON_PREAMBLE + """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE: TESTING — POPULATION EVIDENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your objective is to determine whether this evidence establishes a COMPLETE,
CREDIBLE POPULATION of items the control should have operated on during the
test period.

The population is the universe of items the auditor will sample from.
If the population is incomplete or unreliable, the entire testing phase
is compromised — you cannot sample from a flawed population.

Ask yourself:
  1. Does the export or report cover the FULL test period (not just a subset)?
     Look for date ranges, period headers, or export timestamps.
  2. Is the source system clearly identified? (System name, URL, or report title)
  3. Are record counts visible? Can we see how many items are in the population?
  4. Are the filter criteria documented? We need to know what was included
     and what was excluded — otherwise completeness cannot be assessed.
  5. Does the format look like a genuine system export vs. a manually prepared list?
  6. Are there any obvious gaps — e.g. missing months in a 12-month period?

Watch for these common population deficiencies:
  - Export covers only part of the period (e.g. 6 of 12 months)
  - Source system is unnamed — auditor cannot validate completeness
  - No record count — cannot determine population size for sampling
  - Filter/query parameters not shown — cannot confirm completeness
  - Manually prepared spreadsheet with no system header or export metadata
  - Date column shows a narrow date range inconsistent with the stated period

Return this JSON object:
{
  "verdict": "ready_to_submit" | "needs_work" | "do_not_submit",
  "rejection_risk": "low" | "medium" | "high",
  "rejection_risk_reason": "<one sentence>",
  "satisfied_attributes": ["<attribute: what this population evidence proves>"],
  "gap_attributes": ["<auditor challenge>"],
  "what_to_fix": ["<instruction 1>", "<instruction 2>"],
  "evidence_quality": "strong" | "adequate" | "weak" | "insufficient",
  "auditor_notes": "<senior auditor briefing tone>",
  "period_coverage": "Full period covered" | "Partial — <detail of what is missing>" | "Not evidenced",
  "record_count_visible": true | false,
  "source_system_identified": true | false,
  "filter_criteria_documented": true | false
}
"""

_IPE_PROMPT = _COMMON_PREAMBLE + """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE: TESTING — IPE VALIDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IPE = Information Produced by the Entity.

Your objective is to determine whether this evidence gives sufficient assurance
that the population export is ACCURATE AND COMPLETE.

The entity produced the population export themselves — the auditor cannot
accept it at face value. Before sampling, the auditor needs independent
corroboration that the report or export was not incomplete, filtered, or
manipulated, whether intentionally or by error.

Ask yourself:
  1. Is there a reconciliation to an independent source?
     (e.g. total record count ties to a system parameter, a second report,
      or a screenshot of the system showing total record count)
  2. Are the report parameters or query criteria visible?
     (e.g. a screenshot showing date range, filters, and record count before
      the export was generated)
  3. Is there IT administrator confirmation of the report's completeness?
  4. Does the data format show system metadata (headers, export timestamps,
     system name) that is consistent with a live export rather than a
     manually assembled file?
  5. Could a reasonable auditor conclude that the population is reliable
     based on this IPE evidence alone?

Watch for these common IPE deficiencies:
  - No reconciliation to any independent source
  - Excel file with no system headers or export metadata
  - Record count in population export doesn't match record count in IPE evidence
  - IPE evidence is just a second copy of the same report — not independent
  - Report parameters screenshot is cropped or doesn't show the date range

IMPORTANT — reliability tiers:
  "Reliable"      : Independent reconciliation present OR report parameters
                    screenshotted from system with record count visible
  "Questionable"  : Entity-prepared with some corroboration but gaps remain
  "Unreliable"    : Manually prepared spreadsheet, no system provenance,
                    no reconciliation, or reconciliation doesn't close

Return this JSON object:
{
  "verdict": "ready_to_submit" | "needs_work" | "do_not_submit",
  "rejection_risk": "low" | "medium" | "high",
  "rejection_risk_reason": "<one sentence>",
  "satisfied_attributes": ["<attribute: what this IPE evidence proves>"],
  "gap_attributes": ["<auditor challenge>"],
  "what_to_fix": ["<instruction 1>", "<instruction 2>"],
  "evidence_quality": "strong" | "adequate" | "weak" | "insufficient",
  "auditor_notes": "<senior auditor briefing tone>",
  "ipe_reliability": "Reliable — independent reconciliation present" | "Questionable — entity-prepared, limited corroboration" | "Unreliable — manually prepared spreadsheet, no system provenance",
  "reconciliation_present": true | false,
  "report_parameters_visible": true | false
}
"""

_SAMPLE_PROMPT = _COMMON_PREAMBLE + """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE: TESTING — SAMPLE EVIDENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your objective is to determine whether this evidence proves that the control
OPERATED EFFECTIVELY FOR THIS SPECIFIC SAMPLE ITEM.

The auditor selected this item from the population. The entity must now show
that the control fired correctly for this exact transaction, user, event,
or record.

Ask yourself:
  1. Does the evidence clearly identify the specific sample item being tested?
     (e.g. the username, ticket number, invoice number, or change request ID
      that was selected from the population)
  2. Is the evidence CONTEMPORANEOUS — was it created at the time the control
     ran, not staged after the fact for audit purposes?
     (Approval emails, system-generated logs, and timestamped records are
      contemporaneous. Screenshots taken specifically for the audit are not.)
  3. Does the evidence show the CONTROL OUTPUT — what the control actually did?
     (An approval, a log entry, a configuration state, a signed document)
  4. Does the control output match what was described in the walkthrough?
     (If the walkthrough said "manager approval via Jira", the sample should
      show a Jira ticket with manager approval — not a Slack message)
  5. Is there an exception? If so, is there evidence it was identified and
     resolved in a timely manner?
  6. Is the date on the evidence within the test period?

Watch for these common sample deficiencies:
  - Evidence does not name or reference the specific sample item
  - Evidence is a screenshot taken specifically for the audit (not contemporaneous)
  - Date on the evidence is outside the test period
  - Control output shown doesn't match the control description from walkthrough
  - Evidence shows a different user or system than expected
  - Exception is present but no resolution evidence provided

Return this JSON object:
{
  "verdict": "ready_to_submit" | "needs_work" | "do_not_submit",
  "rejection_risk": "low" | "medium" | "high",
  "rejection_risk_reason": "<one sentence>",
  "satisfied_attributes": ["<attribute: what this sample evidence proves>"],
  "gap_attributes": ["<auditor challenge — specific to this sample item>"],
  "what_to_fix": ["<instruction 1>", "<instruction 2>"],
  "evidence_quality": "strong" | "adequate" | "weak" | "insufficient",
  "auditor_notes": "<senior auditor briefing tone>",
  "is_contemporaneous": true | false,
  "exception_noted": true | false,
  "exception_detail": "<describe the exception if present, else null>"
}
"""

_PHASE_PROMPTS: dict[str, str] = {
    'walkthrough':          _WALKTHROUGH_PROMPT,
    'testing_population':   _POPULATION_PROMPT,
    'testing_ipe':          _IPE_PROMPT,
    'testing_sample':       _SAMPLE_PROMPT,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def evaluate_evidence(
    raw_text: str,
    criteria_code: str,
    phase: str,
    control_title: str,
    control_description: str,
    control_type: str,
    file_type: str,
    was_truncated: bool = False,
    sample_reference: Optional[str] = None,
    population_context: Optional[str] = None,
) -> EvaluationResult:
    """
    Evaluates extracted document text against a TSC criterion and control,
    with phase-specific logic for walkthrough vs. the three testing phases.

    Args:
        raw_text:             Text extracted from the uploaded document.
                              For images, this is a base64 string.
        criteria_code:        TSC criterion code e.g. 'CC6.1'
        phase:                One of VALID_PHASES
        control_title:        Title of the control this evidence is attached to
        control_description:  Full description of the control
        control_type:         'automated' | 'manual' | 'it_dependent_manual'
        file_type:            One of: pdf, image, excel, word, csv, text
        was_truncated:        Whether the document was truncated due to length
        sample_reference:     For testing_sample only — which population item
                              this evidence covers (e.g. "User: john@acme.com")

    Returns:
        EvaluationResult — never raises. Returns safe default on any error.

    NOTE ON STORAGE:
        Unlike the prior version, the caller IS expected to store
        EvaluationResult.to_dict() into evidence_files.evaluation (JSONB).
        Evidence evaluations are now persistent and attached to a control row.
        They must still never be cached via secure_ai_cache.
    """

    # ── Validate phase ──────────────────────────────────────────────────────
    if phase not in VALID_PHASES:
        logger.error('Invalid phase: %s', phase)
        return _safe_default(
            phase=phase,
            control_title=control_title,
            criteria_code=criteria_code,
            criteria_description=f'Invalid phase: {phase}',
        )

    criteria_description = SOC_LABELS.get(
        criteria_code,
        f'Unknown criterion: {criteria_code}'
    )

    # ── Step 1: Strip PII ───────────────────────────────────────────────────
    scrubbed_text, redactions = scrub(raw_text)
    pii_redacted = len(redactions) > 0

    # ── Step 2: Prompt injection guard ─────────────────────────────────────
    guard = sanitize(scrubbed_text)
    injection_detected = guard.is_high_risk

    if guard.is_high_risk:
        logger.warning(
            'High-risk prompt injection detected in evidence upload. '
            'Phase: %s | Control: %s | Triggers: %s',
            phase, control_title, guard.triggers,
        )

    safe_text = guard.sanitized_text

    # ── Step 3: Build user message ──────────────────────────────────────────
    wrapped = wrap_for_prompt(safe_text, label='EVIDENCE DOCUMENT')

    control_type_label = {
        'automated':           'Automated',
        'manual':              'Manual',
        'it_dependent_manual': 'IT-Dependent Manual',
    }.get(control_type, control_type)

    sample_note = (
        f'\nSAMPLE ITEM BEING TESTED: {sample_reference}'
        if phase == 'testing_sample' and sample_reference
        else ''
    )

    truncation_note = (
        '\n\nNOTE: This document was truncated due to length. '
        'Your assessment should explicitly note that only partial content was reviewed.'
        if was_truncated else ''
    )

    injection_note = (
        '\n\nSECURITY NOTE: This document contained suspicious content that '
        'was redacted by the security filter. Assess only the remaining content.'
        if injection_detected else ''
    )

    user_message = (
        f'CONTROL BEING EVALUATED:\n'
        f'  Title:       {control_title}\n'
        f'  Description: {control_description}\n'
        f'  Type:        {control_type_label}\n'
        f'\n'
        f'TSC CRITERION:\n'
        f'  Code:        {criteria_code}\n'
        f'  Description: {criteria_description}\n'
        f'\n'
        f'AUDIT PHASE: {PHASE_LABELS.get(phase, phase)}'
        f'{sample_note}'
        f'\n'
        f'DOCUMENT TYPE: {file_type}'
        f'{truncation_note}'
        f'{injection_note}'
        f'\n\n'
        f'{wrapped}'
    )

    # ── Step 4: Select system prompt for this phase ─────────────────────────
    system_prompt = _PHASE_PROMPTS[phase]

    # ── Step 5: Call AI ─────────────────────────────────────────────────────
    try:
        if file_type == 'image':
            raw_result = _evaluate_image(
                base64_data=raw_text,
                user_context=user_message,
                system_prompt=system_prompt,
            )
        else:
            raw_result = _evaluate_text(
                user_message=user_message,
                system_prompt=system_prompt,
            )
    except Exception as exc:
        logger.error(
            'Evidence evaluation AI call failed. Phase: %s | Control: %s | Error: %s',
            phase, control_title, exc,
        )
        return _safe_default(
            phase=phase,
            control_title=control_title,
            criteria_code=criteria_code,
            criteria_description=criteria_description,
            pii_redacted=pii_redacted,
            injection_detected=injection_detected,
            was_truncated=was_truncated,
        )

    # ── Step 6: Build typed result from raw dict ────────────────────────────
    return _build_result(
        raw=raw_result,
        phase=phase,
        control_title=control_title,
        criteria_code=criteria_code,
        criteria_description=criteria_description,
        sample_reference=sample_reference,
        pii_redacted=pii_redacted,
        injection_detected=injection_detected,
        was_truncated=was_truncated,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _evaluate_text(user_message: str, system_prompt: str) -> dict:
    response = _client.chat.completions.create(
        model=_MODEL,
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': user_message},
        ],
        temperature=0,
        max_tokens=1200,    # slightly higher — more structured output fields
    )
    raw = response.choices[0].message.content or ''
    return _parse_response(raw)


def _evaluate_image(
    base64_data: str,
    user_context: str,
    system_prompt: str,
) -> dict:
    """Evaluates an image using GPT-4 vision with phase-aware system prompt."""
    if base64_data.startswith('/9j/'):
        media_type = 'image/jpeg'
    elif base64_data.startswith('iVBOR'):
        media_type = 'image/png'
    else:
        media_type = 'image/png'

    response = _client.chat.completions.create(
        model=_MODEL,
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': [
                {
                    'type': 'text',
                    'text': (
                        f'{user_context}\n\n'
                        'NOTE: This is a screenshot or image. Assess only what '
                        'is visibly present. For walkthrough phase, screenshots '
                        'of system configuration are valid point-in-time evidence. '
                        'For testing phases, note the inherent limitations of '
                        'point-in-time screenshots as operating effectiveness evidence.'
                    ),
                },
                {
                    'type': 'image_url',
                    'image_url': {
                        'url': f'data:{media_type};base64,{base64_data}',
                        'detail': 'high',
                    },
                },
            ]},
        ],
        temperature=0,
        max_tokens=1200,
    )
    raw = response.choices[0].message.content or ''
    return _parse_response(raw)


def _parse_response(raw: str) -> dict:
    """Strip markdown fences and parse JSON. Returns empty dict on failure."""
    cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.DOTALL)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error('Failed to parse AI response: %s\nRaw: %s', exc, raw[:300])
        return {}


def _build_result(
    raw: dict,
    phase: str,
    control_title: str,
    criteria_code: str,
    criteria_description: str,
    sample_reference: Optional[str],
    pii_redacted: bool,
    injection_detected: bool,
    was_truncated: bool,
) -> EvaluationResult:
    """
    Constructs a typed EvaluationResult from the raw AI response dict.
    Falls back gracefully on any missing or malformed field.
    """
    # Universal fields
    verdict = raw.get('verdict', 'do_not_submit')
    if verdict not in ('ready_to_submit', 'needs_work', 'do_not_submit'):
        verdict = 'do_not_submit'

    rejection_risk = raw.get('rejection_risk', 'high')
    if rejection_risk not in ('low', 'medium', 'high'):
        rejection_risk = 'high'

    evidence_quality = raw.get('evidence_quality', 'insufficient')
    if evidence_quality not in ('strong', 'adequate', 'weak', 'insufficient'):
        evidence_quality = 'insufficient'

    result = EvaluationResult(
        verdict=verdict,
        rejection_risk=rejection_risk,
        rejection_risk_reason=raw.get('rejection_risk_reason', ''),
        phase=phase,
        control_title=control_title,
        criteria_code=criteria_code,
        criteria_description=criteria_description,
        satisfied_attributes=raw.get('satisfied_attributes', []),
        gap_attributes=raw.get('gap_attributes', []),
        what_to_fix=raw.get('what_to_fix', [])[:3],    # enforce max 3
        evidence_quality=evidence_quality,
        auditor_notes=raw.get('auditor_notes', ''),
        pii_redacted=pii_redacted,
        injection_detected=injection_detected,
        was_truncated=was_truncated,
    )

    # Phase-specific fields
    if phase == 'walkthrough':
        result.design_verdict = raw.get('design_verdict')

    elif phase == 'testing_population':
        result.period_coverage             = raw.get('period_coverage')
        result.record_count_visible        = raw.get('record_count_visible')
        result.source_system_identified    = raw.get('source_system_identified')
        result.filter_criteria_documented  = raw.get('filter_criteria_documented')

    elif phase == 'testing_ipe':
        result.ipe_reliability             = raw.get('ipe_reliability')
        result.reconciliation_present      = raw.get('reconciliation_present')
        result.report_parameters_visible   = raw.get('report_parameters_visible')

    elif phase == 'testing_sample':
        result.sample_reference    = sample_reference
        result.is_contemporaneous  = raw.get('is_contemporaneous')
        result.exception_noted     = raw.get('exception_noted')
        result.exception_detail    = raw.get('exception_detail')

    return result