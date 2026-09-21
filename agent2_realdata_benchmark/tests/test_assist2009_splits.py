#!/usr/bin/env python3
"""Integrity tests for frozen ASSISTments unseen-student splits."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data/processed/assist2009"
SPLITS = ROOT / "data/splits/assist2009"


def sha256(path: Path) -> str:
    """Calculate a file checksum."""
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


@pytest.fixture(scope="module")
def artifacts():
    """Load canonical interactions and frozen split files."""
    interactions = pd.read_parquet(
        PROCESSED / "interactions.parquet"
    )

    assignments = pd.read_parquet(
        SPLITS / "assignments.parquet"
    )

    manifest = json.loads(
        (SPLITS / "manifest.json").read_text(encoding="utf-8")
    )

    groups = {
        partition: set(json.loads(
            (
                SPLITS / f"{partition}_students.json"
            ).read_text(encoding="utf-8")
        ))
        for partition in ("train", "val", "test")
    }

    return interactions, assignments, manifest, groups


def test_student_disjointness(artifacts):
    """No student appears in two partitions."""
    df, assignments, manifest, groups = artifacts

    assert groups["train"].isdisjoint(groups["val"])
    assert groups["train"].isdisjoint(groups["test"])
    assert groups["val"].isdisjoint(groups["test"])

    assert set.union(*groups.values()) == set(
        df["student_id"].astype(str)
    )

    assert len(groups["train"]) == 2951
    assert len(groups["val"]) == 633
    assert len(groups["test"]) == 633

    assert manifest["students"] == 4217


def test_every_interaction_assigned_once(artifacts):
    """All 346860 original interactions remain assigned."""
    df, assignments, manifest, groups = artifacts

    assert len(assignments) == len(df) == 346860

    assert assignments["source_row"].is_unique

    assert set(assignments["source_row"]) == set(
        df["source_row"]
    )

    assert assignments["partition"].notna().all()

    assert set(assignments["partition"].unique()) == {
        "train", "val", "test"
    }

    assert manifest["interactions"] == len(df)


def test_assignments_match_student_membership(artifacts):
    """Each record belongs to its student's frozen partition."""
    df, assignments, manifest, groups = artifacts

    mapping = {
        student: partition
        for partition, students in groups.items()
        for student in students
    }

    actual = assignments["student_id"].astype(str).map(mapping)

    assert actual.notna().all()
    assert actual.equals(assignments["partition"])

    per_student = assignments.groupby(
        "student_id"
    )["partition"].nunique()

    assert (per_student == 1).all()


def test_target_flags_and_counts(artifacts):
    """Primary target flags remain unchanged after splitting."""
    df, assignments, manifest, groups = artifacts

    original = df.set_index("source_row")[
        "is_primary_target"
    ].astype(bool)

    split_flags = assignments.set_index("source_row")[
        "is_primary_target"
    ].astype(bool)

    assert original.sort_index().equals(
        split_flags.sort_index()
    )

    assert int(split_flags.sum()) == 259399

    for partition in groups:
        mask = assignments["partition"].eq(partition)

        assert int(mask.sum()) == (
            manifest["interaction_counts"][partition]
        )

        assert int(
            assignments.loc[mask, "is_primary_target"].sum()
        ) == manifest["primary_target_counts"][partition]


def test_frozen_source_checksums(artifacts):
    """Split manifest identifies the canonical source."""
    df, assignments, manifest, groups = artifacts

    assert manifest["processed_sha256"] == sha256(
        PROCESSED / "interactions.parquet"
    )

    assert manifest["assignment_sha256"] == sha256(
        SPLITS / "assignments.parquet"
    )
