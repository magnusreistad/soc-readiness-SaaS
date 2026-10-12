import pytest

from app.utils.control_classification import (
    derive_testing_requirements,
    explain_testing_approach,
)


@pytest.mark.parametrize(
    "control_type, frequency, expected",
    [
        (None, "monthly", (False, False, None)),
        ("automated", "daily", (False, False, None)),
        ("manual", "annual", (False, False, 1)),
        ("manual", "quarterly", (True, True, 2)),
        ("manual", "monthly", (True, True, 5)),
        ("itdm", "weekly", (True, True, 15)),
        ("ITDM", "daily", (True, True, 25)),
        ("manual", None, (True, True, None)),
    ],
)
def test_derive_testing_requirements(control_type, frequency, expected):
    result = derive_testing_requirements(control_type, frequency)
    assert (
        result["requires_population"],
        result["requires_sample"],
        result["suggested_sample_size"],
    ) == expected


def test_explanation_matches_derived_sample_size():
    text = explain_testing_approach("manual", "monthly")
    # 5 samples + walkthrough + population/IPE
    assert "sample of 5 items" in text
    assert "Total evidence files expected: 7 or more." in text


def test_unclassified_control_has_no_explanation():
    assert explain_testing_approach(None, "monthly") is None
    assert explain_testing_approach("unknown", "monthly") is None
