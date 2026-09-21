"""Synthetic tests for fixed-budget disagreement evaluation."""

import numpy as np
import pytest

from scripts.evaluate_disagreement import (
    score_budget,
    select_registered,
)


def test_fixed_budget_confusion_matrix():
    # Response zero is the event; the first two are alerted.
    result = score_budget([0, 1, 0, 1, 1], 2)

    assert result["count"] == 5
    assert result["alerts"] == 2
    assert result["tp"] == 1
    assert result["fp"] == 1
    assert result["fn"] == 1
    assert result["tn"] == 2

    assert result["alert_rate"] == pytest.approx(0.4)
    assert result["precision"] == pytest.approx(0.5)
    assert result["recall"] == pytest.approx(0.5)
    assert result["false_positive_rate"] == pytest.approx(1 / 3)


def test_fixed_budget_false_positives_mirror_tp():
    first = score_budget([0, 1, 1, 0], 2)
    second = score_budget([0, 0, 1, 1], 2)

    assert first["alerts"] == second["alerts"] == 2
    assert second["tp"] - first["tp"] == 1
    assert second["fp"] - first["fp"] == -1


@pytest.mark.parametrize(
    ("labels", "count"),
    [
        ([0, 1], 0),
        ([0, 1], 3),
        ([0, 1], True),
        ([0, 2, 1], 2),
        ([0, 0, 0], 2),
        ([1, 1, 1], 2),
        ([], 1),
    ],
)
def test_invalid_scoring_inputs_rejected(labels, count):
    with pytest.raises((ValueError, TypeError)):
        score_budget(labels, count)


def make_selection():
    ids_and_alphas = [
        ("neuralcd_risk", 0.0),
        ("bkt_risk", None),
        ("mean_risk", None),
        ("max_risk", None),
        ("neuralcd_risk_plus_disagreement_a0.25", 0.25),
        ("neuralcd_risk_plus_disagreement_a0.5", 0.5),
        ("neuralcd_risk_plus_disagreement_a1", 1.0),
        ("neuralcd_risk_plus_disagreement_a2", 2.0),
    ]

    spec = {
        "candidate_scores": [
            {"id": name, "alpha": alpha}
            for name, alpha in ids_and_alphas
        ]
    }

    results = [
        {
            "candidate_id": name,
            "budgets": {"0.3": {"tp": 5}},
        }
        for name, _ in ids_and_alphas
    ]

    return spec, results


def test_tie_preserves_risk_only_baseline():
    spec, results = make_selection()

    chosen = select_registered(results, spec)

    assert chosen["candidate_id"] == "neuralcd_risk"


def test_selection_excludes_non_disagreement_controls():
    spec, results = make_selection()

    for result in results:
        if result["candidate_id"] == "bkt_risk":
            result["budgets"]["0.3"]["tp"] = 99

    chosen = select_registered(results, spec)

    assert chosen["candidate_id"] == "neuralcd_risk"


def test_smaller_alpha_breaks_detection_tie():
    spec, results = make_selection()

    for result in results:
        if result["candidate_id"] in {
            "neuralcd_risk_plus_disagreement_a0.25",
            "neuralcd_risk_plus_disagreement_a1",
        }:
            result["budgets"]["0.3"]["tp"] = 8

    chosen = select_registered(results, spec)

    assert chosen["candidate_id"] == (
        "neuralcd_risk_plus_disagreement_a0.25"
    )
