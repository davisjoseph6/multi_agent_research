"""Exact mathematical checks for the hypothetical eight-concept drift certificate.

These are proofs-by-enumeration and model sanity tests, not educational data.
"""
from fractions import Fraction

import pytest

from src.prototype.step97_policy_drift_certificate import (
    N, capped_drift_bound, certify_distribution, coverage_mixture,
    expected_state_drift,
)
from src.prototype.study_v3_pomcp import CONCEPTS, PRACTICE


PRIMARY = (PRACTICE, CONCEPTS[0])


def test_deterministic_single_target_has_zero_worst_case_drift_without_forgetting():
    result = certify_distribution({PRIMARY: 1})
    assert result["strict_uniform_negative_drift"] is False
    assert result["worst_case_expected_drift"] == "0"
    assert result["certified_uniform_margin"] == "0"
    assert result["exhaustively_checked_positive_deficit_states"] == 2**N - 1
    assert result["deployed_v3_or_rct_policy_certified"] is False


def test_uniform_practice_sharp_margin_matches_closed_form():
    result = certify_distribution(coverage_mixture(PRIMARY, 1))
    # p_practice=.05; q_j=1/8; delta=p/(8*8)=1/1280.
    assert result["strict_uniform_negative_drift"] is True
    assert Fraction(result["certified_uniform_margin"]) == Fraction(1, 1280)
    assert result["exhaustively_checked_positive_deficit_states"] == 255


def test_mixture_margin_is_epsilon_times_practice_gain_over_n_squared():
    result = certify_distribution(coverage_mixture(PRIMARY, "0.1"))
    assert Fraction(result["certified_uniform_margin"]) == Fraction(1, 12800)


def test_arbitrarily_small_uniform_forgetting_can_destroy_some_guarantees():
    forgetting = {c: "0.001" for c in CONCEPTS}
    result = certify_distribution(coverage_mixture(PRIMARY, 1),
                                  forgetting=forgetting)
    # For a state with seven mastered concepts:
    # drift=(7*.001-.05/8)/8=0.00009375 > 0.
    assert Fraction(result["worst_case_expected_drift"]) == Fraction(3, 32000)
    assert result["strict_uniform_negative_drift"] is False


def test_weaker_forgetting_permits_a_conditional_model_margin():
    forgetting = {c: "0.0001" for c in CONCEPTS}
    result = certify_distribution(coverage_mixture(PRIMARY, 1),
                                  forgetting=forgetting)
    assert Fraction(result["certified_uniform_margin"]) == Fraction(111, 160000)
    assert result["strict_uniform_negative_drift"] is True


def test_formula_matches_single_target_mastered_counterexample():
    model_rates = (Fraction(1, 20),) + (Fraction(0),) * (N - 1)
    zeros = (Fraction(0),) * N
    state = (True, False) + (True,) * (N - 2)
    assert expected_state_drift(state, model_rates, zeros) == 0


def test_fifty_five_step_bound_is_vacuous_even_under_uniform_practice():
    result = capped_drift_bound(Fraction(1, 2), Fraction(1, 1280), 55)
    assert result["upper_bound_probability_not_recovered"] == "1"
    assert result["nontrivial"] is False


@pytest.mark.parametrize("bad", [-0.1, 1.01, float("nan"), True])
def test_invalid_mixture_probability_fails_closed(bad):
    with pytest.raises(ValueError):
        coverage_mixture(PRIMARY, bad)


def test_incomplete_action_support_or_invalid_weights_rejected():
    with pytest.raises(ValueError, match="sum"):
        certify_distribution({PRIMARY: "0.5"})
    with pytest.raises(ValueError, match="Invalid action"):
        certify_distribution({("NOT_AN_ACTION", CONCEPTS[0]): 1})
    with pytest.raises(ValueError, match="all eight"):
        certify_distribution({PRIMARY: 1}, forgetting={CONCEPTS[0]: 0.1})
