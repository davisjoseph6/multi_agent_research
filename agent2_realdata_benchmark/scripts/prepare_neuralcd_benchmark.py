#!/usr/bin/env python3
"""Freeze NeuralCD eligibility and a matched BKT validation comparison."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from scripts.fit_bkt import metrics


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/assist2009"
SPLITS = ROOT / "data/splits/assist2009"
BKT = ROOT / "results/bkt"
OUTPUT = ROOT / "docs/data/neuralcd_readiness_v1.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(
            "Readiness v1 already exists. Do not silently overwrite it."
        )

    manifest = read_json(SPLITS / "manifest.json")
    frozen = read_json(ROOT / "docs/data/bkt_v1_frozen.json")

    canonical = DATA / "interactions.parquet"
    assignment_file = SPLITS / "assignments.parquet"
    prediction_file = BKT / "frozen_v1_validation_predictions.parquet"

    if sha256(canonical) != manifest["processed_sha256"]:
        raise RuntimeError("Canonical dataset checksum mismatch")

    if sha256(assignment_file) != manifest["assignment_sha256"]:
        raise RuntimeError("Split checksum mismatch")

    if frozen["split_assignment_sha256"] != manifest["assignment_sha256"]:
        raise RuntimeError("Frozen BKT uses another split")

    df = pd.read_parquet(
        canonical,
        columns=[
            "source_row", "student_id", "item_id",
            "event_order", "has_skill_annotation",
            "is_primary_target",
        ],
    )

    assignments = pd.read_parquet(
        assignment_file,
        columns=["source_row", "partition"],
    )

    df = df.merge(
        assignments,
        on="source_row",
        validate="one_to_one",
    )

    # Do not inspect test interactions in this development diagnostic.
    df = df.loc[
        df["partition"].isin(["train", "val"])
    ].copy()

    train = df.loc[df["partition"].eq("train")]

    train_items = set(
        train.loc[train["has_skill_annotation"], "item_id"]
    )

    train_primary_items = set(
        train.loc[train["is_primary_target"], "item_id"]
    )

    val = df.loc[
        df["partition"].eq("val")
    ].sort_values(
        ["student_id", "event_order"],
        kind="mergesort",
    ).copy()

    val["prior_tagged_events"] = (
        val.groupby("student_id")["has_skill_annotation"]
        .cumsum().astype(int)
        - val["has_skill_annotation"].astype(int)
    )

    targets = val.loc[
        val["is_primary_target"]
    ].copy()

    targets["item_seen_in_train"] = targets["item_id"].isin(
        train_items
    )

    predictions = pd.read_parquet(prediction_file)

    if not predictions["source_row"].is_unique:
        raise AssertionError("Duplicate BKT prediction identifiers")

    if set(predictions["source_row"]) != set(targets["source_row"]):
        raise AssertionError(
            "BKT predictions do not match validation targets"
        )

    scored = targets.merge(
        predictions,
        on=["source_row", "student_id"],
        validate="one_to_one",
    )

    if len(scored) != manifest["primary_target_counts"]["val"]:
        raise AssertionError("Validation target count mismatch")

    known = scored.loc[scored["item_seen_in_train"]].copy()
    unknown = scored.loc[~scored["item_seen_in_train"]].copy()

    def bkt_metrics(frame: pd.DataFrame) -> dict:
        records = list(
            frame[
                [
                    "source_row",
                    "student_id",
                    "observed_correct",
                    "predicted_probability",
                ]
            ].itertuples(index=False, name=None)
        )

        result, _ = metrics(records)
        return result

    report = {
        "dataset": manifest["dataset"],
        "split_assignment_sha256": manifest["assignment_sha256"],
        "frozen_bkt_version": frozen["version"],
        "frozen_prediction_sha256": sha256(prediction_file),
        "training_tagged_item_count": len(train_items),
        "training_primary_item_count": len(train_primary_items),
        "validation_students_with_targets": int(
            targets["student_id"].nunique()
        ),
        "validation_primary_targets": int(len(targets)),
        "known_item_targets": int(len(known)),
        "unseen_item_targets": int(len(unknown)),
        "distinct_unseen_items": int(
            unknown["item_id"].nunique()
        ),
        "known_item_target_fraction": float(
            len(known) / len(targets)
        ),
        "cold_start_targets_zero_prior_tagged": int(
            targets["prior_tagged_events"].eq(0).sum()
        ),
        "bkt_full_validation": bkt_metrics(scored),
        "bkt_known_item_matched_validation": bkt_metrics(known),
        "comparison_population": (
            "Validation primary targets whose item IDs have "
            "at least one skill-tagged training interaction"
        ),
        "test_partition_inspected": False,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    print("\nSaved:", OUTPUT)


if __name__ == "__main__":
    main()
