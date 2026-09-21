#!/usr/bin/env python3
"""Audit annotation eligibility in validation histories; no test access."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow.dataset as ds
import torch

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/assist2009"
SPLITS = ROOT / "data/splits/assist2009"
OUT = ROOT / "docs/data/neuralcd_history_audit_v1.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if OUT.exists():
        raise FileExistsError(OUT)

    manifest = read(SPLITS / "manifest.json")
    canonical = DATA / "interactions.parquet"

    assert sha256(canonical) == manifest["processed_sha256"]

    students = read(SPLITS / "val_students.json")
    assert len(students) == 633

    checkpoint_path = (
        ROOT / "results/neuralcd/full_train_v1/epoch_02.pt"
    )

    checkpoint = torch.load(
        checkpoint_path,
        map_location="cpu",
        weights_only=True,
    )

    seen = checkpoint["seen_item_mask"].numpy().astype(bool)
    q = np.load(DATA / "Q.npy")

    assert seen.shape == (26688,)
    assert q.shape == (26688, 123)

    table = ds.dataset(
        str(canonical),
        format="parquet",
    ).to_table(
        columns=[
            "source_row",
            "student_id",
            "event_order",
            "item_idx",
            "has_skill_annotation",
            "is_primary_target",
        ],
        filter=ds.field("student_id").isin(students),
    )

    df = table.to_pandas()

    assert len(df) == 58525
    assert df["source_row"].is_unique
    assert df["has_skill_annotation"].notna().all()

    item = df["item_idx"].to_numpy(dtype=np.int64)
    tagged = df["has_skill_annotation"].to_numpy(dtype=bool)
    primary = df["is_primary_target"].to_numpy(dtype=bool)

    assert np.all((item >= 0) & (item < len(seen)))

    trained_item = seen[item]
    has_q = q[item].sum(axis=1) > 0
    currently_supported = trained_item & has_q

    # These are the interactions that the current evaluator
    # would use although their own annotation flag is false.
    questionable = (
        ~tagged & currently_supported
    )

    known_primary = primary & currently_supported

    assert int(primary.sum()) == 42748
    assert int(known_primary.sum()) == 42437

    # Count later scored targets belonging to a student with
    # at least one preceding questionable interaction.
    bad = df.loc[
        questionable,
        ["student_id", "event_order"],
    ]

    affected_later_targets = 0

    if len(bad):
        first_bad = (
            bad.groupby("student_id", as_index=False)[
                "event_order"
            ]
            .min()
            .rename(columns={
                "event_order": "first_questionable_order"
            })
        )

        later = df.loc[
            known_primary,
            ["student_id", "event_order"],
        ].merge(
            first_bad,
            on="student_id",
            how="inner",
        )

        affected_later_targets = int((
            later["event_order"]
            > later["first_questionable_order"]
        ).sum())

    report = {
        "status": (
            "annotation_eligibility_consistent"
            if not questionable.any()
            else "annotation_eligibility_discrepancy"
        ),
        "processed_sha256": sha256(canonical),
        "split_assignment_sha256":
            manifest["assignment_sha256"],
        "validation_interactions": len(df),
        "validation_primary_targets": int(primary.sum()),
        "known_primary_targets": int(known_primary.sum()),
        "unannotated_but_currently_supported": int(
            questionable.sum()
        ),
        "affected_students": int(
            df.loc[
                questionable, "student_id"
            ].nunique()
        ),
        "later_known_targets_potentially_affected":
            affected_later_targets,
        "tagged_but_empty_q": int(
            (tagged & ~has_q).sum()
        ),
        "test_evaluated": False,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)

    OUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    print("Saved:", OUT)

    if questionable.any():
        raise SystemExit(
            "STOP: annotation eligibility discrepancy found. "
            "Do not freeze the existing validation grid."
        )

    print("ANNOTATION ELIGIBILITY AUDIT PASSED")


if __name__ == "__main__":
    main()
