"""Synthetic tests for registered event-detection evaluation."""

import numpy as np
import pytest

from scripts.evaluate_event_detection import (
    score,
    select_candidate,
)


def test_confusion_matrix_and_metrics():
    # The negative response (correct=0) is the detection target.
    negative = np.array([True, False, False, True])
    flags = np.array([True, False, True, False])

    result = score(flags, negative)

    assert result["count"] == 4
    assert result["tp"] == 1
    assert result["fp"] == 1
    assert result["fn"] == 1
    assert result["tn"] == 1

    assert result["alerts"] == 2
    assert result["alert_rate"] == pytest.approx(0.5)
    assert result["precision"] == pytest.approx(0.5)
    assert result["recall"] == pytest.approx(0.5)
    assert result["false_positive_rate"] == pytest.approx(0.5)


def test_no_trigger_has_undefined_precision():
    negative = np.array([True, False, True])
    flags = np.array([False, False, False])

    result = score(flags, negative)

    assert result["tp"] == 0
    assert result["fp"] == 0
    assert result["fn"] == 2
    assert result["tn"] == 1
    assert result["alerts"] == 0
    assert result["precision"] is None
    assert result["recall"] == 0.0


def test_budget_excludes_higher_detection_candidate():
    candidates = [
        {
            "policy": "no_trigger",
            "risk_threshold": 0.7,
            "entropy_threshold": 0.8,
            "metrics": {"tp": 0, "fp": 0, "alerts": 0},
            "within_alert_budget": True,
        },
        {
            "policy": "risk_only",
            "risk_threshold": 0.5,
            "entropy_threshold": 0.8,
            "metrics": {"tp": 9, "fp": 4, "alerts": 13},
            "within_alert_budget": False,
        },
        {
            "policy": "entropy_only",
            "risk_threshold": 0.7,
            "entropy_threshold": 0.8,
            "metrics": {"tp": 7, "fp": 2, "alerts": 9},
            "within_alert_budget": True,
        },
    ]

    chosen = select_candidate(
        candidates,
        ["no_trigger", "risk_only", "entropy_only"],
    )

    assert chosen["policy"] == "entropy_only"


def test_fewer_false_positives_breaks_tp_tie():
    candidates = [
        {
            "policy": "risk_only",
            "risk_threshold": 0.7,
            "entropy_threshold": 0.8,
            "metrics": {"tp": 5, "fp": 3, "alerts": 8},
            "within_alert_budget": True,
        },
        {
            "policy": "entropy_only",
            "risk_threshold": 0.7,
            "entropy_threshold": 0.8,
            "metrics": {"tp": 5, "fp": 1, "alerts": 6},
            "within_alert_budget": True,
        },
    ]

    chosen = select_candidate(
        candidates,
        ["risk_only", "entropy_only"],
    )

    assert chosen["policy"] == "entropy_only"


def test_invalid_paired_population_rejected():
    with pytest.raises(ValueError):
        score(
            np.array([True, False]),
            np.array([True]),
        )
