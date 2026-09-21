"""Tests for the model-independent predictive-signal interface."""

import inspect
import math
from dataclasses import FrozenInstanceError

import pytest

from src.uncertainty.predictive import (
    signal_from_probability,
)


def test_maximum_entropy_at_half():
    signal = signal_from_probability(0.5)

    assert signal.p_correct == 0.5
    assert signal.failure_risk == 0.5

    assert signal.predictive_entropy_nats == pytest.approx(
        math.log(2)
    )

    assert signal.normalized_predictive_entropy == pytest.approx(
        1.0
    )


@pytest.mark.parametrize(
    ("p", "risk"),
    [(0.0, 1.0), (1.0, 0.0)],
)
def test_boundary_probabilities(p, risk):
    signal = signal_from_probability(p)

    assert signal.failure_risk == risk
    assert signal.predictive_entropy_nats == 0.0
    assert signal.normalized_predictive_entropy == 0.0


def test_complementary_probabilities_have_equal_entropy():
    low = signal_from_probability(0.1)
    high = signal_from_probability(0.9)

    assert low.normalized_predictive_entropy == pytest.approx(
        high.normalized_predictive_entropy
    )

    assert low.failure_risk == pytest.approx(0.9)
    assert high.failure_risk == pytest.approx(0.1)


def test_high_failure_risk_does_not_require_high_entropy():
    signal = signal_from_probability(0.01)

    assert signal.failure_risk == pytest.approx(0.99)
    assert signal.normalized_predictive_entropy < 0.1


@pytest.mark.parametrize(
    "p",
    [0.0001, 0.01, 0.25, 0.5, 0.75, 0.99, 0.9999],
)
def test_entropy_stays_within_unit_interval(p):
    signal = signal_from_probability(p)

    assert 0.0 <= signal.failure_risk <= 1.0
    assert 0.0 <= signal.normalized_predictive_entropy <= 1.0


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), -float("inf")],
)
def test_nonfinite_probabilities_rejected(value):
    with pytest.raises(ValueError, match="finite"):
        signal_from_probability(value)


@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_out_of_range_probabilities_rejected(value):
    with pytest.raises(ValueError, match="within"):
        signal_from_probability(value)


@pytest.mark.parametrize("value", [True, False, None, "0.5"])
def test_non_numeric_and_boolean_inputs_rejected(value):
    with pytest.raises(TypeError):
        signal_from_probability(value)


def test_output_is_immutable():
    signal = signal_from_probability(0.4)

    with pytest.raises(FrozenInstanceError):
        signal.failure_risk = 0.0


def test_no_response_label_in_function_interface():
    parameters = inspect.signature(
        signal_from_probability
    ).parameters

    assert list(parameters) == ["p_correct"]
