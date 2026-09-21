"""Synthetic checks for the registered disagreement ranking."""

import hashlib

import numpy as np
import pytest

from src.uncertainty.disagreement import (
    candidate_scores,
    rank_indices,
)


def test_all_eight_candidate_scores():
    scores = candidate_scores(
        np.array([0.2, 0.8]),
        np.array([0.6, 0.4]),
    )

    assert len(scores) == 8

    np.testing.assert_allclose(
        scores["neuralcd_risk"],
        [0.8, 0.2],
    )

    np.testing.assert_allclose(
        scores["bkt_risk"],
        [0.4, 0.6],
    )

    np.testing.assert_allclose(
        scores["mean_risk"],
        [0.6, 0.4],
    )

    np.testing.assert_allclose(
        scores["max_risk"],
        [0.8, 0.6],
    )

    np.testing.assert_allclose(
        scores["neuralcd_risk_plus_disagreement_a0.5"],
        [1.0, 0.4],
    )


def test_ranking_is_descending():
    order = rank_indices(
        [0.2, 0.9, 0.5],
        ["a", "b", "c"],
        [10, 11, 12],
    )

    assert order.tolist() == [1, 2, 0]


def test_registered_sha256_tie_break():
    students = ["a", "b", "c"]
    rows = [10, 11, 12]
    scores = [0.5, 0.5, 0.5]

    order = rank_indices(scores, students, rows)

    expected = sorted(
        range(3),
        key=lambda i: (
            hashlib.sha256(
                (
                    f"phase6_disagreement_v1|"
                    f"{students[i]}|{rows[i]}"
                ).encode("utf-8")
            ).hexdigest(),
            rows[i],
        ),
    )

    assert order.tolist() == expected


def test_ranking_is_deterministic():
    args = (
        [0.5, 0.5, 0.7],
        ["a", "b", "c"],
        [1, 2, 3],
    )

    np.testing.assert_array_equal(
        rank_indices(*args),
        rank_indices(*args),
    )


@pytest.mark.parametrize(
    ("neural", "bkt"),
    [
        ([0.2], [0.2, 0.3]),
        ([float("nan")], [0.3]),
        ([1.1], [0.3]),
        ([-0.1], [0.3]),
    ],
)
def test_invalid_predictions_rejected(neural, bkt):
    with pytest.raises(ValueError):
        candidate_scores(neural, bkt)


def test_duplicate_sources_rejected():
    with pytest.raises(ValueError, match="unique"):
        rank_indices(
            [0.1, 0.2],
            ["a", "b"],
            [10, 10],
        )


def test_nonfinite_ranking_score_rejected():
    with pytest.raises(ValueError, match="finite"):
        rank_indices(
            [0.1, float("inf")],
            ["a", "b"],
            [10, 11],
        )
