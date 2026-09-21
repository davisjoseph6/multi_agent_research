#!/usr/bin/env python3
"""Paired student-cluster bootstrap for BKT validation results."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / "data/splits/assist2009"
RESULTS = ROOT / "results/bkt"

SEED = 20260921
BOOTSTRAP_REPLICATES = 1000
AUC_REPLICATES = 300


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024), b""
        ):
            digest.update(chunk)

    return digest.hexdigest()


def interval(point: float, samples: list[float]) -> dict:
    samples = np.asarray(samples, dtype=np.float64)

    if not np.isfinite(samples).all():
        raise ValueError("Nonfinite bootstrap estimates")

    lower, upper = np.quantile(samples, [0.025, 0.975])

    return {
        "estimate": float(point),
        "ci95": [float(lower), float(upper)],
        "replicates": int(len(samples)),
    }


def main() -> None:
    manifest = json.loads(
        (SPLITS / "manifest.json").read_text()
    )

    assignment_path = SPLITS / "assignments.parquet"

    if sha256(assignment_path) != manifest[
        "assignment_sha256"
    ]:
        raise RuntimeError("Frozen assignment checksum changed")

    students = json.loads(
        (SPLITS / "val_students.json").read_text()
    )

    if len(students) != manifest["student_counts"]["val"]:
        raise AssertionError("Validation student count changed")

    predictions = pd.read_parquet(
        RESULTS / "validation_predictions.parquet"
    )

    diagnostic = json.loads(
        (RESULTS / "validation_diagnostics.json").read_text()
    )

    if not predictions["source_row"].is_unique:
        raise AssertionError("Duplicate prediction rows")

    expected = manifest["primary_target_counts"]["val"]

    if len(predictions) != expected:
        raise AssertionError(
            f"Expected {expected} predictions, "
            f"found {len(predictions)}"
        )

    student_index = pd.Index(
        [str(student) for student in students]
    )

    cluster = student_index.get_indexer(
        predictions["student_id"].astype(str)
    )

    if (cluster < 0).any():
        raise AssertionError(
            "Prediction belongs to a non-validation student"
        )

    y = predictions[
        "observed_correct"
    ].to_numpy(dtype=np.int8)

    p = predictions[
        "predicted_probability"
    ].to_numpy(dtype=np.float64)

    if not set(np.unique(y)).issubset({0, 1}):
        raise ValueError("Nonbinary labels")

    if not np.isfinite(p).all() or (
        (p <= 0) | (p >= 1)
    ).any():
        raise ValueError("Probabilities must be finite in (0,1)")

    constant = float(
        diagnostic["training_primary_target_positive_rate"]
    )

    if not 0 < constant < 1:
        raise ValueError("Invalid training positive rate")

    # Per-interaction paired losses.
    bkt_nll = -(
        y * np.log(p)
        + (1 - y) * np.log1p(-p)
    )

    constant_nll = -(
        y * np.log(constant)
        + (1 - y) * np.log1p(-constant)
    )

    bkt_brier = (p - y) ** 2
    constant_brier = (constant - y) ** 2

    bkt_correct = ((p >= 0.5) == y).astype(float)
    constant_correct = np.full_like(
        y,
        constant >= 0.5,
        dtype=bool,
    ).__eq__(y).astype(float)

    n_students = len(students)

    def per_student(values):
        return np.bincount(
            cluster,
            weights=values,
            minlength=n_students,
        )

    counts = np.bincount(
        cluster,
        minlength=n_students,
    )

    nll_gain = per_student(constant_nll - bkt_nll)
    brier_gain = per_student(
        constant_brier - bkt_brier
    )
    accuracy_gain = per_student(
        bkt_correct - constant_correct
    )

    n = int(counts.sum())

    if n != expected:
        raise AssertionError("Cluster counts do not sum correctly")

    point_nll = float(nll_gain.sum() / n)
    point_brier = float(brier_gain.sum() / n)
    point_accuracy = float(accuracy_gain.sum() / n)
    point_auc = float(roc_auc_score(y, p))

    # Check that we reproduce the independently generated diagnostic.
    reference_bkt = diagnostic["fitted_bkt"]
    reference_constant = diagnostic[
        "constant_train_rate_baseline"
    ]

    if not np.isclose(
        bkt_nll.mean(),
        reference_bkt["nll"],
        atol=1e-10,
    ):
        raise AssertionError("BKT NLL mismatch")

    if not np.isclose(
        constant_nll.mean(),
        reference_constant["nll"],
        atol=1e-10,
    ):
        raise AssertionError("Constant-baseline NLL mismatch")

    rng = np.random.default_rng(SEED)

    nll_samples = []
    brier_samples = []
    accuracy_samples = []
    auc_samples = []

    for iteration in range(BOOTSTRAP_REPLICATES):
        # Sample entire students, not independent interactions.
        selected = rng.integers(
            0, n_students, size=n_students
        )

        multiplicities = np.bincount(
            selected,
            minlength=n_students,
        )

        denominator = int(
            np.dot(multiplicities, counts)
        )

        if denominator == 0:
            raise RuntimeError("Empty bootstrap replicate")

        nll_samples.append(
            float(
                np.dot(multiplicities, nll_gain)
                / denominator
            )
        )

        brier_samples.append(
            float(
                np.dot(multiplicities, brier_gain)
                / denominator
            )
        )

        accuracy_samples.append(
            float(
                np.dot(multiplicities, accuracy_gain)
                / denominator
            )
        )

        # AUC requires reranking the resampled observations.
        # Use sample weights to represent repeated students.
        if iteration < AUC_REPLICATES:
            weights = multiplicities[cluster]

            selected_labels = y[weights > 0]

            if np.unique(selected_labels).size == 2:
                auc_samples.append(
                    float(
                        roc_auc_score(
                            y,
                            p,
                            sample_weight=weights,
                        )
                    )
                )

    report = {
        "dataset": "assist2009_corrected_collapsed",
        "partition": "validation_only",
        "split_seed": manifest["seed"],
        "bootstrap_seed": SEED,
        "validation_students": n_students,
        "students_with_targets": int(
            np.count_nonzero(counts)
        ),
        "validation_predictions": n,
        "method": "paired_student_cluster_bootstrap",
        "interpretation": (
            "Conditional uncertainty given the fitted models; "
            "does not include variation from retraining."
        ),
        "nll_gain_constant_minus_bkt": interval(
            point_nll,
            nll_samples,
        ),
        "brier_gain_constant_minus_bkt": interval(
            point_brier,
            brier_samples,
        ),
        "accuracy_gain_bkt_minus_constant": interval(
            point_accuracy,
            accuracy_samples,
        ),
        "bkt_roc_auc": interval(
            point_auc,
            auc_samples,
        ),
    }

    RESULTS.mkdir(parents=True, exist_ok=True)

    output = RESULTS / "validation_bootstrap.json"

    output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    print("\nSaved:", output)


if __name__ == "__main__":
    main()
