"""Exact finite-horizon recovery certificate tests."""

from fractions import Fraction as F

import pytest

from src.prototype.step94_finite_drift import (
    FiniteDriftModel,
)


def bernoulli(p):
    return FiniteDriftModel(
        (F(0), F(1)),
        (
            (F(1), F(0)),
            (p, F(1) - p),
        ),
    )


def test_two_attempt_recovery_is_not_certain():
    model = bernoulli(F(3, 5))
    stats = model.capped_statistics(
        initial_state=1,
        cap=2,
    )

    assert stats["uniform_drift_margin"] == F(3, 5)
    assert stats["expected_attempts"] == F(7, 5)
    assert (
        stats["probability_not_recovered_by_cap"]
        == F(4, 25)
    )
    assert stats["expected_residual"] == F(4, 25)
    assert (
        stats["expected_attempts_upper_bound"]
        == F(5, 3)
    )
    assert (
        stats["failure_probability_upper_bound"]
        == F(5, 6)
    )


def test_less_than_half_success_still_positive_drift():
    stats = bernoulli(F(2, 5)).capped_statistics(1, 2)

    assert stats["uniform_drift_margin"] == F(2, 5)
    assert (
        stats["probability_not_recovered_by_cap"]
        == F(9, 25)
    )
    assert stats["expected_attempts"] == F(8, 5)


def test_multistate_model_certifies_worst_case_margin():
    model = FiniteDriftModel(
        (F(0), F(1), F(2)),
        (
            (F(1), F(0), F(0)),
            (F(1, 2), F(1, 2), F(0)),
            (F(0), F(1, 4), F(3, 4)),
        ),
    )

    assert model.uniform_drift_margin() == F(1, 4)

    stats = model.capped_statistics(2, 2)

    assert (
        stats["probability_not_recovered_by_cap"]
        == F(7, 8)
    )
    assert stats["expected_attempts"] == F(2)


def test_zero_drift_rejected():
    with pytest.raises(ValueError, match="drift"):
        bernoulli(F(0)).uniform_drift_margin()


@pytest.mark.parametrize(
    "invalid",
    [F(-1, 2), F(3, 2), 0.2],
)
def test_bad_probabilities_rejected(invalid):
    with pytest.raises(ValueError):
        bernoulli(invalid)


def test_nonabsorbing_target_rejected():
    with pytest.raises(ValueError, match="absorbing"):
        FiniteDriftModel(
            (F(0), F(1)),
            (
                (F(1, 2), F(1, 2)),
                (F(1), F(0)),
            ),
        )


def test_bad_caps_rejected():
    for cap in (0, -1, 1.0, True):
        with pytest.raises(ValueError):
            bernoulli(F(3, 5)).capped_statistics(1, cap)
