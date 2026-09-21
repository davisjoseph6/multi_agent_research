"""Tests for frozen-model signal records."""

import inspect
import math

import pytest

from src.uncertainty.bridge import signal_record


def make(**changes):
    arguments = {
        "source_row": 12,
        "student_id": "student-A",
        "model": "neuralcd_v1",
        "supported": True,
        "probability": 0.25,
    }
    arguments.update(changes)
    return signal_record(**arguments)


def test_supported_prediction():
    row = make()

    assert row["status"] == "supported"
    assert row["p_correct"] == 0.25
    assert row["failure_risk"] == 0.75
    assert 0 < row["normalized_predictive_entropy"] < 1
    assert math.isfinite(row["predictive_entropy_nats"])


def test_bkt_supported_prediction():
    row = make(model="bkt_v1")

    assert row["status"] == "supported"
    assert row["failure_risk"] == 0.75


def test_unsupported_neuralcd_is_not_artificial_probability():
    row = make(
        supported=False,
        probability=None,
    )

    assert row["status"] == "unsupported_training_item"

    for column in (
        "p_correct",
        "failure_risk",
        "predictive_entropy_nats",
        "normalized_predictive_entropy",
    ):
        assert row[column] is None


def test_unsupported_with_probability_rejected():
    with pytest.raises(ValueError, match="must not"):
        make(supported=False)


def test_supported_without_probability_rejected():
    with pytest.raises(ValueError, match="require"):
        make(probability=None)


def test_unsupported_bkt_rejected():
    with pytest.raises(ValueError, match="BKT"):
        make(
            model="bkt_v1",
            supported=False,
            probability=None,
        )


@pytest.mark.parametrize(
    "value",
    [-0.1, 1.1, float("nan"), float("inf")],
)
def test_invalid_probabilities_rejected(value):
    with pytest.raises(ValueError):
        make(probability=value)


def test_unknown_model_rejected():
    with pytest.raises(ValueError, match="Unknown"):
        make(model="unregistered_model")


def test_invalid_student_rejected():
    with pytest.raises(ValueError, match="student_id"):
        make(student_id="")


def test_negative_source_row_rejected():
    with pytest.raises(ValueError, match="nonnegative"):
        make(source_row=-1)


def test_boolean_source_row_rejected():
    with pytest.raises(TypeError):
        make(source_row=True)


def test_no_response_labels_in_interface():
    names = inspect.signature(signal_record).parameters

    assert set(names) == {
        "source_row",
        "student_id",
        "model",
        "supported",
        "probability",
    }

    assert "correct" not in names
    assert "observed_correct" not in names
    assert "outcome" not in names
