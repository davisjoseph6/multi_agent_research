#!/usr/bin/env python3
"""Build canonical interactions and a Q-matrix from corrected ASSISTments."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

SOURCE = (
    ROOT
    / "data/raw/assist2009"
    / "skill_builder_data_corrected_collapsed.csv"
)

OUTPUT = ROOT / "data/processed/assist2009"

REQUIRED = [
    "order_id",
    "user_id",
    "problem_id",
    "skill_id",
    "correct",
    "original",
    "first_action",
]


def parse_skills(value: object) -> list[str]:
    """Parse a missing or underscore-separated skill annotation."""
    if pd.isna(value) or not str(value).strip():
        return []

    tokens = str(value).strip().split("_")

    if any(not token.isascii() or not token.isdigit() for token in tokens):
        raise ValueError(f"Invalid skill annotation: {value!r}")

    return sorted({str(int(token)) for token in tokens}, key=int)


def sorted_ids(values) -> list[str]:
    """Produce a deterministic order for numeric and nonnumeric IDs."""
    def key(value: str):
        text = str(value)
        if text.isascii() and text.isdigit():
            return (0, int(text), text)
        return (1, text, text)

    return sorted({str(value) for value in values}, key=key)


def sha256(path: Path) -> str:
    """Calculate a file checksum without loading it all into memory."""
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def main() -> None:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)

    df = pd.read_csv(
        SOURCE,
        encoding="latin1",
        dtype="string",
        low_memory=False,
    )

    missing_columns = set(REQUIRED) - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    # Important: preserve original file-row identity.
    df["source_row"] = np.arange(len(df), dtype=np.int64)

    # Missing skill annotations are permitted; missing identifiers are not.
    for column in [
        "order_id", "user_id", "problem_id",
        "correct", "original", "first_action",
    ]:
        invalid = (
            df[column].isna()
            | df[column].str.strip().fillna("").eq("")
        )
        if invalid.any():
            raise ValueError(
                f"{column} has {int(invalid.sum())} missing values"
            )

    for column, allowed in [
        ("correct", {"0", "1"}),
        ("original", {"0", "1"}),
        ("first_action", {"0", "1", "2"}),
    ]:
        bad = ~df[column].isin(allowed)
        if bad.any():
            raise ValueError(
                f"Unexpected values in {column}: "
                f"{df.loc[bad, column].unique().tolist()}"
            )

    order = pd.to_numeric(df["order_id"], errors="coerce")

    if order.isna().any():
        raise ValueError("Some order IDs are not numeric")

    if order.duplicated().any():
        raise ValueError("Duplicate order IDs detected")

    df["event_order"] = order.astype(np.int64)

    # Each collapsed interaction remains exactly one record.
    df["concept_ids"] = df["skill_id"].map(parse_skills)

    df["has_skill_annotation"] = df["concept_ids"].map(
        lambda skills: len(skills) > 0
    )

    # A single question must have a consistent concept set.
    tagged = df.loc[df["has_skill_annotation"]].copy()

    tagged["skill_key"] = tagged["concept_ids"].map(tuple)

    variants = tagged.groupby("problem_id")["skill_key"].nunique()

    conflicts = variants[variants > 1]

    if not conflicts.empty:
        example_ids = conflicts.index[:10].tolist()

        examples = tagged.loc[
            tagged["problem_id"].isin(example_ids),
            ["problem_id", "skill_key"],
        ].drop_duplicates()

        print("Conflicting question-to-concept assignments:")
        print(examples.to_string(index=False))

        raise ValueError(
            f"{len(conflicts)} questions have conflicting skill sets. "
            "Investigate before building a Q-matrix."
        )

    students = sorted_ids(df["user_id"].unique())
    items = sorted_ids(df["problem_id"].unique())

    concept_set = set()

    for skills in tagged["concept_ids"]:
        concept_set.update(skills)

    concepts = sorted_ids(concept_set)

    student_index = {sid: i for i, sid in enumerate(students)}
    item_index = {qid: i for i, qid in enumerate(items)}
    concept_index = {cid: i for i, cid in enumerate(concepts)}

    # All questions receive a row.
    # An unannotated question has an all-zero row, NOT invented skills.
    Q = np.zeros(
        (len(items), len(concepts)),
        dtype=np.uint8,
    )

    unique_tagged_items = tagged.drop_duplicates(
        subset=["problem_id"]
    )

    for question_id, skills in unique_tagged_items[
        ["problem_id", "concept_ids"]
    ].itertuples(index=False, name=None):
        item_position = item_index[str(question_id)]

        for concept_id in skills:
            Q[item_position, concept_index[concept_id]] = 1

    primary_target = (
        df["original"].eq("1")
        & df["has_skill_annotation"]
    )

    # Canonical IDs and labels. The current outcome is a target,
    # never a feature available before the prediction.
    canonical = pd.DataFrame({
        "source_row": df["source_row"],
        "student_id": df["user_id"],
        "student_idx": df["user_id"].map(student_index).astype(np.int32),
        "item_id": df["problem_id"],
        "item_idx": df["problem_id"].map(item_index).astype(np.int32),
        "event_order": df["event_order"],
        "concept_ids": df["concept_ids"],
        "has_skill_annotation": df["has_skill_annotation"],
        "is_main_problem": df["original"].eq("1"),
        "is_primary_target": primary_target,
        "correct": df["correct"].astype(np.int8),
        "first_action": df["first_action"],
    })

    # Keep useful response metadata for analysis, not current-step
    # prediction features.
    for column in ["answer_type", "hint_count", "assistment_id"]:
        if column in df.columns:
            canonical[column] = df[column]

    canonical = canonical.sort_values(
        ["student_idx", "event_order"],
        kind="mergesort",
    ).reset_index(drop=True)

    OUTPUT.mkdir(parents=True, exist_ok=True)

    canonical.to_parquet(
        OUTPUT / "interactions.parquet",
        index=False,
    )

    np.save(OUTPUT / "Q.npy", Q)

    for filename, mapping in [
        ("student_index.json", student_index),
        ("item_index.json", item_index),
        ("concept_index.json", concept_index),
    ]:
        (OUTPUT / filename).write_text(
            json.dumps(mapping, indent=2),
            encoding="utf-8",
        )

    metadata = {
        "source": SOURCE.name,
        "source_sha256": sha256(SOURCE),
        "interactions": len(canonical),
        "students": len(students),
        "items": len(items),
        "concepts": len(concepts),
        "primary_target_rows": int(primary_target.sum()),
        "missing_skill_rows": int(
            (~df["has_skill_annotation"]).sum()
        ),
        "unannotated_items": int((Q.sum(axis=1) == 0).sum()),
        "q_shape": list(Q.shape),
    }

    (OUTPUT / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(metadata, indent=2))
    print("\nSaved canonical dataset to:", OUTPUT)


if __name__ == "__main__":
    main()
