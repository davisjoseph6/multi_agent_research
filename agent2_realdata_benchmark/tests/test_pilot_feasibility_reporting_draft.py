"""Feasibility summaries are descriptive and strictly fictional."""
import copy

import pytest

from src.prototype.pilot_feasibility_reporting_draft import (
    SCHEMA, summarize_synthetic_feasibility, wilson_95,
)


def _row(randomized=30, v1=29, v2=28, v3=26, completed=25):
    return {
        "randomized": randomized,
        "visit1_attended": v1,
        "visit2_attended": v2,
        "visit3_attended": v3,
        "protocol_completed": completed,
        "posttest_observed": 25,
        "mvas_observed": 2 * (v1 + v2 + v3) - 2,
        "mvas_expected": 2 * (v1 + v2 + v3),
        "adjacent_visit_pairs_on_time": v2 + v3 - 1,
        "application_requests": 1000,
        "application_failures": 1,
        "intervention_fidelity_deviations": 0,
        "critical_incidents_reported": 0,
    }


def _example():
    return {
        "schema_version": SCHEMA,
        "fictional_only": True,
        "screening": {
            "approached": 110, "screened": 105,
            "eligible": 95, "consented": 90,
        },
        "arms": {arm: _row() for arm in "ABC"},
    }


def test_wilson_interval_at_boundaries_and_known_midpoint():
    empty = wilson_95(0, 0)
    assert empty == dict(numerator=0, denominator=0, rate=None,
                         lower_95=None, upper_95=None)
    mid = wilson_95(1, 2)
    assert mid["rate"] == .5
    assert .09 < mid["lower_95"] < .10
    assert .90 < mid["upper_95"] < .91
    assert wilson_95(2, 2)["upper_95"] == 1
    assert wilson_95(0, 2)["lower_95"] == 0


def test_fictional_90_person_report_reports_feasibility_not_efficacy():
    report = summarize_synthetic_feasibility(_example())
    assert report["result"] == "DESCRIPTIVE_SYNTHETIC_ONLY"
    assert report["overall"]["protocol_completion_among_randomized"]["rate"] == (
        round(75/90, 6)
    )
    assert report["arms"]["A"][
        "posttest_capture_among_visit3_attendees"
    ]["denominator"] == 26
    assert report["overall"]["mvas_capture_among_attended_visit_opportunities"][
        "denominator"
    ] == 498
    assert report["overall"]["adjacent_visit_pairs_on_time"]["numerator"] == 159
    assert set(report["arms"]) == {"A", "B", "C"}
    assert not report["progression_criteria_signed_and_frozen"]
    assert not report["human_enrollment_authorized"]
    assert not report["formal_efficacy_or_fatigue_noninferiority_analysis"]
    assert not report["ethics_and_data_protection_approved"]
    assert not report["fatigue_instrument_wording_and_validity_approved"]
    assert "student_id" not in str(report)
    assert "participant_id" not in str(report)


@pytest.mark.parametrize("counts", [
    (-1, 4), (5, 4), (True, 1), (1, True), (.5, 1), (0, -1),
])
def test_wilson_rejects_invalid_counts(counts):
    with pytest.raises(ValueError):
        wilson_95(*counts)


def test_denies_real_data_or_ids_and_any_extra_fields():
    example = _example()
    example["fictional_only"] = False
    with pytest.raises(ValueError):
        summarize_synthetic_feasibility(example)
    example = _example()
    example["participant_ids"] = ["real-person"]
    with pytest.raises(ValueError):
        summarize_synthetic_feasibility(example)
    example = _example()
    example["arms"]["A"]["student_name"] = "not allowed"
    with pytest.raises(ValueError):
        summarize_synthetic_feasibility(example)


def test_denies_invalid_visit_mvas_or_screening_counts():
    for path, invalid in [
        (("arms", "A", "visit2_attended"), 31),
        (("arms", "B", "posttest_observed"), 27),
        (("arms", "C", "mvas_expected"), 999),
        (("arms", "A", "mvas_observed"), 999),
        (("arms", "B", "adjacent_visit_pairs_on_time"), 999),
        (("arms", "B", "application_failures"), 1001),
        (("screening", "screened"), 111),
        (("arms", "C", "randomized"), True),
    ]:
        example = _example()
        example[path[0]][path[1]][path[2]] = invalid
        with pytest.raises(ValueError):
            summarize_synthetic_feasibility(example)


def test_missing_total_denominators_report_none_not_zero():
    example = {
        "schema_version": SCHEMA,
        "fictional_only": True,
        "screening": {
            "approached": 0, "screened": 0, "eligible": 0, "consented": 0,
        },
        "arms": {},
    }
    row = {
        key: 0 for key in _row()
    }
    for arm in "ABC":
        example["arms"][arm] = copy.deepcopy(row)
    report = summarize_synthetic_feasibility(example)
    assert report["recruitment_screened_per_approached"]["rate"] is None
    assert report["overall"]["application_failure_rate"]["rate"] is None
    assert report["overall"]["protocol_completion_among_randomized"]["rate"] is None
