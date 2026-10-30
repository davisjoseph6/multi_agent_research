"""Falsification checks for a fixed-mastery V6 signal null."""
from fractions import Fraction
from itertools import product

import pytest

from scripts.step95_v6_null_signal_exact import (
    INITIAL, exact_signal_probability, transition,
)
from src.prototype.step95_v6_decline_candidate import ObservationChangeController
from src.prototype.study_v3_pomcp import CONCEPTS


def exhaustive_probability(q, n):
    total = Fraction(0)
    for sequence in product((False, True), repeat=n):
        controller = ObservationChangeController()
        for response in sequence:
            controller.observe(CONCEPTS[0], response)
        if controller.signal_onsets:
            total += (q ** sum(sequence)) * ((1 - q) ** (n - sum(sequence)))
    return total


@pytest.mark.parametrize("q", [Fraction(9, 10), Fraction(3, 4), Fraction(1, 4)])
def test_four_observation_closed_form(q):
    assert exact_signal_probability(q, 4) == q**2 * (1 - q)**2


@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_trigger_needs_four_responses(n):
    assert exact_signal_probability(Fraction(1, 4), n) == 0


@pytest.mark.parametrize("q", [Fraction(9, 10), Fraction(1, 4)])
@pytest.mark.parametrize("n", [4, 6, 8])
def test_exact_dp_matches_exhaustive_real_controller(q, n):
    assert exact_signal_probability(q, n) == exhaustive_probability(q, n)


def test_stationary_no_forgetting_can_generate_signal():
    assert exact_signal_probability(Fraction(9, 10), 4) > 0
    assert exact_signal_probability(Fraction(1, 4), 4) > 0


def test_four_observation_unmastered_more_likely_than_mastered_nominal():
    assert exact_signal_probability(Fraction(1, 4), 4) > exact_signal_probability(Fraction(9, 10), 4)


def test_four_observation_noisy_mastered_equals_unmastered():
    assert exact_signal_probability(Fraction(3, 4), 4) == exact_signal_probability(Fraction(1, 4), 4)


def test_one_state_transition_matches_expected_trigger():
    state = INITIAL
    for answer in (True, True, False, False):
        state = transition(state, answer)
    assert state[-1] is True
    assert state[-2] is True


@pytest.mark.parametrize("invalid_q", [Fraction(-1, 10), Fraction(11, 10), True, "not probability"])
def test_reject_invalid_probability(invalid_q):
    with pytest.raises(ValueError):
        exact_signal_probability(invalid_q, 4)


@pytest.mark.parametrize("invalid_n", [-1, 201, 1.5, True])
def test_reject_invalid_observation_count(invalid_n):
    with pytest.raises(ValueError):
        exact_signal_probability(Fraction(1, 4), invalid_n)


def test_probability_nondecreasing_and_normalized():
    for q in (Fraction(1, 4), Fraction(9, 10)):
        values = [exact_signal_probability(q, n) for n in range(21)]
        assert all(0 <= p <= 1 for p in values)
        assert values == sorted(values)


def test_iid_constant_model_not_claiming_human_validity():
    assert exact_signal_probability(Fraction(1, 2), 4) == Fraction(1, 16)
