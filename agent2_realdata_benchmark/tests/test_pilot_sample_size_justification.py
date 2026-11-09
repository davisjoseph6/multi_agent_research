"""Prospective design arithmetic checks, NOT researcher approval or outcome data."""
import pytest

from scripts.pilot_sample_size_justification import (
    hypothetical_wilson,
    min_allocated_per_arm,
    planning_report,
    probability_all_arms_reach_target,
)


def test_90_enrolled_75_target_not_assured_per_arm():
    report = planning_report()
    nominal = report["nominal_enrollment"]
    assert nominal["total_enrolled"] == 90
    assert nominal["target_completers_total"] == 75
    assert nominal["target_completers_per_arm"] == 25
    assert nominal["expected_completers_total_under_model"] == pytest.approx(75)
    assert nominal["probability_one_arm_reaches_target"] == pytest.approx(
        0.61644701469, abs=1e-7,
    )
    assert nominal["probability_all_three_arms_reach_target"] == pytest.approx(
        0.234254132579, abs=1e-7,
    )
    assert nominal["probability_total_reaches_target"] == pytest.approx(
        0.56837353036, abs=1e-7,
    )
    assert not report["sample_size_approved"]
    assert not report["human_enrollment_authorized"]
    assert not report["uses_real_student_data"]


def test_90_75_hypothetical_precision_is_not_an_observed_rate():
    report = planning_report()
    overall = report["nominal_enrollment"][
        "completion_interval_overall_if_exact_target_observed"
    ]
    arm = report["nominal_enrollment"][
        "completion_interval_one_arm_if_exact_target_observed"
    ]
    assert overall["wilson_95pct_low"] == pytest.approx(.74306114, abs=1e-7)
    assert overall["wilson_95pct_high"] == pytest.approx(.89631511, abs=1e-7)
    assert arm["wilson_95pct_low"] == pytest.approx(.66435649, abs=1e-7)
    assert arm["wilson_95pct_high"] == pytest.approx(.92663458, abs=1e-7)
    assert not arm["is_human_study_result"]
    assert not overall["is_human_study_result"]
    assert arm["maximum_distance_from_point_estimate"] > (
        overall["maximum_distance_from_point_estimate"]
    )


def test_assurance_sensitivity_if_independent_attrition_model():
    p = 5 / 6
    assert min_allocated_per_arm(25, p, .8) == 34
    assert min_allocated_per_arm(25, p, .9) == 35
    assert min_allocated_per_arm(25, p, .95) == 36
    assert probability_all_arms_reach_target(30, 25, p) < .25
    assert probability_all_arms_reach_target(34, 25, p) >= .8
    assert probability_all_arms_reach_target(33, 25, p) < .8


def test_existing_two_contrast_power_is_reused_without_adjusted_claims():
    report = planning_report(effect_sizes=(.5, .8))
    assert report["model"]["efficacy_alpha_per_comparison_bonferroni"] == .025
    assert report["minimum_detectable_d_at_nominal_completers"] == pytest.approx(
        .896, abs=.005,
    )
    effect = report["effect_size_sensitivity_only"]
    assert effect[0]["required_completers_per_arm_for_target_power"] == 78
    assert effect[0]["illustrative_total_recruits_at_assumed_completion"] == 282
    assert effect[0]["power_at_target_completers_per_arm"] == pytest.approx(
        .30166, abs=.002,
    )
    assert effect[1]["required_completers_per_arm_for_target_power"] == 31
    assert effect[1]["illustrative_total_recruits_at_assumed_completion"] == 114
    assert not report["model"]["adjustment_for_pretest_or_ceiling"]
    assert not report["model"]["fatigue_noninferiority_power_calculated"]


def test_hypothetical_counts_are_consistent():
    data = hypothetical_wilson(25, 30)
    assert data["hypothetical_successes_if_observed"] == 25
    assert data["denominator"] == 30
    assert data["wilson_95pct_low"] <= 25 / 30 <= data["wilson_95pct_high"]


def test_invalid_models_fail_closed_without_phantom_sample_size():
    for bad in (0, 1.01, 24, -3):
        with pytest.raises(ValueError):
            probability_all_arms_reach_target(30, 25, bad)
    for bad in (-.1, 0, 1.1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            planning_report(completion_probability=bad)
    with pytest.raises(ValueError):
        planning_report(target_per_arm=31)
    with pytest.raises(ValueError):
        planning_report(effect_sizes=(0.0,))
    with pytest.raises(ValueError):
        planning_report(effect_sizes=(float("nan"),))
    with pytest.raises(ValueError):
        planning_report(comparisons=0)
    with pytest.raises(ValueError):
        planning_report(family_alpha=1)
    with pytest.raises(ValueError):
        min_allocated_per_arm(25, .01, .95, maximum_per_arm=30)
