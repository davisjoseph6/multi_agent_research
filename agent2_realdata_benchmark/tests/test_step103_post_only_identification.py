"""Exact restricted observational-equivalence regression tests."""
from fractions import Fraction

import pytest

from src.prototype.step103_post_only_identification import (
    distributions, emission_sequence, exact_identification_report,
    observation_prob, total_variation,
)


@pytest.mark.parametrize("n", [0, 1, 2, 3, 6, 8])
def test_post_only_observations_cannot_discriminate_same_current_mixture(n):
    forgotten, low_initial = distributions(
        forget_probability=Fraction(1, 4), post_questions=n)
    assert forgotten == low_initial
    assert total_variation(forgotten, low_initial) == 0
    assert sum(forgotten.values()) == 1


def test_one_pretransition_question_is_not_exactly_equivalent():
    a, b = distributions(
        forget_probability=Fraction(1, 4),
        post_questions=3, observed_pre_question=True,
    )
    assert total_variation(a, b) == Fraction(13, 80)


def test_demo_reports_exact_equal_prior_classification_limits():
    report = exact_identification_report()
    assert report["post_only_optimal_equal_prior_error"] == "1/2"
    assert report["one_prequestion_plus_post_total_variation"] == "13/80"
    assert report["one_prequestion_plus_post_optimal_equal_prior_error"] == "67/160"
    assert report["general_bkt_nonidentifiable"] is False
    assert report["human_learning_evidence"] is False


def test_no_forgetting_means_identical_hypotheses_with_pre_and_post():
    a, b = distributions(forget_probability=0, post_questions=3,
                         observed_pre_question=True)
    assert a == b
    assert total_variation(a, b) == 0


def test_indistinguishable_emissions_hide_any_pretransition_difference():
    report = exact_identification_report(
        slip="3/4", guess="1/4", forget_probability="1/2", post_questions=4)
    assert report["one_prequestion_plus_post_total_variation"] == "0"
    assert report["post_only_total_variation"] == "0"


def test_fixed_state_emission_probabilities():
    assert observation_prob(True, True) == Fraction(9, 10)
    assert observation_prob(False, True) == Fraction(1, 4)
    assert emission_sequence(True, (True, False)) == Fraction(9, 100)


@pytest.mark.parametrize("invalid", ["-1/2", "5/4", "bad", True])
def test_invalid_probabilities_rejected(invalid):
    with pytest.raises(ValueError):
        distributions(forget_probability=invalid, post_questions=3)


@pytest.mark.parametrize("invalid_n", [-1, 13, True, "3"])
def test_invalid_number_of_questions_rejected(invalid_n):
    with pytest.raises(ValueError):
        distributions(forget_probability="1/4", post_questions=invalid_n)


def test_invalid_distribution_or_nonnormalized_input_rejected():
    with pytest.raises(ValueError):
        total_variation({True: Fraction(1)}, {False: Fraction(1)})
    with pytest.raises(ValueError):
        total_variation({True: Fraction(1, 2)}, {True: Fraction(1)})


def test_one_pretest_observation_is_not_a_general_bkt_identifiability_claim():
    report = exact_identification_report(
        forget_probability="1/10", slip="1/10", guess="1/4", post_questions=5)
    assert report["post_only_total_variation"] == "0"
    assert Fraction(report["one_prequestion_plus_post_total_variation"]) == Fraction(13, 200)
    assert report["novel_identifiability_theorem_established"] is False
