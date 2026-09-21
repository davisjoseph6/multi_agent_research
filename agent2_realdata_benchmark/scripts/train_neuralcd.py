#!/usr/bin/env python3
"""Train NeuralCDM on frozen training students; save every epoch.

No validation or test responses are loaded.
This script does not select a final checkpoint.
"""

from __future__ import annotations

import hashlib
import json
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
OUTPUT = ROOT / "results/neuralcd/full_train_v1"

SEED = 7
EPOCHS = 5
BATCH_SIZE = 256
LEARNING_RATE = 0.002
FIXED_SAMPLE_SIZE = 2048


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024), b""
        ):
            digest.update(chunk)

    return digest.hexdigest()


def save_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(".tmp")

    temporary.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    temporary.replace(path)


def load_training_data():
    """Load only training-student response records."""
    manifest = read_json(SPLITS / "manifest.json")
    metadata = read_json(DATA / "metadata.json")

    canonical = DATA / "interactions.parquet"
    assignment_file = SPLITS / "assignments.parquet"
    q_file = DATA / "Q.npy"

    if sha256(canonical) != manifest["processed_sha256"]:
        raise RuntimeError("Canonical dataset checksum mismatch")

    if sha256(assignment_file) != manifest["assignment_sha256"]:
        raise RuntimeError("Frozen assignment checksum mismatch")

    if metadata["source_sha256"] != manifest["source_sha256"]:
        raise RuntimeError("Raw dataset identity mismatch")

    train_students = read_json(
        SPLITS / "train_students.json"
    )

    if (
        len(train_students)
        != manifest["student_counts"]["train"]
        or len(set(train_students)) != len(train_students)
    ):
        raise RuntimeError("Invalid training-student membership")

    table = ds.dataset(
        str(canonical),
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
        raise RuntimeError("Training student coverage mismatch")

    assignments = pd.read_parquet(
        assignment_file,
        columns=["source_row", "partition"],
    )

    expected_rows = set(
        assignments.loc[
            assignments["partition"].eq("train"),
            "source_row",
        ].astype(int)
    )

    actual_rows = set(train["source_row"].astype(int))

    if actual_rows != expected_rows:
        raise RuntimeError("Frozen training rows do not match")

    if train["source_row"].duplicated().any():
        raise RuntimeError("Duplicate training source rows")

    if int(train["is_primary_target"].sum()) != (
        manifest["primary_target_counts"]["train"]
    ):
        raise RuntimeError("Training target count mismatch")

    tagged = train.loc[
        train["has_skill_annotation"]
    ].copy()

    if len(tagged) != 188223:
        raise RuntimeError(
            "Unexpected tagged training count for frozen v1 data"
        )

    q = np.load(q_file)

    if q.ndim != 2 or list(q.shape) != metadata["q_shape"]:
        raise RuntimeError("Q-matrix dimensions mismatch")

    if not np.isin(q, [0, 1]).all():
        raise RuntimeError("Q-matrix is not binary")

    student_index = {
        str(student): index
        for index, student in enumerate(train_students)
    }

    mapped = tagged["student_id"].astype(str).map(
        student_index
    )

    if mapped.isna().any():
        raise RuntimeError("Unexpected student in training data")

    # Explicit copies prevent PyTorch's non-writable NumPy warning.
    student_ids = np.array(
        mapped,
        dtype=np.int64,
        copy=True,
    )

    item_ids = np.array(
        tagged["item_idx"],
        dtype=np.int64,
        copy=True,
    )

    labels = np.array(
        tagged["correct"],
        dtype=np.float32,
        copy=True,
    )

    if not (
        student_ids.flags.writeable
        and item_ids.flags.writeable
        and labels.flags.writeable
    ):
        raise RuntimeError("Training arrays must be writable")

    if (
        np.any(item_ids < 0)
        or np.any(item_ids >= q.shape[0])
    ):
        raise RuntimeError("Out-of-range item index")

    if not np.isin(labels, [0.0, 1.0]).all():
        raise RuntimeError("Nonbinary training label")

    if np.any(q[item_ids].sum(axis=1) == 0):
        raise RuntimeError("Unannotated training question")

    seen = np.zeros(q.shape[0], dtype=np.bool_)
    seen[np.unique(item_ids)] = True

    return {
        "student_ids": student_ids,
        "item_ids": item_ids,
        "labels": labels,
        "q": q,
        "seen": seen,
        "student_index": student_index,
        "manifest": manifest,
        "q_sha256": sha256(q_file),
        "tagged_source_rows": np.array(
            tagged["source_row"],
            dtype=np.int64,
            copy=True,
        ),
    }


@torch.no_grad()
def fixed_diagnostic(
    model,
    students,
    items,
    labels,
    q_tensor,
):
    """Evaluate an unchanged sample with dropout disabled."""
    model.eval()

    probabilities = model(
        students,
        items,
        q_tensor[items],
    ).reshape(-1)

    raw = probabilities.detach().double()
    targets = labels.detach().double()

    if not torch.isfinite(raw).all():
        raise RuntimeError("Nonfinite fixed-sample predictions")

    # Cast to float64 BEFORE clipping exact float32 endpoints.
    p = raw.clamp(1e-12, 1.0 - 1e-12)

    loss = -(
        targets * torch.log(p)
        + (1.0 - targets) * torch.log1p(-p)
    ).mean()

    return {
        "fixed_sample_clipped_nll": float(loss.cpu()),
        "mean_probability": float(raw.mean().cpu()),
        "minimum_probability": float(raw.min().cpu()),
        "maximum_probability": float(raw.max().cpu()),
        "fraction_below_0_01": float(
            (raw < 0.01).float().mean().cpu()
        ),
        "fraction_above_0_99": float(
            (raw > 0.99).float().mean().cpu()
        ),
        "exact_zero_count": int(
            (raw == 0).sum().cpu()
        ),
        "exact_one_count": int(
            (raw == 1).sum().cpu()
        ),
    }


def main():
    # Prevent accidental overwriting of an earlier experiment.
    if OUTPUT.exists():
        raise FileExistsError(
            f"Training run already exists: {OUTPUT}"
        )

    torch.manual_seed(SEED)
    np.random.seed(SEED)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)

    data = load_training_data()

    dataset = TensorDataset(
        torch.from_numpy(data["student_ids"]),
        torch.from_numpy(data["item_ids"]),
        torch.from_numpy(data["labels"]),
    )

    shuffle_generator = torch.Generator().manual_seed(SEED)

    loader = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        generator=shuffle_generator,
        num_workers=0,
    )

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    q = data["q"]

    q_tensor = torch.as_tensor(
        q,
        dtype=torch.float32,
        device=device,
    )

    model = NeuralCDM(
        n_students=len(data["student_index"]),
        n_items=q.shape[0],
        n_concepts=q.shape[1],
    ).to(device)

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE,
    )

    criterion = nn.BCELoss()

    fixed_generator = torch.Generator().manual_seed(
        SEED + 1
    )

    fixed_indices = torch.randperm(
        len(dataset),
        generator=fixed_generator,
    )[:FIXED_SAMPLE_SIZE]

    fixed_students = dataset.tensors[0][
        fixed_indices
    ].to(device)

    fixed_items = dataset.tensors[1][
        fixed_indices
    ].to(device)

    fixed_labels = dataset.tensors[2][
        fixed_indices
    ].to(device)

    fixed_rows = data["tagged_source_rows"][
        fixed_indices.numpy()
    ]

    fixed_sample_sha256 = hashlib.sha256(
        fixed_rows.tobytes()
    ).hexdigest()

    report = {
        "run_id": "full_train_v1",
        "status": "training_in_progress",
        "dataset": data["manifest"]["dataset"],
        "source_sha256": data["manifest"]["source_sha256"],
        "processed_sha256": data["manifest"]["processed_sha256"],
        "split_assignment_sha256": (
            data["manifest"]["assignment_sha256"]
        ),
        "q_sha256": data["q_sha256"],
        "seed": SEED,
        "torch_version": torch.__version__,
        "device": str(device),
        "epochs_planned": EPOCHS,
        "batch_size": BATCH_SIZE,
        "optimizer": "Adam",
        "learning_rate": LEARNING_RATE,
        "training_students": len(data["student_index"]),
        "tagged_training_examples": len(dataset),
        "unique_trained_items": int(
            data["seen"].sum()
        ),
        "fixed_sample_size": len(fixed_indices),
        "fixed_sample_source_rows_sha256":
            fixed_sample_sha256,
        "epoch_results": [],
        "validation_evaluated": False,
        "test_evaluated": False,
    }

    OUTPUT.mkdir(parents=True, exist_ok=False)

    baseline = fixed_diagnostic(
        model,
        fixed_students,
        fixed_items,
        fixed_labels,
        q_tensor,
    )

    report["before_training"] = baseline

    save_json(OUTPUT / "run_report.json", report)

    print("Device:", device, flush=True)
    print("Training examples:", len(dataset), flush=True)
    print("Unique trained items:", int(data["seen"].sum()), flush=True)
    print("Initial fixed sample:", baseline, flush=True)

    for epoch in range(1, EPOCHS + 1):
        model.train()

        total_loss = 0.0
        examples = 0
        batches = 0

        for students, items, labels in loader:
            students = students.to(device)
            items = items.to(device)
            labels = labels.to(device).unsqueeze(1)

            optimizer.zero_grad(set_to_none=True)

            predictions = model(
                students,
                items,
                q_tensor[items],
            )

            loss = criterion(predictions, labels)

            if not torch.isfinite(loss):
                raise RuntimeError(
                    f"Epoch {epoch}: nonfinite training loss"
                )

            loss.backward()

            optimizer.step()

            # Preserve the NeuralCD nonnegative-weight constraint.
            model.apply_clipper()

            size = len(students)

            total_loss += float(loss.detach().cpu()) * size
            examples += size
            batches += 1

        if examples != len(dataset):
            raise RuntimeError("Incomplete training epoch")

        for parameter in model.parameters():
            if not torch.isfinite(parameter).all():
                raise RuntimeError("Nonfinite trained parameter")

        for layer in (
            model.prednet_full1,
            model.prednet_full2,
            model.prednet_full3,
        ):
            if torch.any(layer.weight < 0):
                raise RuntimeError(
                    "Prediction-network weight constraint violated"
                )

        diagnostic = fixed_diagnostic(
            model,
            fixed_students,
            fixed_items,
            fixed_labels,
            q_tensor,
        )

        checkpoint_path = OUTPUT / f"epoch_{epoch:02d}.pt"

        if checkpoint_path.exists():
            raise FileExistsError(checkpoint_path)

        checkpoint = {
            "model_state_dict": model.state_dict(),
            "train_student_index": data["student_index"],
            "seen_item_mask": torch.from_numpy(
                data["seen"].copy()
            ),
            "dimensions": {
                "students": len(data["student_index"]),
                "items": int(q.shape[0]),
                "concepts": int(q.shape[1]),
            },
            "epoch": epoch,
            "training_run": "full_train_v1",
            "source_sha256": report["source_sha256"],
            "processed_sha256": report["processed_sha256"],
            "split_assignment_sha256":
                report["split_assignment_sha256"],
            "q_sha256": report["q_sha256"],
            "configuration": {
                "seed": SEED,
                "batch_size": BATCH_SIZE,
                "learning_rate": LEARNING_RATE,
                "epochs_planned": EPOCHS,
            },
        }

        temporary_checkpoint = checkpoint_path.with_suffix(
            ".tmp"
        )

        torch.save(checkpoint, temporary_checkpoint)
        temporary_checkpoint.replace(checkpoint_path)

        epoch_record = {
            "epoch": epoch,
            "examples_processed": examples,
            "batches": batches,
            "mean_training_bce": total_loss / examples,
            "fixed_sample": diagnostic,
            "checkpoint": checkpoint_path.name,
            "checkpoint_sha256": sha256(checkpoint_path),
        }

        report["epoch_results"].append(epoch_record)

        # Save progress after every completed epoch.
        save_json(OUTPUT / "run_report.json", report)

        print(
            f"Epoch {epoch}/{EPOCHS}: "
            f"training_BCE={epoch_record['mean_training_bce']:.6f}; "
            f"fixed_NLL={diagnostic['fixed_sample_clipped_nll']:.6f}; "
            f"p<0.01={diagnostic['fraction_below_0_01']:.3f}; "
            f"p>0.99={diagnostic['fraction_above_0_99']:.3f}",
            flush=True,
        )

    report["status"] = "completed_training_only"
    save_json(OUTPUT / "run_report.json", report)

    print("\nTRAINING COMPLETED")
    print("Epoch checkpoints:", len(report["epoch_results"]))
    print("Report:", OUTPUT / "run_report.json")
    print("Validation evaluated: False")
    print("Test evaluated: False")


if __name__ == "__main__":
    main()
