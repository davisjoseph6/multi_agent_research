#!/usr/bin/env python3
"""Training-only constant baseline and BKT validation diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/assist2009"
SPLITS = ROOT / "data/splits/assist2009"
RESULTS = ROOT / "results/bkt"


def metrics(y, probabilities):
    """Binary prediction metrics; no fitting or threshold selection."""
    y = np.asarray(y, dtype=np.int8)
    p = np.clip(
        np.asarray(probabilities, dtype=np.float64),
        1e-12,
        1.0 - 1e-12,
    )

    result = {
        "n": int(len(y)),
        "positive_rate": float(np.mean(y)),
        "nll": float(-np.mean(
            y * np.log(p) + (1 - y) * np.log1p(-p)
        )),
        "brier": float(np.mean((p - y) ** 2)),
        "accuracy_0_5": float(np.mean((p >= 0.5) == y)),
        "roc_auc": (
            float(roc_auc_score(y, p))
            if len(np.unique(y)) == 2
            else None
        ),
    }

    return result


def calibration(y, probabilities, bins=10):
    """Report fixed-width calibration bins and weighted ECE."""
    p = np.asarray(probabilities, dtype=np.float64)
    y = np.asarray(y, dtype=np.int8)

    indices = np.minimum((p * bins).astype(int), bins - 1)
    rows = []
    ece = 0.0

    for bin_id in range(bins):
        mask = indices == bin_id

        if not mask.any():
            continue

        observed = float(y[mask].mean())
        predicted = float(p[mask].mean())
        weight = float(mask.mean())

        ece += weight * abs(observed - predicted)

        rows.append({
            "bin": bin_id,
            "count": int(mask.sum()),
            "mean_prediction": predicted,
            "observed_frequency": observed,
        })

    return float(ece), rows


def main():
    df = pd.read_parquet(
        DATA / "interactions.parquet",
        columns=[
            "source_row",
            "student_id",
            "event_order",
            "concept_ids",
            "has_skill_annotation",
            "is_primary_target",
            "correct",
            "first_action",
        ],
    )

    assignments = pd.read_parquet(
        SPLITS / "assignments.parquet",
        columns=["source_row", "partition"],
    )

    df = df.merge(
        assignments,
        on="source_row",
        validate="one_to_one",
    )

    # The test partition is not used for any computation.
    df = df.loc[df["partition"].isin(["train", "val"])].copy()

    train_targets = df.loc[
        df["partition"].eq("train")
        & df["is_primary_target"]
    ]

    train_positive_rate = float(
        train_targets["correct"].mean()
    )

    val = df.loc[
        df["partition"].eq("val")
    ].copy()

    val = val.sort_values(
        ["student_id", "event_order"],
        kind="mergesort",
    )

    # History lengths are calculated using only preceding records.
    val["prior_events"] = val.groupby(
        "student_id"
    ).cumcount()

    val["prior_tagged_events"] = (
        val.groupby("student_id")[
            "has_skill_annotation"
        ].cumsum().astype(int)
        - val["has_skill_annotation"].astype(int)
    )

    val = val.loc[val["is_primary_target"]].copy()

    val["skill_count"] = val["concept_ids"].map(len)

    val["history_group"] = pd.cut(
        val["prior_tagged_events"],
        bins=[-1, 0, 4, 19, np.inf],
        labels=["0", "1-4", "5-19", "20+"],
    )

    predictions = pd.read_parquet(
        RESULTS / "validation_predictions.parquet"
    )

    if not predictions["source_row"].is_unique:
        raise AssertionError("Duplicate prediction source rows")

    if set(predictions["source_row"]) != set(val["source_row"]):
        raise AssertionError(
            "Validation predictions do not match eligible "
            "validation targets exactly"
        )

    scored = val.merge(
        predictions[
            ["source_row", "observed_correct",
             "predicted_probability"]
        ],
        on="source_row",
        validate="one_to_one",
    )

    if not np.array_equal(
        scored["correct"].to_numpy(),
        scored["observed_correct"].to_numpy(),
    ):
        raise AssertionError("Prediction labels disagree with data")

    if len(scored) != 42748:
        raise AssertionError("Unexpected validation target count")

    if (
        scored["predicted_probability"].isna().any()
        or not np.isfinite(
            scored["predicted_probability"].to_numpy()
        ).all()
    ):
        raise AssertionError("Nonfinite predictions")

    y = scored["correct"].to_numpy()

    p = scored["predicted_probability"].to_numpy()

    constant = np.full(
        len(scored),
        train_positive_rate,
        dtype=np.float64,
    )

    report = {
        "training_primary_target_positive_rate":
            train_positive_rate,
        "constant_train_rate_baseline": metrics(y, constant),
        "fitted_bkt": metrics(y, p),
        "subgroups": {},
    }

    report["ece_10_bins"], report["calibration_bins"] = (
        calibration(y, p)
    )

    groups = {
        "single_concept": scored["skill_count"].eq(1),
        "multi_concept": scored["skill_count"].gt(1),
        "answer_attempt": scored["first_action"].eq("0"),
        "help_or_scaffold_request": scored[
            "first_action"
        ].isin(["1", "2"]),
    }

    for category in ("0", "1-4", "5-19", "20+"):
        groups[f"prior_tagged_{category}"] = (
            scored["history_group"].astype(str).eq(category)
        )

    for name, mask in groups.items():
        subset = scored.loc[mask]

        if len(subset) == 0:
            continue

        report["subgroups"][name] = metrics(
            subset["correct"],
            subset["predicted_probability"],
        )

    RESULTS.mkdir(parents=True, exist_ok=True)

    path = RESULTS / "validation_diagnostics.json"

    path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    print("\nSaved:", path)


if __name__ == "__main__":
    main()
