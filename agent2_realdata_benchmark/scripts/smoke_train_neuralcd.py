#!/usr/bin/env python3
"""Training-only NeuralCD smoke test. No validation or test outcomes."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from src.models.neuralcd import NeuralCDM


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/assist2009"
SPLITS = ROOT / "data/splits/assist2009"
OUTPUT = ROOT / "results/neuralcd"

SEED = 7
BATCH_SIZE = 256
LEARNING_RATE = 0.002
MAX_BATCHES = 3
RUN_ID = "smoke_three_batches_v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024), b""
        ):
            digest.update(block)

    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", RUN_ID):
        raise ValueError("Unsafe run ID")

    torch.manual_seed(SEED)
    np.random.seed(SEED)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)

    manifest = read_json(SPLITS / "manifest.json")
    metadata = read_json(DATA / "metadata.json")

    interactions_path = DATA / "interactions.parquet"
    assignments_path = SPLITS / "assignments.parquet"
    student_file = SPLITS / "train_students.json"
    q_path = DATA / "Q.npy"

    if sha256(interactions_path) != manifest["processed_sha256"]:
        raise RuntimeError("Canonical dataset checksum changed")

    if sha256(assignments_path) != manifest["assignment_sha256"]:
        raise RuntimeError("Frozen split checksum changed")

    if metadata["source_sha256"] != manifest["source_sha256"]:
        raise RuntimeError("Dataset identity mismatch")

    train_students = read_json(student_file)

    if len(train_students) != manifest["student_counts"]["train"]:
        raise RuntimeError("Incorrect training-student count")

    if len(set(train_students)) != len(train_students):
        raise RuntimeError("Duplicate training student IDs")

    # Read ONLY rows belonging to training students.
    table = ds.dataset(
        str(interactions_path),
        format="parquet",
    ).to_table(
        columns=[
            "source_row",
            "student_id",
            "item_idx",
            "correct",
            "has_skill_annotation",
            "is_primary_target",
        ],
        filter=ds.field("student_id").isin(train_students),
    )

    train = table.to_pandas()

    if len(train) != manifest["interaction_counts"]["train"]:
        raise RuntimeError("Training interaction count mismatch")

    if train["student_id"].nunique() != len(train_students):
        raise RuntimeError("Unexpected training student IDs")

    # Independently check membership against the frozen assignments.
    assignments = pd.read_parquet(
        assignments_path,
        columns=["source_row", "partition"],
    )

    assigned_train_rows = set(
        assignments.loc[
            assignments["partition"].eq("train"),
            "source_row",
        ].astype(int)
    )

    if set(train["source_row"].astype(int)) != assigned_train_rows:
        raise RuntimeError("Training rows differ from frozen assignments")

    if int(train["is_primary_target"].sum()) != (
        manifest["primary_target_counts"]["train"]
    ):
        raise RuntimeError("Primary-target count mismatch")

    # Retain tagged training interactions, including scaffolding.
    tagged = train.loc[
        train["has_skill_annotation"]
    ].copy()

    if tagged.empty:
        raise RuntimeError("No annotated training interactions")

    q = np.load(q_path)

    if q.ndim != 2 or list(q.shape) != metadata["q_shape"]:
        raise RuntimeError("Q-matrix dimensions mismatch")

    if not np.isin(q, [0, 1]).all():
        raise RuntimeError("Q-matrix must be binary")

    # Compact mapping: validation students receive NO training embedding.
    student_index = {
        str(student): i
        for i, student in enumerate(train_students)
    }

    student_ids = tagged["student_id"].astype(str).map(
        student_index
    )

    if student_ids.isna().any():
        raise RuntimeError("A nontraining student entered the dataset")

    student_ids = student_ids.to_numpy(dtype=np.int64)
    item_ids = tagged["item_idx"].to_numpy(dtype=np.int64)
    labels = tagged["correct"].to_numpy(dtype=np.float32)

    if np.any(item_ids < 0) or np.any(item_ids >= len(q)):
        raise RuntimeError("Item ID out of range")

    if not np.isin(labels, [0.0, 1.0]).all():
        raise RuntimeError("Invalid labels")

    if np.any(q[item_ids].sum(axis=1) == 0):
        raise RuntimeError("Unannotated item in training examples")

    seen_item_mask = np.zeros(q.shape[0], dtype=np.bool_)
    seen_item_mask[np.unique(item_ids)] = True

    dataset = TensorDataset(
        torch.from_numpy(student_ids),
        torch.from_numpy(item_ids),
        torch.from_numpy(labels),
    )

    generator = torch.Generator().manual_seed(SEED)

    loader = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        generator=generator,
        num_workers=0,
    )

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    model = NeuralCDM(
        n_students=len(train_students),
        n_items=q.shape[0],
        n_concepts=q.shape[1],
    ).to(device)

    q_tensor = torch.as_tensor(
        q,
        dtype=torch.float32,
        device=device,
    )

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE,
    )

    criterion = nn.BCELoss()

    checkpoint = OUTPUT / f"{RUN_ID}.pt"
    report_file = OUTPUT / f"{RUN_ID}.json"

    if checkpoint.exists() or report_file.exists():
        raise FileExistsError(
            "This smoke run already exists; do not overwrite it."
        )

    model.train()

    losses = []
    examples_processed = 0

    for step, (students, items, outcomes) in enumerate(loader):
        if step >= MAX_BATCHES:
            break

        students = students.to(device)
        items = items.to(device)
        outcomes = outcomes.to(device).unsqueeze(1)

        masks = q_tensor[items]

        optimizer.zero_grad(set_to_none=True)

        predictions = model(students, items, masks)
        loss = criterion(predictions, outcomes)

        if not torch.isfinite(loss):
            raise RuntimeError("Nonfinite training loss")

        loss.backward()
        optimizer.step()

        # Required for the monotonic prediction-network constraint.
        model.apply_clipper()

        losses.append(float(loss.detach().cpu()))
        examples_processed += int(students.shape[0])

        print(
            f"Update {step + 1}: "
            f"batch_size={len(students)}, "
            f"BCE={losses[-1]:.6f}",
            flush=True,
        )

    if len(losses) != MAX_BATCHES:
        raise RuntimeError("Smoke test did not finish all updates")

    for layer in (
        model.prednet_full1,
        model.prednet_full2,
        model.prednet_full3,
    ):
        if torch.any(layer.weight < 0):
            raise RuntimeError("Nonnegativity constraint violated")

    # Check inference on training examples only.
    model.eval()

    sample_students = torch.from_numpy(
        student_ids[:8]
    ).to(device)

    sample_items = torch.from_numpy(
        item_ids[:8]
    ).to(device)

    with torch.no_grad():
        sample_predictions = model(
            sample_students,
            sample_items,
            q_tensor[sample_items],
        )

    if (
        not torch.isfinite(sample_predictions).all()
        or torch.any(sample_predictions <= 0)
        or torch.any(sample_predictions >= 1)
    ):
        raise RuntimeError("Invalid inference probabilities")

    OUTPUT.mkdir(parents=True, exist_ok=True)

    torch.save({
        "model_state_dict": model.state_dict(),
        "train_student_index": student_index,
        "seen_item_mask": torch.from_numpy(seen_item_mask),
        "dimensions": {
            "students": len(train_students),
            "items": int(q.shape[0]),
            "concepts": int(q.shape[1]),
        },
        "configuration": {
            "seed": SEED,
            "batch_size": BATCH_SIZE,
            "learning_rate": LEARNING_RATE,
            "completed_updates": len(losses),
            "run_type": "incomplete_smoke_test",
        },
    }, checkpoint)

    report = {
        "run_id": RUN_ID,
        "status": "smoke_test_only_not_a_trained_baseline",
        "device": str(device),
        "torch_version": torch.__version__,
        "source_sha256": manifest["source_sha256"],
        "processed_sha256": manifest["processed_sha256"],
        "split_assignment_sha256": (
            manifest["assignment_sha256"]
        ),
        "q_sha256": sha256(q_path),
        "training_students": len(train_students),
        "training_interactions": len(train),
        "tagged_training_interactions": len(tagged),
        "unique_trained_items": int(seen_item_mask.sum()),
        "completed_optimizer_updates": len(losses),
        "examples_processed": examples_processed,
        "batch_losses": losses,
        "checkpoint_sha256": sha256(checkpoint),
        "validation_evaluated": False,
        "test_evaluated": False,
    }

    report_file.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("\n=== NEURALCD TRAINING SMOKE TEST ===")
    print(json.dumps(report, indent=2))
    print("\nCheckpoint:", checkpoint)
    print("Report:", report_file)


if __name__ == "__main__":
    main()
