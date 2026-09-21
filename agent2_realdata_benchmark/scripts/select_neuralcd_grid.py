#!/usr/bin/env python3
"""Verify all registered candidates and record minimum-NLL selection."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/data"
BASE = ROOT / "results/neuralcd/validation_v1"
GRID = ROOT / "results/neuralcd/validation_grid_v1"
TRAINING = ROOT / "results/neuralcd/full_train_v1"
OUT = DOCS / "neuralcd_grid_selection_v1.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def token(value):
    return format(value, "g").replace(".", "p")


def main():
    if OUT.exists():
        raise FileExistsError(OUT)

    audit = read(DOCS / "neuralcd_history_audit_v1.json")
    assert audit["status"] == "annotation_eligibility_consistent"
    assert audit["unannotated_but_currently_supported"] == 0
    assert audit["tagged_but_empty_q"] == 0
    assert audit["test_evaluated"] is False

    spec_path = DOCS / "neuralcd_grid_spec_v1.json"
    spec = read(spec_path)

    assert spec["version"] == "neuralcd_grid_v1"
    assert spec["candidate_count"] == 45
    assert len(spec["candidates"]) == 45
    assert spec["test_evaluated"] is False

    assert sha256(
        ROOT / "scripts/validate_neuralcd.py"
    ) == spec["validator_sha256"]

    assert sha256(
        ROOT / "scripts/validate_neuralcd_grid.py"
    ) == spec["wrapper_sha256"]

    training_path = TRAINING / "run_report.json"
    training = read(training_path)

    assert sha256(training_path) == (
        spec["training_report_sha256"]
    )

    assert training["status"] == "completed_training_only"

    reference = pd.read_parquet(
        BASE / "epoch_02/predictions.parquet"
    ).sort_values("source_row").reset_index(drop=True)

    identity_columns = [
        "source_row",
        "student_id",
        "event_order",
        "item_idx",
        "observed_correct",
        "prior_supported_observations",
    ]

    assert len(reference) == 42437
    assert reference["source_row"].is_unique

    reference_bkt = read(
        BASE / "epoch_02/report.json"
    )["matched_bkt"]

    previous = {
        row["epoch"]: row
        for row in spec["reference_results"]
    }

    records = []

    for candidate in spec["candidates"]:
        epoch = candidate["epoch"]
        lr = candidate["learning_rate"]
        penalty = candidate["prior_penalty"]

        reused = (lr == 0.1 and penalty == 0.01)

        directory = (
            BASE / f"epoch_{epoch:02d}"
            if reused else
            GRID / (
                f"lr{token(lr)}_pen{token(penalty)}"
            ) / f"epoch_{epoch:02d}"
        )

        report_file = directory / "report.json"
        predictions_file = directory / "predictions.parquet"

        report = read(report_file)

        assert report["status"] == "full_validation_candidate"
        assert report["epoch"] == epoch
        assert report["adaptation_learning_rate"] == lr
        assert report["adaptation_prior_penalty"] == penalty

        assert report["validation_students_processed"] == 633
        assert report["primary_targets"] == 42748
        assert report["matched_targets"] == 42437
        assert report["unsupported_targets"] == 311
        assert report["global_weights_unchanged"] is True
        assert report["test_evaluated"] is False

        expected_checkpoint = training[
            "epoch_results"
        ][epoch - 1]["checkpoint_sha256"]

        assert report["checkpoint_sha256"] == expected_checkpoint

        assert sha256(predictions_file) == (
            report["predictions_sha256"]
        )

        if reused:
            assert sha256(report_file) == (
                previous[epoch]["report_sha256"]
            )
            assert report["predictions_sha256"] == (
                previous[epoch]["predictions_sha256"]
            )

        df = pd.read_parquet(
            predictions_file
        ).sort_values("source_row").reset_index(drop=True)

        assert len(df) == 42437
        assert df["source_row"].is_unique

        for column in identity_columns:
            np.testing.assert_array_equal(
                df[column].to_numpy(),
                reference[column].to_numpy(),
            )

        p = df["predicted_probability"].to_numpy(
            dtype=np.float64
        )

        y = df["observed_correct"].to_numpy(
            dtype=np.float64
        )

        assert np.isfinite(p).all()
        assert np.all((p > 0) & (p < 1))

        computed_nll = -np.mean(
            y * np.log(p)
            + (1 - y) * np.log1p(-p)
        )

        np.testing.assert_allclose(
            computed_nll,
            report["neuralcd"]["nll"],
            atol=1e-10,
            rtol=0,
        )

        for metric in (
            "nll", "brier",
            "accuracy_at_0_5", "roc_auc",
        ):
            np.testing.assert_allclose(
                report["matched_bkt"][metric],
                reference_bkt[metric],
                atol=1e-10,
                rtol=0,
            )

        records.append({
            **candidate,
            "validation_nll": report["neuralcd"]["nll"],
            "validation_brier": report["neuralcd"]["brier"],
            "validation_auc": report["neuralcd"]["roc_auc"],
            "checkpoint_sha256": report["checkpoint_sha256"],
            "predictions_sha256": report["predictions_sha256"],
            "report_sha256": sha256(report_file),
            "reused_reference": reused,
        })

    assert len(records) == 45

    ranked = sorted(
        records,
        key=lambda row: (
            row["validation_nll"],
            row["epoch"],
            row["learning_rate"],
            row["prior_penalty"],
        ),
    )

    selected = ranked[0]

    assert selected["epoch"] == 2
    assert selected["learning_rate"] == 0.1
    assert selected["prior_penalty"] == 0.1

    result = {
        "version": "neuralcd_grid_selection_v1",
        "status": "selected_on_validation_not_test",
        "selection_rule": spec["selection_metric"],
        "grid_spec_sha256": sha256(spec_path),
        "history_audit_sha256": sha256(
            DOCS / "neuralcd_history_audit_v1.json"
        ),
        "runner_sha256": sha256(
            ROOT / "scripts/run_neuralcd_grid.py"
        ),
        "candidates_verified": len(records),
        "matched_targets": 42437,
        "selected": selected,
        "runner_up": ranked[1],
        "nll_gap_to_runner_up": (
            ranked[1]["validation_nll"]
            - selected["validation_nll"]
        ),
        "matched_bkt": reference_bkt,
        "all_candidates": records,
        "test_evaluated": False,
        "limitations": (
            "Selected using validation outcomes across 45 "
            "configurations; validation metrics are development "
            "estimates, not independent test performance."
        ),
    }

    OUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("ALL 45 CONFIGURATIONS VERIFIED")
    print("\nSELECTED:")
    print(json.dumps(selected, indent=2))
    print("\nRUNNER-UP:")
    print(json.dumps(ranked[1], indent=2))
    print(
        "\nNLL gap:",
        result["nll_gap_to_runner_up"],
    )
    print("Test evaluated: False")
    print("Saved:", OUT)


if __name__ == "__main__":
    main()
