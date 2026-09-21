"""Label-free scoring and deterministic ranking for disagreement v1."""

from __future__ import annotations

import hashlib

import numpy as np


def candidate_scores(p_neural, p_bkt):
    """Return all eight registered scores from paired predictions."""

    p_n = np.asarray(p_neural, dtype=float)
    p_b = np.asarray(p_bkt, dtype=float)

    if p_n.ndim != 1 or p_n.shape != p_b.shape:
        raise ValueError("Predictions must be paired 1-D arrays")

    if not np.isfinite(p_n).all() or not np.isfinite(p_b).all():
        raise ValueError("Predictions must be finite")

    if (
        ((p_n < 0) | (p_n > 1)).any()
        or ((p_b < 0) | (p_b > 1)).any()
    ):
        raise ValueError("Predictions must be probabilities")

    r_n = 1.0 - p_n
    r_b = 1.0 - p_b
    disagreement = np.abs(p_n - p_b)

    scores = {
        "neuralcd_risk": r_n,
        "bkt_risk": r_b,
        "mean_risk": (r_n + r_b) / 2.0,
        "max_risk": np.maximum(r_n, r_b),
    }

    for alpha in (0.25, 0.5, 1.0, 2.0):
        scores[
            f"neuralcd_risk_plus_disagreement_a{alpha:g}"
        ] = r_n + alpha * disagreement

    return scores


def rank_indices(scores, student_ids, source_rows):
    """Rank descending score, then registered SHA256 tie-break."""

    values = np.asarray(scores, dtype=float)
    students = list(student_ids)
    sources = list(source_rows)

    if values.ndim != 1:
        raise ValueError("Scores must be one-dimensional")

    n = len(values)

    if len(students) != n or len(sources) != n:
        raise ValueError("Ranking identities must be aligned")

    if not np.isfinite(values).all():
        raise ValueError("Scores must be finite")

    if len(set(int(source) for source in sources)) != n:
        raise ValueError("Source rows must be unique")

    if any(
        not isinstance(student, str) or not student
        for student in students
    ):
        raise ValueError("Invalid student identifier")

    hashes = [
        hashlib.sha256(
            (
                "phase6_disagreement_v1|"
                + students[i]
                + "|"
                + str(int(sources[i]))
            ).encode("utf-8")
        ).hexdigest()
        for i in range(n)
    ]

    order = sorted(
        range(n),
        key=lambda i: (
            -float(values[i]),
            hashes[i],
            int(sources[i]),
        ),
    )

    return np.asarray(order, dtype=np.int64)
