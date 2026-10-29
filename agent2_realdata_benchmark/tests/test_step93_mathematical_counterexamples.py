"""Exact counterexamples to overly broad recovery claims.

These are mathematical checks, not real-learner evidence.
"""

from fractions import Fraction


def test_a4_does_not_imply_positive_drift_margin():
    p = Fraction(3, 5)
    epsilon = Fraction(1)
    eta = Fraction(4, 5)
    n = 1

    assert p > Fraction(1, 2)
    assert eta < epsilon
    assert (p * epsilon - eta) / n == Fraction(-1, 5)


def test_probability_below_half_can_still_recover():
    # Successful action removes the deficit.
    # Failure leaves it unchanged.
    p = Fraction(2, 5)

    expected_drift = -p
    expected_hitting_time = 1 / p

    assert p <= Fraction(1, 2)
    assert expected_drift == Fraction(-2, 5)
    assert expected_hitting_time == Fraction(5, 2)


def test_two_attempt_cap_has_nonzero_failure_probability():
    p = Fraction(3, 5)
    attempts = 2

    probability_of_failure = (1 - p) ** attempts

    assert -p < 0
    assert probability_of_failure == Fraction(4, 25)


def test_low_initial_mastery_is_not_observed_decline():
    mastery = (Fraction(1, 5),) * 8

    degradation = 1 - sum(mastery) / len(mastery)

    assert degradation == Fraction(4, 5)
    assert degradation > Fraction(1, 2)
    # No previous timepoint exists to establish a decline.
