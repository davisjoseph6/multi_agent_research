#!/usr/bin/env python3
"""Build label-free validation signals from frozen BKT and NeuralCD.

Never accesses test data or response labels.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from src.uncertainty.bridge import signal_record


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/data"

BKT = (
    ROOT
    / "results/bkt/frozen_v1_validation_predictions.parquet"
)

NEURAL = (
    ROOT
    / "results/neuralcd/validation_grid_v1"
    / "lr0p1_pen0p1/epoch_02/predictions.parquet"
)

OUTPUT = (
    ROOT / "results/uncertainty/validation_signals_v1.parquet"
)

REPORT = DOCS / "uncertainty_validation_bridge_v1.json"

PROJECTION = [
    "source_row",
    "student_id",
    "predicted_probability",
]

SIGNAL_COLUMNS = [
    "source_row",
    "student_id",
    "model",
    "status",
    "p_correct",
    "failure_risk",
    "predictive_entropy_nats",
    "normalized_predictive_entropy",
]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def main():
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError(
            "Bridge artifact already exists; refusing to overwrite"
        )

    frozen = read_json(DOCS / "neuralcd_v1_frozen.json")
    selection = read_json(
        DOCS / "neuralcd_grid_selection_v1.json"
    )
    readiness = read_json(
        DOCS / "neuralcd_readiness_v1.json"
    )

    assert frozen["status"] == "frozen_uncalibrated_baseline"
    assert frozen["test_evaluated"] is False

    assert (
        frozen["validation"]["predictions_sha256"]
        == selection["selected"]["predictions_sha256"]
        == sha256(NEURAL)
    )

    assert sha256(BKT) == readiness[
        "frozen_prediction_sha256"
    ]

    assert frozen["checkpoint_epoch"] == 2
    assert frozen["adaptation"]["learning_rate"] == 0.1
    assert frozen["adaptation"]["prior_penalty"] == 0.1
    assert frozen["calibration"]["transformation"] == "none"

    # Column projection deliberately excludes observed outcomes.
    bkt = pd.read_parquet(
        BKT,
        columns=PROJECTION,
    )

    neural = pd.read_parquet(
        NEURAL,
        columns=PROJECTION,
    )

    assert list(bkt.columns) == PROJECTION
    assert list(neural.columns) == PROJECTION

    assert len(bkt) == 42748
    assert len(neural) == 42437

    assert bkt["source_row"].is_unique
    assert neural["source_row"].is_unique

    bkt["student_id"] = bkt["student_id"].astype(str)
    neural["student_id"] = neural["student_id"].astype(str)

    # Every NeuralCD target must be one of the eligible BKT targets.
    assert neural["source_row"].isin(
        bkt["source_row"]
    ).all()

    joined = bkt.merge(
        neural,
        on="source_row",
        how="left",
        validate="one_to_one",
        suffixes=("_bkt", "_neural"),
        indicator=True,
    ).sort_values("source_row").reset_index(drop=True)

    assert len(joined) == 42748

    matched = joined["_merge"].eq("both")
    missing = joined["_merge"].eq("left_only")

    assert int(matched.sum()) == 42437
    assert int(missing.sum()) == 311

    assert (
        joined.loc[matched, "student_id_bkt"].to_numpy()
        == joined.loc[matched, "student_id_neural"].to_numpy()
    ).all()

    assert joined.loc[
        missing, "predicted_probability_neural"
    ].isna().all()

    records = []
    matched_by_row = joined["_merge"].eq("both").to_numpy()

    for index, row in enumerate(joined.itertuples(index=False)):
        source = int(row.source_row)
        student = str(row.student_id_bkt)

        records.append(
            signal_record(
                source_row=source,
                student_id=student,
                model="bkt_v1",
                supported=True,
                probability=float(
                    row.predicted_probability_bkt
                ),
            )
        )

        if matched_by_row[index]:
            records.append(
                signal_record(
                    source_row=source,
                    student_id=student,
                    model="neuralcd_v1",
                    supported=True,
                    probability=float(
                        row.predicted_probability_neural
                    ),
                )
            )
        else:
            records.append(
                signal_record(
                    source_row=source,
                    student_id=student,
                    model="neuralcd_v1",
                    supported=False,
                    probability=None,
                )
            )

    signals = pd.DataFrame.from_records(
        records,
        columns=SIGNAL_COLUMNS,
    )

    assert len(signals) == 2 * 42748

    assert not signals.duplicated(
        ["source_row", "model"]
    ).any()

    assert set(signals.columns) == set(SIGNAL_COLUMNS)

    counts = signals.groupby(
        ["model", "status"]
    ).size().to_dict()

    assert counts == {
        ("bkt_v1", "supported"): 42748,
        ("neuralcd_v1", "supported"): 42437,
        ("neuralcd_v1", "unsupported_training_item"): 311,
    }

    value_columns = [
        "p_correct",
        "failure_risk",
        "predictive_entropy_nats",
        "normalized_predictive_entropy",
    ]

    unsupported = signals["status"].eq(
        "unsupported_training_item"
    )

    assert signals.loc[
        unsupported, value_columns
    ].isna().all().all()

    assert signals.loc[
        ~unsupported, value_columns
    ].notna().all().all()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    signals.to_parquet(
        OUTPUT,
        index=False,
    )

    # Verify serialization did not turn missing values into
    # artificial numeric predictions.
    saved = pd.read_parquet(OUTPUT)

    assert len(saved) == len(signals)
    assert list(saved.columns) == SIGNAL_COLUMNS

    saved_unsupported = saved["status"].eq(
        "unsupported_training_item"
    )

    assert int(saved_unsupported.sum()) == 311

    assert saved.loc[
        saved_unsupported, value_columns
    ].isna().all().all()

    report = {
        "version": "uncertainty_validation_bridge_v1",
        "status": "label_free_validation_signals",
        "source_columns_read": PROJECTION,
        "output_columns": SIGNAL_COLUMNS,
        "eligible_primary_targets": 42748,
        "total_signal_records": 85496,
        "bkt_supported": 42748,
        "neuralcd_supported": 42437,
        "neuralcd_unsupported": 311,
        "frozen_neuralcd_sha256": sha256(
            DOCS / "neuralcd_v1_frozen.json"
        ),
        "bkt_predictions_sha256": sha256(BKT),
        "neuralcd_predictions_sha256": sha256(NEURAL),
        "output_sha256": sha256(OUTPUT),
        "no_response_labels_read": True,
        "no_intervention_policy_applied": True,
        "test_evaluated": False,
    }

    REPORT.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    print("VALIDATION UNCERTAINTY BRIDGE VERIFIED")
    print("Eligible targets:", 42748)
    print("Total signal records:", len(saved))
    print("BKT supported:", 42748)
    print("NeuralCD supported:", 42437)
    print("NeuralCD unsupported:", 311)
    print("Response labels read: False")
    print("Test evaluated: False")
    print("Saved:", OUTPUT)
    print("Report:", REPORT)


if __name__ == "__main__":
    main()
