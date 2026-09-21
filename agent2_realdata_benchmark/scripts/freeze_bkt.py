#!/usr/bin/env python3
"""Freeze the best converged training-only BKT fit as baseline v1."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.fit_bkt import (
    load_sequences,
    metrics,
    run_partition,
)
from src.models.bkt import BKTParams


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/bkt"
DOCS = ROOT / "docs/data"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    original = read_json(RESULTS / "fit_report.json")
    multistart = read_json(
        RESULTS / "multistart_report.json"
    )

    if multistart["status"] != "training_objective_stable":
        raise RuntimeError("Multistart review is incomplete")

    if not multistart["all_runs_converged"]:
        raise RuntimeError("Not all optimization runs converged")

    successful = [
        run for run in multistart["runs"]
        if run["success"]
    ]

    selected = min(
        successful,
        key=lambda run: run["training_nll"],
    )

    if selected["name"] != (
        multistart["best_converged_fit"]["name"]
    ):
        raise AssertionError("Inconsistent multistart selection")

    sequences, num_concepts, manifest = load_sequences()

    for report in (original, multistart):
        if report["split_assignment_sha256"] != (
            manifest["assignment_sha256"]
        ):
            raise RuntimeError("Split identity mismatch")

    names = (
        "initial_mastery",
        "learning",
        "slip",
        "guess",
    )

    params = BKTParams(
        *(float(selected["parameters"][name]) for name in names)
    )

    train_nll, _ = run_partition(
        params,
        sequences["train"],
        num_concepts,
    )

    if not np.isclose(
        train_nll,
        selected["training_nll"],
        atol=1e-9,
        rtol=0,
    ):
        raise AssertionError(
            "Selected training NLL cannot be reproduced"
        )

    _, predictions = run_partition(
        params,
        sequences["val"],
        num_concepts,
        collect=True,
    )

    validation_metrics, selected_df = metrics(predictions)

    expected_count = manifest["primary_target_counts"]["val"]

    if len(selected_df) != expected_count:
        raise AssertionError("Unexpected validation target count")

    original_df = pd.read_parquet(
        RESULTS / "validation_predictions.parquet"
    )

    if (
        original_df["source_row"].duplicated().any()
        or selected_df["source_row"].duplicated().any()
    ):
        raise AssertionError("Duplicate prediction identifiers")

    old = original_df.sort_values(
        "source_row"
    ).reset_index(drop=True)

    new = selected_df.sort_values(
        "source_row"
    ).reset_index(drop=True)

    for column in (
        "source_row",
        "student_id",
        "observed_correct",
    ):
        if not np.array_equal(
            old[column].to_numpy(),
            new[column].to_numpy(),
        ):
            raise AssertionError(
                f"Original and selected predictions differ in {column}"
            )

    old_p = old["predicted_probability"].to_numpy(
        dtype=np.float64
    )

    new_p = new["predicted_probability"].to_numpy(
        dtype=np.float64
    )

    max_prediction_difference = float(
        np.max(np.abs(old_p - new_p))
    )

    nll_difference = float(
        validation_metrics["nll"]
        - original["fitted_validation"]["nll"]
    )

    record = {
        "version": "bkt_shared_v1",
        "status": "frozen_for_benchmark",
        "dataset": manifest["dataset"],
        "source_sha256": manifest["source_sha256"],
        "processed_sha256": manifest["processed_sha256"],
        "split_seed": manifest["seed"],
        "split_assignment_sha256": (
            manifest["assignment_sha256"]
        ),
        "selection_rule": (
            "Lowest training NLL among converged "
            "prespecified initializations"
        ),
        "selected_run": selected["name"],
        "parameters": {
            name: float(selected["parameters"][name])
            for name in names
        },
        "training_nll": float(train_nll),
        "validation": validation_metrics,
        "validation_predictions": (
            "results/bkt/frozen_v1_validation_predictions.parquet"
        ),
        "comparison_with_original_fit": {
            "validation_nll_difference_selected_minus_original":
                nll_difference,
            "maximum_absolute_probability_difference":
                max_prediction_difference,
        },
        "model_description": (
            "Shared-parameter BKT with factorized "
            "conjunctive multi-skill approximation"
        ),
        "outcome_definition": (
            "ASSISTments recorded binary outcome; "
            "zeros can include help requests"
        ),
        "test_evaluated": False,
    }

    # Never overwrite the original experiment.
    prediction_path = (
        RESULTS / "frozen_v1_validation_predictions.parquet"
    )

    document_path = DOCS / "bkt_v1_frozen.json"

    if prediction_path.exists() or document_path.exists():
        raise FileExistsError(
            "Frozen v1 already exists. "
            "Inspect it instead of silently overwriting."
        )

    selected_df.to_parquet(
        prediction_path,
        index=False,
    )

    write_json(document_path, record)

    print(json.dumps(record, indent=2))
    print("\nFrozen predictions:", prediction_path)
    print("Frozen specification:", document_path)


if __name__ == "__main__":
    main()
