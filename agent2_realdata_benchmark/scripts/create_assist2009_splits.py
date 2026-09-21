#!/usr/bin/env python3
"""Create reproducible, student-disjoint ASSISTments data partitions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data/processed/assist2009"
OUTPUT = ROOT / "data/splits/assist2009"

SEED = 7
TRAIN_RATIO = 0.70
VALIDATION_RATIO = 0.15
TEST_RATIO = 0.15


def sha256(path: Path) -> str:
    """Return the SHA-256 checksum of a file."""
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def write_json(path: Path, obj: object) -> None:
    """Write deterministic, human-readable JSON."""
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """Split all students, then assign every interaction accordingly."""
    interactions_path = PROCESSED / "interactions.parquet"
    metadata_path = PROCESSED / "metadata.json"

    if not interactions_path.is_file():
        raise FileNotFoundError(interactions_path)

    if not metadata_path.is_file():
        raise FileNotFoundError(metadata_path)

    df = pd.read_parquet(interactions_path)

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    required = {
        "source_row",
        "student_id",
        "is_primary_target",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing canonical columns: {sorted(missing)}")

    if df["source_row"].duplicated().any():
        raise ValueError("Duplicate source_row values")

    if df["student_id"].isna().any():
        raise ValueError("Missing student IDs")

    students = sorted(df["student_id"].astype(str).unique().tolist())
    n_students = len(students)

    if n_students != int(metadata["students"]):
        raise ValueError("Student count disagrees with processed metadata")

    if len(df) != int(metadata["interactions"]):
        raise ValueError("Interaction count disagrees with metadata")

    if not np.isclose(
        TRAIN_RATIO + VALIDATION_RATIO + TEST_RATIO,
        1.0,
    ):
        raise ValueError("Split ratios must sum to one")

    rng = np.random.default_rng(SEED)

    shuffled = [
        str(student_id)
        for student_id in rng.permutation(students).tolist()
    ]

    n_test = round(n_students * TEST_RATIO)
    n_val = round(n_students * VALIDATION_RATIO)
    n_train = n_students - n_test - n_val

    train = sorted(shuffled[:n_train])
    val = sorted(shuffled[n_train:n_train + n_val])
    test = sorted(shuffled[n_train + n_val:])

    sets = {
        "train": set(train),
        "val": set(val),
        "test": set(test),
    }

    if sets["train"] & sets["val"]:
        raise AssertionError("Train/validation student leakage")

    if sets["train"] & sets["test"]:
        raise AssertionError("Train/test student leakage")

    if sets["val"] & sets["test"]:
        raise AssertionError("Validation/test student leakage")

    if set(students) != set.union(*sets.values()):
        raise AssertionError("Some students are missing")

    mapping = {
        student_id: partition
        for partition, student_ids in sets.items()
        for student_id in student_ids
    }

    assignments = pd.DataFrame({
        "source_row": df["source_row"].astype("int64"),
        "student_id": df["student_id"].astype(str),
        "partition": df["student_id"].astype(str).map(mapping),
        "is_primary_target": df["is_primary_target"].astype(bool),
    })

    if assignments["partition"].isna().any():
        raise AssertionError("Unassigned interactions")

    # Prevent an existing frozen split from being silently replaced
    # by a different seed, source dataset or student membership.
    existing_manifest = OUTPUT / "manifest.json"

    if existing_manifest.exists():
        previous = json.loads(
            existing_manifest.read_text(encoding="utf-8")
        )

        expected_identity = {
            "seed": SEED,
            "source_sha256": metadata["source_sha256"],
            "students": n_students,
            "student_counts": {
                "train": len(train),
                "val": len(val),
                "test": len(test),
            },
        }

        for key, expected in expected_identity.items():
            if previous.get(key) != expected:
                raise RuntimeError(
                    f"Existing split differs in {key}. "
                    "Do not silently overwrite a frozen split."
                )

        for partition, student_ids in [
            ("train", train),
            ("val", val),
            ("test", test),
        ]:
            existing_file = OUTPUT / f"{partition}_students.json"

            existing_ids = json.loads(
                existing_file.read_text(encoding="utf-8")
            )

            if existing_ids != student_ids:
                raise RuntimeError(
                    f"Existing {partition} student membership differs"
                )

    OUTPUT.mkdir(parents=True, exist_ok=True)

    for partition, student_ids in [
        ("train", train),
        ("val", val),
        ("test", test),
    ]:
        write_json(
            OUTPUT / f"{partition}_students.json",
            student_ids,
        )

    assignments.to_parquet(
        OUTPUT / "assignments.parquet",
        index=False,
    )

    student_counts = {
        partition: len(ids)
        for partition, ids in [
            ("train", train),
            ("val", val),
            ("test", test),
        ]
    }

    interaction_counts = {
        partition: int(
            (assignments["partition"] == partition).sum()
        )
        for partition in sets
    }

    primary_target_counts = {
        partition: int(
            (
                (assignments["partition"] == partition)
                & assignments["is_primary_target"]
            ).sum()
        )
        for partition in sets
    }

    manifest = {
        "dataset": "assist2009_corrected_collapsed",
        "purpose": "primary_unseen_student_evaluation",
        "seed": SEED,
        "source_sha256": metadata["source_sha256"],
        "processed_sha256": sha256(interactions_path),
        "students": n_students,
        "interactions": len(assignments),
        "student_counts": student_counts,
        "interaction_counts": interaction_counts,
        "primary_target_counts": primary_target_counts,
        "ratios": {
            "train": TRAIN_RATIO,
            "val": VALIDATION_RATIO,
            "test": TEST_RATIO,
        },
        "assignment_sha256": sha256(
            OUTPUT / "assignments.parquet"
        ),
    }

    write_json(OUTPUT / "manifest.json", manifest)

    print(json.dumps(manifest, indent=2))
    print("\nStudent-disjoint splits saved to:", OUTPUT)


if __name__ == "__main__":
    main()
