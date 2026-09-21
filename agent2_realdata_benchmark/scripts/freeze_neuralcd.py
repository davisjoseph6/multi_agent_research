#!/usr/bin/env python3
"""Freeze selected uncalibrated NeuralCD v1 without inspecting test data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/data"
DATA = ROOT / "data/processed/assist2009"
SPLITS = ROOT / "data/splits/assist2009"
TRAINING = ROOT / "results/neuralcd/full_train_v1"

SELECTED = (
    ROOT / "results/neuralcd/validation_grid_v1"
    / "lr0p1_pen0p1/epoch_02"
)

OUTPUT = DOCS / "neuralcd_v1_frozen.json"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(
            f"Frozen model already registered: {OUTPUT}"
        )

    manifest = read(SPLITS / "manifest.json")
    training = read(TRAINING / "run_report.json")
    selection = read(
        DOCS / "neuralcd_grid_selection_v1.json"
    )
    specification = read(
        DOCS / "neuralcd_grid_spec_v1.json"
    )
    history_audit = read(
        DOCS / "neuralcd_history_audit_v1.json"
    )
    history_access = read(
        DOCS / "neuralcd_history_access_v1.json"
    )
    calibration = read(
        DOCS / "neuralcd_calibration_diagnostics_v1.json"
    )
    readiness = read(
        DOCS / "neuralcd_readiness_v1.json"
    )

    require(
        training["status"] == "completed_training_only",
        "Training was not completed",
    )
    require(
        selection["candidates_verified"] == 45,
        "Grid was not fully verified",
    )
    require(
        specification["candidate_count"] == 45,
        "Registered grid changed",
    )
    require(
        selection["grid_spec_sha256"]
        == sha256(DOCS / "neuralcd_grid_spec_v1.json"),
        "Grid specification checksum mismatch",
    )

    chosen = selection["selected"]

    require(
        (
            chosen["epoch"],
            chosen["learning_rate"],
            chosen["prior_penalty"],
        ) == (2, 0.1, 0.1),
        "Unexpected selected configuration",
    )

    require(
        history_audit["status"]
        == "annotation_eligibility_consistent",
        "History eligibility audit failed",
    )
    require(
        history_audit["unannotated_but_currently_supported"] == 0,
        "Unsupported annotation history",
    )
    require(
        history_audit["tagged_but_empty_q"] == 0,
        "Annotated history has empty Q rows",
    )

    checkpoint_file = TRAINING / "epoch_02.pt"
    report_file = SELECTED / "report.json"
    predictions_file = SELECTED / "predictions.parquet"

    require(
        sha256(checkpoint_file) == chosen["checkpoint_sha256"],
        "Selected checkpoint changed",
    )
    require(
        sha256(report_file) == chosen["report_sha256"],
        "Selected validation report changed",
    )
    require(
        sha256(predictions_file) == chosen["predictions_sha256"],
        "Selected predictions changed",
    )

    report = read(report_file)

    require(
        report["status"] == "full_validation_candidate",
        "Incorrect validation run type",
    )
    require(
        report["global_weights_unchanged"] is True,
        "Validation altered global parameters",
    )
    require(
        report["test_evaluated"] is False,
        "Test lock not confirmed",
    )
    require(
        (
            report["epoch"],
            report["adaptation_learning_rate"],
            report["adaptation_prior_penalty"],
        ) == (2, 0.1, 0.1),
        "Validation configuration differs",
    )

    require(
        report["validation_students_processed"] == 633
        and report["primary_targets"] == 42748
        and report["matched_targets"] == 42437
        and report["unsupported_targets"] == 311,
        "Validation population mismatch",
    )

    np.testing.assert_allclose(
        report["neuralcd"]["nll"],
        chosen["validation_nll"],
        rtol=0,
        atol=1e-12,
    )

    require(
        history_access["selected_predictions_sha256"]
        == chosen["predictions_sha256"],
        "History analysis uses different predictions",
    )
    require(
        calibration["neural_predictions_sha256"]
        == chosen["predictions_sha256"],
        "Calibration analysis uses different predictions",
    )
    require(
        calibration["calibrator_fitted"] is False,
        "A calibration transformation was fitted",
    )
    require(
        calibration["test_evaluated"] is False
        and history_access["test_evaluated"] is False
        and selection["test_evaluated"] is False,
        "Test lock not confirmed in all reports",
    )

    q_file = DATA / "Q.npy"
    canonical = DATA / "interactions.parquet"
    assignments = SPLITS / "assignments.parquet"

    require(
        sha256(canonical) == manifest["processed_sha256"],
        "Processed data changed",
    )
    require(
        sha256(assignments) == manifest["assignment_sha256"],
        "Student split changed",
    )
    require(
        sha256(q_file) == training["q_sha256"],
        "Q-matrix changed",
    )

    require(
        report["split_assignment_sha256"]
        == manifest["assignment_sha256"],
        "Validation split mismatch",
    )

    require(
        sha256(
            ROOT
            / "results/bkt/frozen_v1_validation_predictions.parquet"
        ) == readiness["frozen_prediction_sha256"],
        "Frozen BKT predictions changed",
    )

    checkpoint = torch.load(
        checkpoint_file,
        map_location="cpu",
        weights_only=True,
    )

    require(
        checkpoint["training_run"] == "full_train_v1"
        and checkpoint["epoch"] == 2,
        "Incorrect checkpoint identity",
    )
    require(
        checkpoint["dimensions"] == {
            "students": 2951,
            "items": 26688,
            "concepts": 123,
        },
        "Unexpected architecture dimensions",
    )
    require(
        len(checkpoint["train_student_index"]) == 2951,
        "Training student map mismatch",
    )
    require(
        int(checkpoint["seen_item_mask"].sum()) == 17146,
        "Trained item coverage mismatch",
    )
    require(
        training["epoch_results"][1]["checkpoint_sha256"]
        == chosen["checkpoint_sha256"],
        "Training report checkpoint mismatch",
    )

    code_files = [
        "src/models/neuralcd.py",
        "src/evaluation/neuralcd_online.py",
        "src/evaluation/neuralcd_stream.py",
        "scripts/train_neuralcd.py",
        "scripts/validate_neuralcd.py",
        "scripts/validate_neuralcd_grid.py",
    ]

    code_hashes = {
        name: sha256(ROOT / name)
        for name in code_files
    }

    frozen = {
        "version": "neuralcd_v1",
        "status": "frozen_uncalibrated_baseline",
        "checkpoint_epoch": 2,
        "checkpoint_relative_path":
            "results/neuralcd/full_train_v1/epoch_02.pt",
        "checkpoint_sha256": chosen["checkpoint_sha256"],
        "training_students": 2951,
        "training_tagged_interactions": 188223,
        "trained_items": 17146,
        "adaptation": {
            "initialization":
                "mean training-student embedding logits",
            "optimizer": "SGD",
            "learning_rate": 0.1,
            "prior_penalty": 0.1,
            "updates_per_supported_observation": 1,
            "global_parameters_frozen": True,
            "update_timing": "after current response",
            "unsupported_items": "no prediction or update",
        },
        "calibration": {
            "transformation": "none",
            "descriptive_ece_10":
                calibration["full_population"][
                    "neuralcd"
                ]["calibration"]["ece_10_equal_width"],
            "diagnostics_sha256": sha256(
                DOCS / "neuralcd_calibration_diagnostics_v1.json"
            ),
        },
        "data_identity": {
            "processed_sha256": manifest["processed_sha256"],
            "split_assignment_sha256":
                manifest["assignment_sha256"],
            "q_sha256": training["q_sha256"],
        },
        "validation": {
            "matched_known_item_targets": 42437,
            "unsupported_primary_targets": 311,
            "nll": report["neuralcd"]["nll"],
            "brier": report["neuralcd"]["brier"],
            "accuracy_at_0_5":
                report["neuralcd"]["accuracy_at_0_5"],
            "roc_auc": report["neuralcd"]["roc_auc"],
            "predictions_sha256": chosen["predictions_sha256"],
            "report_sha256": chosen["report_sha256"],
            "selection_sha256": sha256(
                DOCS / "neuralcd_grid_selection_v1.json"
            ),
            "history_access_sha256": sha256(
                DOCS / "neuralcd_history_access_v1.json"
            ),
        },
        "source_code_sha256": code_hashes,
        "scientific_scope": (
            "Predicts observed binary responses; latent "
            "proficiency is not independently verified mastery."
        ),
        "test_evaluated": False,
        "test_permission": (
            "Not yet: final test protocol must be frozen separately."
        ),
    }

    OUTPUT.write_text(
        json.dumps(frozen, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("NEURALCD V1 FREEZE VERIFIED")
    print("Epoch:", frozen["checkpoint_epoch"])
    print("Learning rate:", frozen["adaptation"]["learning_rate"])
    print("Prior penalty:", frozen["adaptation"]["prior_penalty"])
    print("Validation NLL:", frozen["validation"]["nll"])
    print("Calibrator fitted: False")
    print("Test evaluated: False")
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
