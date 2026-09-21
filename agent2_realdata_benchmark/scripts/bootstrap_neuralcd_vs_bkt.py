#!/usr/bin/env python3
"""Paired student-cluster bootstrap: selected NeuralCD versus frozen BKT.

Uses validation predictions only. Conditional on fitted/selected models.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / "data/splits/assist2009"
NEURAL = ROOT / "results/neuralcd/validation_v1/epoch_02"
BKT = ROOT / "results/bkt/frozen_v1_validation_predictions.parquet"
READINESS = ROOT / "docs/data/neuralcd_readiness_v1.json"
SELECTION = ROOT / "docs/data/neuralcd_checkpoint_selection_v1.json"
OUTPUT = NEURAL / "paired_bkt_bootstrap.json"

SEED = 20260921
REPLICATES = 1000
AUC_REPLICATES = 300


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def interval(estimate, samples):
    array = np.asarray(samples, dtype=np.float64)
    if not np.isfinite(array).all() or not len(array):
        raise RuntimeError("Invalid bootstrap estimates")
    lo, hi = np.quantile(array, [0.025, 0.975])
    return {
        "estimate": float(estimate),
        "ci95": [float(lo), float(hi)],
        "replicates": int(len(array)),
    }


def main():
    if OUTPUT.exists():
        raise FileExistsError(f"Bootstrap already exists: {OUTPUT}")

    manifest = read_json(SPLITS / "manifest.json")
    readiness = read_json(READINESS)
    selection = read_json(SELECTION)
    neural_report = read_json(NEURAL / "report.json")

    assert selection["selected"]["epoch"] == 2
    assert selection["test_evaluated"] is False
    assert neural_report["status"] == "full_validation_candidate"
    assert neural_report["epoch"] == 2
    assert neural_report["test_evaluated"] is False
    assert neural_report["global_weights_unchanged"] is True

    assert sha256(BKT) == readiness["frozen_prediction_sha256"]

    neural_file = NEURAL / "predictions.parquet"
    assert sha256(neural_file) == neural_report["predictions_sha256"]
    assert neural_report["checkpoint_sha256"] == (
        selection["selected"]["checkpoint_sha256"]
    )
    assert neural_report["split_assignment_sha256"] == (
        manifest["assignment_sha256"]
    )

    neural = pd.read_parquet(neural_file)[[
        "source_row", "student_id",
        "observed_correct", "predicted_probability",
    ]].rename(columns={
        "observed_correct": "neural_label",
        "predicted_probability": "neural_probability",
    })

    bkt = pd.read_parquet(BKT)[[
        "source_row", "student_id",
        "observed_correct", "predicted_probability",
    ]].rename(columns={
        "observed_correct": "bkt_label",
        "predicted_probability": "bkt_probability",
    })

    assert neural["source_row"].is_unique
    assert bkt["source_row"].is_unique

    bkt = bkt.loc[
        bkt["source_row"].isin(neural["source_row"])
    ]

    joined = neural.merge(
        bkt,
        on=["source_row", "student_id"],
        how="inner",
        validate="one_to_one",
    ).sort_values("source_row").reset_index(drop=True)

    if not (
        len(joined) == len(neural) == len(bkt) == 42437
    ):
        raise RuntimeError("Matched-target coverage mismatch")

    y = joined["neural_label"].to_numpy(dtype=np.int8)
    other_y = joined["bkt_label"].to_numpy(dtype=np.int8)

    np.testing.assert_array_equal(y, other_y)

    if not np.isin(y, [0, 1]).all():
        raise RuntimeError("Nonbinary outcomes")

    pn = joined["neural_probability"].to_numpy(
        dtype=np.float64
    )
    pb = joined["bkt_probability"].to_numpy(
        dtype=np.float64
    )

    for probabilities in (pn, pb):
        if (
            not np.isfinite(probabilities).all()
            or np.any(probabilities <= 0)
            or np.any(probabilities >= 1)
        ):
            raise RuntimeError("Invalid predicted probabilities")

    def nll_losses(probabilities):
        return -(
            y * np.log(probabilities)
            + (1 - y) * np.log1p(-probabilities)
        )

    neural_nll = nll_losses(pn)
    bkt_nll = nll_losses(pb)

    neural_brier = (pn - y) ** 2
    bkt_brier = (pb - y) ** 2

    neural_correct = ((pn >= 0.5) == y).astype(float)
    bkt_correct = ((pb >= 0.5) == y).astype(float)

    for name, losses, brier, correct, probabilities in (
        ("neuralcd", neural_nll, neural_brier, neural_correct, pn),
        ("matched_bkt", bkt_nll, bkt_brier, bkt_correct, pb),
    ):
        reference = neural_report[name]
        observed = {
            "nll": float(losses.mean()),
            "brier": float(brier.mean()),
            "accuracy_at_0_5": float(correct.mean()),
            "roc_auc": float(roc_auc_score(y, probabilities)),
        }
        for metric, value in observed.items():
            if not np.isclose(
                value, reference[metric], atol=1e-10, rtol=0
            ):
                raise RuntimeError(
                    f"{name}: {metric} differs from validation report"
                )

    student_ids = [
        str(s) for s in read_json(SPLITS / "val_students.json")
    ]

    assert len(student_ids) == 633
    assert len(set(student_ids)) == 633

    cluster = pd.Index(student_ids).get_indexer(
        joined["student_id"].astype(str)
    )

    if np.any(cluster < 0):
        raise RuntimeError("A non-validation student was scored")

    n_students = len(student_ids)
    counts = np.bincount(cluster, minlength=n_students)

    def student_sums(values):
        return np.bincount(
            cluster, weights=values, minlength=n_students
        )

    # All signs are positive when NeuralCD improves the metric.
    gains = {
        "nll_gain_bkt_minus_neuralcd":
            bkt_nll - neural_nll,
        "brier_gain_bkt_minus_neuralcd":
            bkt_brier - neural_brier,
        "accuracy_gain_neuralcd_minus_bkt":
            neural_correct - bkt_correct,
    }

    aggregates = {
        name: student_sums(values)
        for name, values in gains.items()
    }

    auc_point = float(
        roc_auc_score(y, pn) - roc_auc_score(y, pb)
    )

    samples = {name: [] for name in gains}
    auc_samples = []

    rng = np.random.default_rng(SEED)

    for iteration in range(REPLICATES):
        sampled = rng.integers(
            0, n_students, size=n_students
        )

        multiplicities = np.bincount(
            sampled, minlength=n_students
        )

        denominator = int(np.dot(multiplicities, counts))

        if denominator <= 0:
            raise RuntimeError("Empty bootstrap replicate")

        for name, sums in aggregates.items():
            samples[name].append(
                float(np.dot(multiplicities, sums) / denominator)
            )

        if iteration < AUC_REPLICATES:
            weights = multiplicities[cluster]

            if np.unique(y[weights > 0]).size == 2:
                auc_samples.append(float(
                    roc_auc_score(
                        y, pn, sample_weight=weights
                    ) - roc_auc_score(
                        y, pb, sample_weight=weights
                    )
                ))

    if len(auc_samples) != AUC_REPLICATES:
        raise RuntimeError("Some AUC replicates had only one class")

    results = {
        name: interval(values.mean(), samples[name])
        for name, values in gains.items()
    }

    results["auc_gain_neuralcd_minus_bkt"] = interval(
        auc_point, auc_samples
    )

    report = {
        "status": "conditional_validation_analysis",
        "selected_epoch": 2,
        "split_assignment_sha256":
            manifest["assignment_sha256"],
        "neural_predictions_sha256": sha256(neural_file),
        "bkt_predictions_sha256": sha256(BKT),
        "students_in_split": n_students,
        "students_with_matched_targets": int(
            np.count_nonzero(counts)
        ),
        "matched_targets": int(len(joined)),
        "seed": SEED,
        "method": "paired_student_cluster_bootstrap",
        "limitations": (
            "Conditional on training, checkpoint selection and "
            "provisional adaptation. Does not correct for "
            "validation-based model selection."
        ),
        "results": results,
        "test_evaluated": False,
    }

    OUTPUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    print("\nSaved:", OUTPUT)


if __name__ == "__main__":
    main()
