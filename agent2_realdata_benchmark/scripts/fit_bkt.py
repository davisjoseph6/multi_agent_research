#!/usr/bin/env python3
"""Fit shared BKT parameters on training students; validate without test use."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.metrics import roc_auc_score

from src.models.bkt import BKT, BKTParams


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/assist2009"
SPLITS = ROOT / "data/splits/assist2009"
OUTPUT = ROOT / "results/bkt"

BOUNDS = [
    (0.01, 0.95),   # Initial mastery
    (0.001, 0.50),  # Learning
    (0.001, 0.45),  # Slip
    (0.001, 0.45),  # Guess
]


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_sequences():
    """Read frozen data and construct train/validation histories only."""
    canonical = DATA / "interactions.parquet"
    assignments_file = SPLITS / "assignments.parquet"

    manifest = json.loads(
        (SPLITS / "manifest.json").read_text(encoding="utf-8")
    )
    metadata = json.loads(
        (DATA / "metadata.json").read_text(encoding="utf-8")
    )

    if checksum(canonical) != manifest["processed_sha256"]:
        raise RuntimeError("Canonical dataset checksum changed")

    if checksum(assignments_file) != manifest["assignment_sha256"]:
        raise RuntimeError("Frozen assignments checksum changed")

    if metadata["source_sha256"] != manifest["source_sha256"]:
        raise RuntimeError("Raw dataset identity changed")

    df = pd.read_parquet(canonical)
    assignments = pd.read_parquet(assignments_file)

    df = df.merge(
        assignments[["source_row", "partition"]],
        on="source_row",
        validate="one_to_one",
    )

    # No test sequences are constructed, fitted, predicted or scored.
    df = df.loc[df["partition"].isin(["train", "val"])].copy()

    Q = np.load(DATA / "Q.npy")
    item_skills = [
        np.flatnonzero(Q[item]).tolist()
        for item in range(Q.shape[0])
    ]

    sequences = {"train": [], "val": []}

    for (partition, student), group in df.groupby(
        ["partition", "student_id"],
        sort=False,
    ):
        group = group.sort_values("event_order")

        history = []

        for row in group.itertuples(index=False):
            history.append((
                int(row.source_row),
                str(student),
                item_skills[int(row.item_idx)],
                int(row.correct),
                bool(row.is_primary_target),
            ))

        sequences[partition].append(history)

    for partition in ("train", "val"):
        expected_students = manifest["student_counts"][partition]
        expected_targets = manifest["primary_target_counts"][partition]

        if len(sequences[partition]) != expected_students:
            raise AssertionError(
                f"{partition}: student count does not match manifest"
            )

        observed_targets = sum(
            int(event[4])
            for history in sequences[partition]
            for event in history
        )

        if observed_targets != expected_targets:
            raise AssertionError(
                f"{partition}: target count does not match manifest"
            )

    return sequences, Q.shape[1], manifest


def run_partition(params, histories, n_concepts, collect=False):
    """Sequentially predict, reveal the label, then update BKT."""
    total_loss = 0.0
    target_count = 0
    predictions = []

    for history in histories:
        model = BKT(n_concepts, params)

        for source_row, student, skills, label, target in history:
            if not skills:
                # Missing tags: no defensible concept update.
                if target:
                    raise AssertionError(
                        "Untagged question cannot be a primary target"
                    )
                continue

            # Prediction is made before the current label is used.
            if target:
                probability = model.predict(skills)

                total_loss -= math.log(
                    probability if label == 1 else 1.0 - probability
                )
                target_count += 1

                if collect:
                    predictions.append((
                        source_row,
                        student,
                        label,
                        probability,
                    ))

            # Previous scaffolding responses also update the history.
            model.update(skills, label)

    if target_count == 0:
        raise RuntimeError("No eligible prediction targets")

    return total_loss / target_count, predictions


def metrics(predictions):
    """Evaluate the already-generated validation predictions."""
    df = pd.DataFrame(
        predictions,
        columns=[
            "source_row",
            "student_id",
            "observed_correct",
            "predicted_probability",
        ],
    )

    y = df["observed_correct"].to_numpy(dtype=np.int8)
    p = df["predicted_probability"].to_numpy(dtype=np.float64)

    output = {
        "count": int(len(df)),
        "nll": float(-np.mean(
            y * np.log(p) + (1 - y) * np.log1p(-p)
        )),
        "brier": float(np.mean((p - y) ** 2)),
        "accuracy_at_0_5": float(np.mean((p >= 0.5) == y)),
        "positive_fraction": float(np.mean(y)),
    }

    output["roc_auc"] = (
        float(roc_auc_score(y, p))
        if len(np.unique(y)) == 2
        else None
    )

    return output, df


def main():
    sequences, n_concepts, manifest = load_sequences()

    train = sequences["train"]
    val = sequences["val"]

    default = BKTParams()

    default_train_nll, _ = run_partition(
        default, train, n_concepts
    )

    print("Training students:", len(train), flush=True)
    print("Validation students:", len(val), flush=True)
    print("Default training NLL:", default_train_nll, flush=True)

    evaluations = 0
    best_loss = float("inf")

    def objective(x):
        nonlocal evaluations, best_loss

        params = BKTParams(*map(float, x))

        loss, _ = run_partition(
            params, train, n_concepts
        )

        evaluations += 1
        best_loss = min(best_loss, loss)

        if evaluations == 1 or evaluations % 10 == 0:
            print(
                f"Train objective evaluation {evaluations}: "
                f"NLL={loss:.6f}; best={best_loss:.6f}",
                flush=True,
            )

        return loss

    initial = np.array([
        default.initial_mastery,
        default.learning,
        default.slip,
        default.guess,
    ])

    result = minimize(
        objective,
        initial,
        method="L-BFGS-B",
        bounds=BOUNDS,
        options={
            "maxiter": 35,
            "maxfun": 120,
            "eps": 1e-4,
            "ftol": 1e-8,
        },
    )

    fitted = BKTParams(*map(float, result.x))

    fitted_train_nll, _ = run_partition(
        fitted, train, n_concepts
    )

    # Only after training do we evaluate the validation partition.
    _, default_predictions = run_partition(
        default, val, n_concepts, collect=True
    )

    _, fitted_predictions = run_partition(
        fitted, val, n_concepts, collect=True
    )

    default_val, _ = metrics(default_predictions)
    fitted_val, fitted_df = metrics(fitted_predictions)

    OUTPUT.mkdir(parents=True, exist_ok=True)

    fitted_df.to_parquet(
        OUTPUT / "validation_predictions.parquet",
        index=False,
    )

    report = {
        "dataset": "assist2009_corrected_collapsed",
        "split_seed": manifest["seed"],
        "split_assignment_sha256": manifest["assignment_sha256"],
        "parameter_method": "training_only_sequential_mle",
        "multi_skill_model": "factorized_conjunctive_approximation",
        "optimizer": {
            "method": "L-BFGS-B",
            "success": bool(result.success),
            "message": str(result.message),
            "iterations": int(result.nit),
            "function_evaluations": int(result.nfev),
        },
        "default_parameters": {
            "initial_mastery": default.initial_mastery,
            "learning": default.learning,
            "slip": default.slip,
            "guess": default.guess,
        },
        "fitted_parameters": {
            "initial_mastery": fitted.initial_mastery,
            "learning": fitted.learning,
            "slip": fitted.slip,
            "guess": fitted.guess,
        },
        "default_train_nll": float(default_train_nll),
        "fitted_train_nll": float(fitted_train_nll),
        "default_validation": default_val,
        "fitted_validation": fitted_val,
        "status": (
            "optimizer_converged"
            if result.success
            else "provisional_optimizer_not_converged"
        ),
    }

    (OUTPUT / "fit_report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\n=== BKT FIT REPORT ===")
    print(json.dumps(report, indent=2))
    print("\nSaved results to:", OUTPUT)


if __name__ == "__main__":
    main()
