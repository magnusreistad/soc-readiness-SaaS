"""
app/utils/control_classification.py

Pure-Python derivation of SOC 2 testing requirements from control_type and frequency.
These rules mirror the SQL backfill in the migration and the TypeScript derivation
in the frontend — keep all three in sync when changing business logic.
"""

from typing import Optional


# ---------------------------------------------------------------------------
# Label dictionaries
# ---------------------------------------------------------------------------

STATUS_LABELS: dict[str, str] = {
    'not_tested':           'Not Tested',
    'exception_noted':      'Exception Noted',
    'cleared':              'Cleared',
    'tested_no_exceptions': 'No Exceptions',
}

FREQUENCY_LABELS: dict[str, str] = {
    'annual':     'Annual',
    'semi_annual': 'Semi-Annual',
    'quarterly':  'Quarterly',
    'monthly':    'Monthly',
    'weekly':     'Weekly',
    'daily':      'Daily',
    'continuous': 'Continuous',
    'adhoc':      'Ad hoc / As needed',
}

_SAMPLE_SIZE: dict[str, int] = {
    'annual':     1,
    'semi_annual': 2,
    'quarterly':  2,
    'monthly':    5,
    'weekly':     15,
    'daily':      25,
    'continuous': 25,
    'adhoc':      25,
}


# ---------------------------------------------------------------------------
# Core derivation
# ---------------------------------------------------------------------------

def derive_testing_requirements(
    control_type: Optional[str],
    frequency: Optional[str],
) -> dict:
    """
    Derives requires_population, requires_sample, and suggested_sample_size
    from control_type and frequency.

    Safe to call with None values — returns all-false/null in that case.

    Returns:
        {
            'requires_population': bool,
            'requires_sample': bool,
            'suggested_sample_size': int | None,
        }
    """
    if not control_type:
        return {
            'requires_population': False,
            'requires_sample': False,
            'suggested_sample_size': None,
        }

    ct = control_type.lower()

    if ct == 'automated':
        return {
            'requires_population': False,
            'requires_sample': False,
            'suggested_sample_size': None,
        }

    if ct == 'manual' and frequency == 'annual':
        return {
            'requires_population': False,
            'requires_sample': False,
            'suggested_sample_size': 1,
        }

    # manual (non-annual) or itdm — all require population + sample
    sample_size = _SAMPLE_SIZE.get(frequency) if frequency else None
    return {
        'requires_population': True,
        'requires_sample': True,
        'suggested_sample_size': sample_size,
    }


# ---------------------------------------------------------------------------
# Human-readable explanation
# ---------------------------------------------------------------------------

def explain_testing_approach(
    control_type: Optional[str],
    frequency: Optional[str],
) -> Optional[str]:
    """
    Returns a plain-English description of the evidence expectations for this
    control, suitable for display to GRC practitioners.

    Returns None if control_type is None (not yet classified).
    """
    if not control_type:
        return None

    ct = control_type.lower()
    freq_label = FREQUENCY_LABELS.get(frequency or '', frequency or '').lower() if frequency else None
    reqs = derive_testing_requirements(ct, frequency)
    sample_size = reqs['suggested_sample_size']

    if ct == 'automated':
        return (
            "This is a fully automated control. Only walkthrough evidence is required. "
            "Provide system configuration exports or screenshots that prove the control "
            "is enforced by the system without human intervention. No population or "
            "sample testing applies."
        )

    if ct == 'manual':
        if frequency == 'annual':
            return (
                "This is an annual manual control. Auditors will expect walkthrough evidence "
                "and a single instance of the control operating during the examination period. "
                "The instance itself is the sample — no separate population export is required."
            )

        if frequency == 'semi_annual':
            return (
                "This is a semi-annual manual control. Auditors will expect walkthrough "
                "evidence, a population of both occurrences in the examination period, and "
                "1–2 samples depending on how many occurrences fall within the window."
            )

        # quarterly, monthly, weekly, daily, continuous, adhoc
        if frequency:
            total_files = (sample_size or 0) + 2  # walkthrough + population/IPE + samples
            return (
                f"This is a {freq_label} manual control. Auditors will expect walkthrough "
                f"evidence, a full population export from the source system for the "
                f"examination period, IPE validation proving the export is complete and "
                f"accurate, and a sample of {sample_size or '?'} items showing the "
                f"control operating for each. "
                f"Total evidence files expected: {total_files} or more."
            )

        # frequency not yet set
        return (
            "This is a manual control. Set a frequency so the system can determine "
            "the required evidence phases and suggested sample size."
        )

    if ct == 'itdm':
        if frequency:
            total_files = (sample_size or 0) + 2
            return (
                f"This is a {freq_label} IT Dependent Manual control. Auditors will expect "
                f"a full population export from the source system for the entire examination "
                f"period, IPE validation proving the export is complete and accurate, and a "
                f"sample of {sample_size or '?'} items showing the human resolution or "
                f"review step for each. "
                f"Total evidence files expected: {total_files} or more."
            )

        return (
            "This is an IT Dependent Manual (ITDM) control. Set a frequency so the system "
            "can determine the required sample size. Population, IPE, and sample evidence "
            "are always required for ITDM controls regardless of frequency."
        )

    return None
