#!/usr/bin/env python3
"""Run and verify the preregistered NeuralCD validation grid."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/data/neuralcd_grid_spec_v1.json"
GRID = ROOT / "results/neuralcd/validation_grid_v1"
BASE = ROOT / "results/neuralcd/validation_v1"
LOGS = ROOT / "results/neuralcd/grid_v1_logs"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024), b""
        ):
            digest.update(chunk)
    return digest.hexdigest()


def token(value):
    return format(value, "g").replace(".", "p")


def verify(path, candidate, expected_rows, expected_labels):
    report_path = path / "report.json"
    prediction_path = path / "predictions.parquet"

    if not report_path.is_file() or not prediction_path.is_file():
        raise RuntimeError(
            f"Incomplete candidate: {path}"
        )

    report = read(report_path)

    assert report["status"] == "full_validation_candidate"
    assert report["epoch"] == candidate["epoch"]
    assert report["adaptation_learning_rate"] == (
        candidate["learning_rate"]
    )
    assert report["adaptation_prior_penalty"] == (
        candidate["prior_penalty"]
    )

    assert report["validation_students_processed"] == 633
    assert report["primary_targets"] == 42748
    assert report["matched_targets"] == 42437
    assert report["unsupported_targets"] == 311
    assert report["global_weights_unchanged"] is True
    assert report["test_evaluated"] is False

    assert sha256(prediction_path) == (
        report["predictions_sha256"]
    )

    predictions = pd.read_parquet(
        prediction_path,
        columns=[
            "source_row",
            "observed_correct",
        ],
    ).sort_values("source_row")

    assert len(predictions) == 42437
    assert predictions["source_row"].is_unique

    np.testing.assert_array_equal(
        predictions["source_row"].to_numpy(),
        expected_rows,
    )

    np.testing.assert_array_equal(
        predictions["observed_correct"].to_numpy(),
        expected_labels,
    )

    return report


def main():
    spec = read(SPEC)

    assert spec["version"] == "neuralcd_grid_v1"
    assert spec["candidate_count"] == 45
    assert spec["existing_candidate_count"] == 5
    assert spec["new_candidate_count"] == 40
    assert spec["test_evaluated"] is False

    assert sha256(
        ROOT / "scripts/validate_neuralcd.py"
    ) == spec["validator_sha256"]

    assert sha256(
        ROOT / "scripts/validate_neuralcd_grid.py"
    ) == spec["wrapper_sha256"]

    reference = pd.read_parquet(
        BASE / "epoch_02/predictions.parquet",
        columns=["source_row", "observed_correct"],
    ).sort_values("source_row")

    expected_rows = reference["source_row"].to_numpy()
    expected_labels = reference[
        "observed_correct"
    ].to_numpy()

    assert len(expected_rows) == 42437

    LOGS.mkdir(parents=True, exist_ok=True)

    completed = 0
    reused = 0

    for candidate in spec["candidates"]:
        epoch = candidate["epoch"]
        lr = candidate["learning_rate"]
        penalty = candidate["prior_penalty"]

        if lr == 0.1 and penalty == 0.01:
            path = BASE / f"epoch_{epoch:02d}"

            verify(
                path,
                candidate,
                expected_rows,
                expected_labels,
            )

            reused += 1
            continue

        name = (
            f"lr{token(lr)}_"
            f"pen{token(penalty)}"
        )

        path = GRID / name / f"epoch_{epoch:02d}"

        if path.exists():
            # A previously completed run may be reused ONLY
            # after all checks pass.
            verify(
                path,
                candidate,
                expected_rows,
                expected_labels,
            )

            reused += 1
            print(
                "Verified existing candidate:",
                epoch, lr, penalty,
                flush=True,
            )
            continue

        command = [
            sys.executable,
            "-m",
            "scripts.validate_neuralcd_grid",
            "--epoch",
            str(epoch),
            "--lr",
            str(lr),
            "--penalty",
            str(penalty),
        ]

        log = LOGS / (
            f"epoch_{epoch:02d}_{name}.log"
        )

        print(
            "Running:",
            candidate,
            flush=True,
        )

        # Exclusive creation prevents accidental log replacement.
        with log.open("x", encoding="utf-8") as stream:
            subprocess.run(
                command,
                cwd=ROOT,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=True,
            )

        report = verify(
            path,
            candidate,
            expected_rows,
            expected_labels,
        )

        completed += 1

        print(
            f"Verified: epoch={epoch}, "
            f"lr={lr}, penalty={penalty}, "
            f"NLL={report['neuralcd']['nll']:.6f}",
            flush=True,
        )

    assert completed + reused == 45

    print("\nGRID COMPLETE")
    print("Newly evaluated:", completed)
    print("Verified existing:", reused)
    print("Total verified:", completed + reused)
    print("Test evaluated: False")


if __name__ == "__main__":
    main()
