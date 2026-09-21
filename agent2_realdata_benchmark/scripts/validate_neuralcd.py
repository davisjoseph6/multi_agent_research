#!/usr/bin/env python3
"""Causal validation of completed NeuralCD training checkpoints.

Only validation-student response histories are loaded.
Global NeuralCD weights remain frozen.
No test responses are loaded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import torch

from scripts.fit_bkt import metrics
from src.evaluation.neuralcd_online import OnlineStudentAdapter
from src.evaluation.neuralcd_stream import (
    Interaction,
    evaluate_histories,
)
from src.models.neuralcd import NeuralCDM


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/assist2009"
SPLITS = ROOT / "data/splits/assist2009"
TRAINING = ROOT / "results/neuralcd/full_train_v1"
OUTPUT = ROOT / "results/neuralcd/validation_v1"
BKT = ROOT / "results/bkt/frozen_v1_validation_predictions.parquet"
READINESS = ROOT / "docs/data/neuralcd_readiness_v1.json"

ADAPTATION_LR = 0.1
PRIOR_PENALTY = 0.01


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024), b""
        ):
            digest.update(chunk)

    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--epoch",
        type=int,
        choices=range(1, 6),
        required=True,
    )

    parser.add_argument(
        "--max-students",
        type=int,
        default=None,
        help="Integration test only; omit for full validation.",
    )

    args = parser.parse_args()

    if (
        args.max_students is not None
        and args.max_students < 1
    ):
        parser.error("--max-students must be positive")

    mode = (
        "integration_only"
        if args.max_students is not None
        else "full_validation_candidate"
    )

    run_name = f"epoch_{args.epoch:02d}"

    if args.max_students is not None:
        run_name += f"_smoke_{args.max_students}students"

    output_dir = OUTPUT / run_name

    if output_dir.exists():
        raise FileExistsError(
            f"Existing run would be overwritten: {output_dir}"
        )

    manifest = read_json(SPLITS / "manifest.json")
    training = read_json(TRAINING / "run_report.json")
    readiness = read_json(READINESS)

    if training["status"] != "completed_training_only":
        raise RuntimeError("Training run is not complete")

    if len(training["epoch_results"]) != 5:
        raise RuntimeError("Expected five completed epochs")

    for record in (training, readiness):
        if record["split_assignment_sha256"] != (
            manifest["assignment_sha256"]
        ):
            raise RuntimeError("Split identity mismatch")

    canonical = DATA / "interactions.parquet"
    q_path = DATA / "Q.npy"
    assignment_path = SPLITS / "assignments.parquet"

    if sha256(canonical) != manifest["processed_sha256"]:
        raise RuntimeError("Canonical dataset checksum mismatch")

    if sha256(assignment_path) != manifest[
        "assignment_sha256"
    ]:
        raise RuntimeError("Frozen assignments checksum mismatch")

    if sha256(q_path) != training["q_sha256"]:
        raise RuntimeError("Q-matrix checksum mismatch")

    if sha256(BKT) != readiness[
        "frozen_prediction_sha256"
    ]:
        raise RuntimeError("Frozen BKT predictions changed")

    epoch_record = training[
        "epoch_results"
    ][args.epoch - 1]

    if epoch_record["epoch"] != args.epoch:
        raise RuntimeError("Checkpoint epoch mismatch")

    checkpoint_path = TRAINING / epoch_record["checkpoint"]

    if sha256(checkpoint_path) != epoch_record[
        "checkpoint_sha256"
    ]:
        raise RuntimeError("Checkpoint checksum mismatch")

    val_students = read_json(
        SPLITS / "val_students.json"
    )

    train_students = read_json(
        SPLITS / "train_students.json"
    )

    val_ids = {str(value) for value in val_students}
    train_ids = {str(value) for value in train_students}

    if val_ids & train_ids:
        raise RuntimeError("Training/validation student overlap")

    if len(val_ids) != manifest["student_counts"]["val"]:
        raise RuntimeError("Validation membership count mismatch")

    # Read only validation students' interactions.
    table = ds.dataset(
        str(canonical),
        format="parquet",
    ).to_table(
        columns=[
            "source_row",
            "student_id",
            "event_order",
            "item_idx",
            "correct",
            "is_primary_target",
        ],
        filter=ds.field("student_id").isin(val_students),
    )

    df = table.to_pandas()

    df["student_id"] = df["student_id"].astype(str)

    if set(df["student_id"]) != val_ids:
        raise RuntimeError("Validation student membership mismatch")

    if len(df) != manifest["interaction_counts"]["val"]:
        raise RuntimeError("Validation interaction count mismatch")

    if int(df["is_primary_target"].sum()) != (
        manifest["primary_target_counts"]["val"]
    ):
        raise RuntimeError("Validation target count mismatch")

    if df["source_row"].duplicated().any():
        raise RuntimeError("Duplicate validation source rows")

    df = df.sort_values(
        ["student_id", "event_order"],
        kind="mergesort",
    )

    checkpoint = torch.load(
        checkpoint_path,
        map_location="cpu",
        weights_only=True,
    )

    if checkpoint["epoch"] != args.epoch:
        raise RuntimeError("Loaded checkpoint is from wrong epoch")

    if checkpoint["training_run"] != "full_train_v1":
        raise RuntimeError("Incorrect training run")

    if checkpoint["split_assignment_sha256"] != (
        manifest["assignment_sha256"]
    ):
        raise RuntimeError("Checkpoint split mismatch")

    if checkpoint["q_sha256"] != training["q_sha256"]:
        raise RuntimeError("Checkpoint Q-matrix mismatch")

    dims = checkpoint["dimensions"]

    if dims != {
        "students": 2951,
        "items": 26688,
        "concepts": 123,
    }:
        raise RuntimeError("Unexpected checkpoint dimensions")

    if set(checkpoint["train_student_index"]) != train_ids:
        raise RuntimeError("Checkpoint student index mismatch")

    q = np.load(q_path)

    if q.shape != (dims["items"], dims["concepts"]):
        raise RuntimeError("Q-matrix shape mismatch")

    seen = checkpoint[
        "seen_item_mask"
    ].cpu().numpy().astype(bool, copy=True)

    if seen.shape != (dims["items"],):
        raise RuntimeError("Invalid trained-item mask")

    if int(seen.sum()) != training["unique_trained_items"]:
        raise RuntimeError("Trained-item coverage mismatch")

    device = (
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    model = NeuralCDM(
        n_students=dims["students"],
        n_items=dims["items"],
        n_concepts=dims["concepts"],
    )

    model.load_state_dict(
        checkpoint["model_state_dict"],
        strict=True,
    )

    model = model.to(device)
    model.eval()
    model.requires_grad_(False)

    # Capture global weights to check that adaptation never changes them.
    global_before = {
        name: value.detach().cpu().clone()
        for name, value in model.state_dict().items()
    }

    # Choose students with eligible targets for the integration run.
    # This uses target metadata, not correctness labels.
    if args.max_students is not None:
        eligible_ids = sorted(
            df.loc[
                df["is_primary_target"],
                "student_id",
            ].unique()
        )

        selected_ids = set(
            eligible_ids[:args.max_students]
        )

        df = df.loc[
            df["student_id"].isin(selected_ids)
        ].copy()

        if not selected_ids:
            raise RuntimeError("No eligible integration students")

    histories = {}

    for student_id, group in df.groupby(
        "student_id",
        sort=True,
    ):
        histories[student_id] = [
            Interaction(
                student_id=str(row.student_id),
                source_row=int(row.source_row),
                event_order=int(row.event_order),
                item_idx=int(row.item_idx),
                correct=int(row.correct),
                is_primary_target=bool(row.is_primary_target),
            )
            for row in group.itertuples(index=False)
        ]

    def make_adapter():
        return OnlineStudentAdapter(
            model=model,
            q_matrix=q,
            seen_item_mask=seen,
            learning_rate=ADAPTATION_LR,
            prior_penalty=PRIOR_PENALTY,
            device=device,
        )

    print(
        "Evaluating epoch:", args.epoch,
        "| mode:", mode,
        "| students:", len(histories),
        "| device:", device,
        flush=True,
    )

    rows, summaries = evaluate_histories(
        histories,
        make_adapter,
    )

    for name, value in model.state_dict().items():
        if not torch.equal(
            global_before[name],
            value.detach().cpu(),
        ):
            raise RuntimeError(
                f"Global parameter changed: {name}"
            )

    predictions = pd.DataFrame(rows)

    if predictions.empty:
        raise RuntimeError("No scored predictions")

    if predictions["source_row"].duplicated().any():
        raise RuntimeError("Duplicate prediction rows")

    targets = df.loc[
        df["is_primary_target"]
    ].copy()

    if np.any(
        q[targets["item_idx"].to_numpy(
            dtype=np.int64
        )].sum(axis=1) == 0
    ):
        raise RuntimeError("Unannotated primary target")

    expected_known = targets.loc[
        seen[
            targets["item_idx"].to_numpy(
                dtype=np.int64
            )
        ]
    ]

    expected_unknown = (
        len(targets) - len(expected_known)
    )

    if set(predictions["source_row"]) != set(
        expected_known["source_row"]
    ):
        raise RuntimeError(
            "NeuralCD targets differ from expected known-item targets"
        )

    if sum(
        summary["primary_targets"]
        for summary in summaries
    ) != len(targets):
        raise RuntimeError("Primary-target accounting mismatch")

    if sum(
        summary["unsupported_targets"]
        for summary in summaries
    ) != expected_unknown:
        raise RuntimeError("Unsupported-target count mismatch")

    frozen_bkt = pd.read_parquet(BKT)

    matched = predictions.merge(
        frozen_bkt.rename(columns={
            "observed_correct": "bkt_label",
            "predicted_probability": "bkt_probability",
        })[
            [
                "source_row",
                "student_id",
                "bkt_label",
                "bkt_probability",
            ]
        ],
        on=["source_row", "student_id"],
        how="inner",
        validate="one_to_one",
    )

    if len(matched) != len(predictions):
        raise RuntimeError("Missing BKT matched predictions")

    if not np.array_equal(
        matched["observed_correct"].to_numpy(),
        matched["bkt_label"].to_numpy(),
    ):
        raise RuntimeError("NeuralCD/BKT labels differ")

    neural_records = list(
        matched[
            [
                "source_row",
                "student_id",
                "observed_correct",
                "predicted_probability",
            ]
        ].itertuples(index=False, name=None)
    )

    bkt_records = list(
        matched[
            [
                "source_row",
                "student_id",
                "bkt_label",
                "bkt_probability",
            ]
        ].itertuples(index=False, name=None)
    )

    neural_metrics, _ = metrics(neural_records)
    bkt_metrics, _ = metrics(bkt_records)

    if args.max_students is None:
        if len(targets) != 42748:
            raise RuntimeError("Full target count mismatch")

        if len(predictions) != 42437:
            raise RuntimeError("Full known-item count mismatch")

        if expected_unknown != 311:
            raise RuntimeError("Unseen-item count mismatch")

        reference = readiness[
            "bkt_known_item_matched_validation"
        ]

        for key in ("nll", "brier", "roc_auc"):
            if not np.isclose(
                bkt_metrics[key],
                reference[key],
                atol=1e-10,
                rtol=0,
            ):
                raise RuntimeError(
                    f"Matched BKT metric differs: {key}"
                )

    report = {
        "status": mode,
        "epoch": args.epoch,
        "checkpoint_sha256": sha256(checkpoint_path),
        "split_assignment_sha256": (
            manifest["assignment_sha256"]
        ),
        "device": device,
        "adaptation_learning_rate": ADAPTATION_LR,
        "adaptation_prior_penalty": PRIOR_PENALTY,
        "validation_students_processed": len(histories),
        "primary_targets": int(len(targets)),
        "matched_targets": int(len(predictions)),
        "unsupported_targets": int(expected_unknown),
        "neuralcd": neural_metrics,
        "matched_bkt": bkt_metrics,
        "global_weights_unchanged": True,
        "test_evaluated": False,
    }

    output_dir.mkdir(parents=True, exist_ok=False)

    prediction_path = output_dir / "predictions.parquet"

    predictions.to_parquet(
        prediction_path,
        index=False,
    )

    report["predictions_sha256"] = sha256(
        prediction_path
    )

    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("\n=== NEURALCD VALIDATION REPORT ===")
    print(json.dumps(report, indent=2))
    print("\nSaved:", output_dir)


if __name__ == "__main__":
    main()
