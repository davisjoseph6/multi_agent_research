#!/usr/bin/env python3
"""Audit BKT-only history exposure on validation, without test access.

This is a prefix-restriction sensitivity analysis. It does NOT
recompute BKT states after removing unsupported interactions.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import torch
from sklearn.metrics import roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/assist2009"
SPLITS = ROOT / "data/splits/assist2009"
DOCS = ROOT / "docs/data"

NEURAL = (
    ROOT
    / "results/neuralcd/validation_grid_v1"
    / "lr0p1_pen0p1/epoch_02/predictions.parquet"
)

BKT = (
    ROOT
    / "results/bkt/frozen_v1_validation_predictions.parquet"
)

CHECKPOINT = (
    ROOT / "results/neuralcd/full_train_v1/epoch_02.pt"
)

OUT = DOCS / "neuralcd_history_access_v1.json"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024), b""
        ):
            digest.update(block)
    return digest.hexdigest()


def model_metrics(frame: pd.DataFrame, column: str) -> dict:
    y = frame["correct"].to_numpy(dtype=np.int64)
    p = frame[column].to_numpy(dtype=np.float64)

    if len(y) == 0:
        raise RuntimeError("Empty comparison population")

    if not np.isin(y, [0, 1]).all():
        raise RuntimeError("Invalid outcome")

    if (
        not np.isfinite(p).all()
        or np.any(p <= 0)
        or np.any(p >= 1)
    ):
        raise RuntimeError("Invalid probability")

    nll = -np.mean(
        y * np.log(p) + (1 - y) * np.log1p(-p)
    )

    auc = (
        float(roc_auc_score(y, p))
        if len(np.unique(y)) == 2
        else None
    )

    return {
        "nll": float(nll),
        "brier": float(np.mean((p - y) ** 2)),
        "accuracy_at_0_5": float(
            np.mean((p >= 0.5) == y)
        ),
        "roc_auc": auc,
    }


def main() -> None:
    if OUT.exists():
        raise FileExistsError(
            f"Historical audit must not be overwritten: {OUT}"
        )

    manifest = read(SPLITS / "manifest.json")
    audit = read(DOCS / "neuralcd_history_audit_v1.json")
    selection = read(DOCS / "neuralcd_grid_selection_v1.json")
    readiness = read(DOCS / "neuralcd_readiness_v1.json")

    assert audit["status"] == "annotation_eligibility_consistent"
    assert selection["candidates_verified"] == 45
    assert selection["test_evaluated"] is False

    chosen = selection["selected"]

    assert chosen["epoch"] == 2
    assert chosen["learning_rate"] == 0.1
    assert chosen["prior_penalty"] == 0.1

    assert sha256(NEURAL) == chosen["predictions_sha256"]
    assert sha256(BKT) == readiness["frozen_prediction_sha256"]

    canonical = DATA / "interactions.parquet"
    q_file = DATA / "Q.npy"

    assert sha256(canonical) == manifest["processed_sha256"]

    checkpoint = torch.load(
        CHECKPOINT,
        map_location="cpu",
        weights_only=True,
    )

    assert sha256(CHECKPOINT) == chosen["checkpoint_sha256"]

    seen = checkpoint["seen_item_mask"].numpy().astype(bool)
    q = np.load(q_file)

    assert q.shape == (26688, 123)
    assert seen.shape == (26688,)

    students = read(SPLITS / "val_students.json")
    assert len(students) == 633

    # Read validation-student interactions only.
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
            "has_skill_annotation",
            "is_primary_target",
        ],
        filter=ds.field("student_id").isin(students),
    )

    df = table.to_pandas()
    df["student_id"] = df["student_id"].astype(str)

    assert len(df) == 58525
    assert df["source_row"].is_unique
    assert df["student_id"].nunique() == 633

    if df.duplicated(["student_id", "event_order"]).any():
        raise RuntimeError("Ambiguous chronological order")

    df = df.sort_values(
        ["student_id", "event_order"],
        kind="mergesort",
    ).reset_index(drop=True)

    items = df["item_idx"].to_numpy(dtype=np.int64)

    if np.any(items < 0) or np.any(items >= len(seen)):
        raise RuntimeError("Item index outside frozen Q-matrix")

    tagged = df["has_skill_annotation"].to_numpy(dtype=bool)
    primary = df["is_primary_target"].to_numpy(dtype=bool)

    has_q = q[items].sum(axis=1) > 0

    # BKT can use these tagged observations through their concepts,
    # but NeuralCD cannot update via an untrained item embedding.
    bkt_only = tagged & has_q & ~seen[items]

    df["bkt_only_history_event"] = bkt_only.astype(np.int64)

    # Cumulative count EXCLUDES the current event.
    df["prior_bkt_only_events"] = (
        df.groupby("student_id", sort=False)[
            "bkt_only_history_event"
        ].cumsum()
        - df["bkt_only_history_event"]
    ).astype(np.int64)

    assert np.all(df["prior_bkt_only_events"] >= 0)

    known_primary = primary & tagged & has_q & seen[items]

    assert int(primary.sum()) == 42748
    assert int(known_primary.sum()) == 42437

    targets = df.loc[
        known_primary,
        [
            "source_row",
            "student_id",
            "correct",
            "prior_bkt_only_events",
        ],
    ].copy()

    neural = pd.read_parquet(
        NEURAL,
        columns=[
            "source_row",
            "student_id",
            "observed_correct",
            "predicted_probability",
        ],
    ).rename(columns={
        "observed_correct": "neural_label",
        "predicted_probability": "neural_probability",
    })

    bkt = pd.read_parquet(
        BKT,
        columns=[
            "source_row",
            "student_id",
            "observed_correct",
            "predicted_probability",
        ],
    ).rename(columns={
        "observed_correct": "bkt_label",
        "predicted_probability": "bkt_probability",
    })

    neural["student_id"] = neural["student_id"].astype(str)
    bkt["student_id"] = bkt["student_id"].astype(str)

    assert neural["source_row"].is_unique
    assert bkt["source_row"].is_unique

    joined = targets.merge(
        neural,
        on=["source_row", "student_id"],
        how="inner",
        validate="one_to_one",
    ).merge(
        bkt,
        on=["source_row", "student_id"],
        how="inner",
        validate="one_to_one",
    )

    assert len(joined) == len(targets) == len(neural) == 42437
    assert joined["source_row"].is_unique

    np.testing.assert_array_equal(
        joined["correct"].to_numpy(),
        joined["neural_label"].to_numpy(),
    )

    np.testing.assert_array_equal(
        joined["correct"].to_numpy(),
        joined["bkt_label"].to_numpy(),
    )

    groups = {
        "all_matched": joined,
        "clean_prefix": joined.loc[
            joined["prior_bkt_only_events"] == 0
        ],
        "one_or_more_bkt_only_history_events": joined.loc[
            joined["prior_bkt_only_events"] > 0
        ],
    }

    results = {}

    for name, frame in groups.items():
        if frame.empty:
            results[name] = {"count": 0}
            continue

        neural_metrics = model_metrics(
            frame, "neural_probability"
        )

        bkt_metrics = model_metrics(
            frame, "bkt_probability"
        )

        results[name] = {
            "count": int(len(frame)),
            "students": int(frame["student_id"].nunique()),
            "positive_fraction": float(frame["correct"].mean()),
            "neuralcd": neural_metrics,
            "bkt": bkt_metrics,
            "nll_gain_bkt_minus_neuralcd": (
                bkt_metrics["nll"] - neural_metrics["nll"]
            ),
            "brier_gain_bkt_minus_neuralcd": (
                bkt_metrics["brier"] - neural_metrics["brier"]
            ),
        }

    assert (
        results["clean_prefix"]["count"]
        + results["one_or_more_bkt_only_history_events"]["count"]
        == 42437
    )

    reference_report = read(
        NEURAL.parent / "report.json"
    )

    for model, key in (
        ("neuralcd", "neuralcd"),
        ("bkt", "matched_bkt"),
    ):
        for metric in ("nll", "brier", "accuracy_at_0_5", "roc_auc"):
            np.testing.assert_allclose(
                results["all_matched"][model][metric],
                reference_report[key][metric],
                atol=1e-10,
                rtol=0,
            )

    report = {
        "status": "validation_history_access_sensitivity",
        "selected_predictions_sha256": sha256(NEURAL),
        "bkt_predictions_sha256": sha256(BKT),
        "split_assignment_sha256": manifest["assignment_sha256"],
        "validation_students": 633,
        "validation_interactions": len(df),
        "bkt_only_history_events": int(bkt_only.sum()),
        "students_with_bkt_only_history": int(
            df.loc[bkt_only, "student_id"].nunique()
        ),
        "groups": results,
        "interpretation": (
            "Clean-prefix targets have zero earlier tagged events "
            "that BKT can use but NeuralCD cannot. This restricts "
            "the comparison population; it does not recompute BKT "
            "states for exposed targets."
        ),
        "test_evaluated": False,
    }

    OUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    print("\nSaved:", OUT)


if __name__ == "__main__":
    main()
