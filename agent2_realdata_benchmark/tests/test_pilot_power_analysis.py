"""Algorithmic sanity checks only; not a substitute for statistician approval."""
import pytest

from scripts.pilot_power_analysis import (
    min_detectable_d, min_n_per_arm, two_sample_t_power, wilson_ci,
)


def test_nominal_25_per_arm_has_large_mde():
    d = min_detectable_d(25, target_power=0.8, alpha=0.025)
    assert 0.88 < d < 0.91
    assert two_sample_t_power(25, 0.5, alpha=0.025) == pytest.approx(
        0.30166, abs=0.002
    )
    assert two_sample_t_power(25, d, alpha=0.025) == pytest.approx(
        0.80, abs=0.001
    )


def test_moderate_effect_requires_more_than_25():
    assert min_n_per_arm(0.5, 0.80, alpha=0.025) == 78
    assert min_n_per_arm(0.8, 0.80, alpha=0.025) == 31


def test_power_is_monotonic_locally():
    assert two_sample_t_power(25, 0.8) > two_sample_t_power(25, 0.5)
    assert two_sample_t_power(30, 0.5) > two_sample_t_power(25, 0.5)


def test_completion_interval_and_invalid_parameters():
    lo, hi = wilson_ci(75, 90)
    assert 0.74 < lo < 0.76
    assert 0.89 < hi < 0.91
    with pytest.raises(ValueError):
        wilson_ci(91, 90)
    with pytest.raises(ValueError):
        two_sample_t_power(2, 0.5)
    with pytest.raises(ValueError):
        min_n_per_arm(0.5, 1.1)
