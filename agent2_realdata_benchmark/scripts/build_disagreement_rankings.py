#!/usr/bin/env python3
"""Build all registered disagreement rankings without response labels."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.uncertainty.disagreement import (
    candidate_scores,
    rank_indices,
)


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/data"
RESULTS = ROOT / "results/uncertainty"

SPEC_FILE = DOCS / "disagreement_experiment_v1.json"

SIGNALS_FILE = RESULTS / "validation_signals_v1.parquet"

OUTPUT = RESULTS / "disagreement_rankings_v1.parquet"
REPORT = DOCS / "disagreement_rankings_v1.json"

PROJECTION = [
    "source_row",
    "student_id",
    "model",
    "status",
    "p_correct",
]

SOURCE_PATHS = {
    "signals": SIGNALS_FILE,
    "bridge": DOCS / "uncertainty_validation_bridge_v1.json",
    "bkt_freeze": DOCS / "bkt_v1_frozen.json",
    "neuralcd_freeze": DOCS / "neuralcd_v1_frozen.json",
    "event_freeze": DOCS / "event_detection_v1_frozen.json",
    "event_structure_audit":
        DOCS / "event_detection_structure_audit_v1.json",
    "predictive_interface":
        ROOT / "src/uncertainty/predictive.py",
    "test_gate": ROOT / "docs/phase6_test_gate_v1.md",
}

EXPECTED_IDS = [
    "neuralcd_risk",
    "bkt_risk",
    "mean_risk",
    "max_risk",
    "neuralcd_risk_plus_disagreement_a0.25",
    "neuralcd_risk_plus_disagreement_a0.5",
    "neuralcd_risk_plus_disagreement_a1",
    "neuralcd_risk_plus_disagreement_a2",
]


def read(path):
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


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError(
            "Disagreement ranking artifacts already exist"
        )

    spec = read(SPEC_FILE)

    require(
        spec["status"]
        == "registered_before_disagreement_outcome_analysis",
        "Incorrect experiment status",
    )

    require(
        spec["individual_response_labels_read"] is False
        and spec["test_evaluated"] is False
        and spec["test_gate"] == "closed",
        "Experimental access conditions changed",
    )

    require(
        spec["matched_targets"] == 42437
        and spec["unsupported_neuralcd_targets"] == 311,
        "Unexpected population",
    )

    require(
        spec["alert_counts"] == {
            "0.1": 4243,
            "0.2": 8487,
            "0.3": 12731,
        },
        "Registered alert counts changed",
    )

    registered_ids = [
        item["id"]
        for item in spec["candidate_scores"]
    ]

    require(
        spec["candidate_count"] == 8
        and registered_ids == EXPECTED_IDS,
        "Unexpected candidate registration",
    )

    require(
        [item["alpha"] for item in spec["candidate_scores"]]
        == [0.0, None, None, None, 0.25, 0.5, 1.0, 2.0],
        "Registered disagreement coefficients changed",
    )

    require(
        set(spec["source_sha256"]) == set(SOURCE_PATHS),
        "Source registry changed",
    )

    for name, path in SOURCE_PATHS.items():
        require(
            sha256(path) == spec["source_sha256"][name],
            f"Registered source changed: {name}",
        )

    bridge = read(SOURCE_PATHS["bridge"])

    require(
        bridge["output_sha256"] == sha256(SIGNALS_FILE),
        "Signal dataset changed",
    )

    require(
        bridge["no_response_labels_read"] is True
        and bridge["test_evaluated"] is False,
        "Invalid signal provenance",
    )

    # LABEL-FREE PHASE: load only the five declared columns.
    signals = pd.read_parquet(
        SIGNALS_FILE,
        columns=PROJECTION,
    )

    require(
        list(signals.columns) == PROJECTION
        and len(signals) == 85496,
        "Unexpected signal schema or size",
    )

    require(
        not signals.duplicated(
            ["source_row", "model"]
        ).any(),
        "Duplicate model-target signals",
    )

    bkt = signals.loc[
        signals["model"].eq("bkt_v1")
    ].copy()

    neural = signals.loc[
        signals["model"].eq("neuralcd_v1")
    ].copy()

    require(
        len(bkt) == len(neural) == 42748,
        "Unexpected model coverage",
    )

    require(
        bkt["status"].eq("supported").all(),
        "Unsupported BKT targets",
    )

    unsupported = neural["status"].eq(
        "unsupported_training_item"
    )

    require(
        int(unsupported.sum()) == 311
        and neural.loc[
            unsupported, "p_correct"
        ].isna().all(),
        "NeuralCD abstention mismatch",
    )

    supported_neural = neural.loc[
        neural["status"].eq("supported")
    ].copy()

    require(
        len(supported_neural) == 42437
        and supported_neural["p_correct"].notna().all(),
        "Unexpected supported NeuralCD population",
    )

    matched = bkt.merge(
        supported_neural,
        on="source_row",
        how="inner",
        suffixes=("_bkt", "_neural"),
        validate="one_to_one",
    ).sort_values(
        "source_row"
    ).reset_index(drop=True)

    require(
        len(matched) == 42437,
        "Incorrect matched population",
    )

    require(
        matched["student_id_bkt"].notna().all()
        and matched["student_id_neural"].notna().all(),
        "Missing student IDs",
    )

    require(
        (
            matched["student_id_bkt"].astype(str).to_numpy()
            == matched["student_id_neural"].astype(str).to_numpy()
        ).all(),
        "Student identity mismatch",
    )

    source_rows = matched[
        "source_row"
    ].to_numpy(dtype=np.int64)

    student_ids = matched[
        "student_id_bkt"
    ].astype(str).to_numpy()

    p_bkt = matched[
        "p_correct_bkt"
    ].to_numpy(dtype=float)

    p_neural = matched[
        "p_correct_neural"
    ].to_numpy(dtype=float)

    scores = candidate_scores(
        p_neural,
        p_bkt,
    )

    require(
        list(scores) == EXPECTED_IDS,
        "Implemented candidate scores differ from registration",
    )

    n = len(matched)
    frames = []

    for candidate in spec["candidate_scores"]:
        candidate_id = candidate["id"]
        values = scores[candidate_id]

        order = rank_indices(
            values,
            student_ids,
            source_rows,
        )

        require(
            len(order) == n
            and len(np.unique(order)) == n,
            f"Invalid ranking: {candidate_id}",
        )

        ranks = np.arange(
            1,
            n + 1,
            dtype=np.int32,
        )

        frame = pd.DataFrame({
            "candidate_id": candidate_id,
            "source_row": source_rows[order],
            "student_id": student_ids[order],
            "rank": ranks,
            "score": values[order],
            "alert_10": (
                ranks <= spec["alert_counts"]["0.1"]
            ),
            "alert_20": (
                ranks <= spec["alert_counts"]["0.2"]
            ),
            "alert_30": (
                ranks <= spec["alert_counts"]["0.3"]
            ),
        })

        require(
            frame["score"].is_monotonic_decreasing,
            f"Incorrect score order: {candidate_id}",
        )

        for fraction, column in (
            ("0.1", "alert_10"),
            ("0.2", "alert_20"),
            ("0.3", "alert_30"),
        ):
            require(
                int(frame[column].sum())
                == spec["alert_counts"][fraction],
                f"Incorrect alert count: {candidate_id}",
            )

        require(
            (
                ~frame["alert_10"] | frame["alert_20"]
            ).all()
            and (
                ~frame["alert_20"] | frame["alert_30"]
            ).all(),
            "Alert budgets are not nested",
        )

        frames.append(frame)

    rankings = pd.concat(
        frames,
        ignore_index=True,
    )

    require(
        len(rankings) == 8 * 42437,
        "Incorrect total ranking records",
    )

    require(
        not rankings.duplicated(
            ["candidate_id", "source_row"]
        ).any(),
        "Duplicate candidate-target ranking",
    )

    require(
        not {
            "correct",
            "observed_correct",
            "outcome",
        }.intersection(rankings.columns),
        "Outcome labels entered ranking artifact",
    )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    rankings.to_parquet(
        OUTPUT,
        index=False,
    )

    saved = pd.read_parquet(OUTPUT)

    require(
        len(saved) == len(rankings)
        and saved.columns.tolist() == rankings.columns.tolist(),
        "Ranking serialization failed",
    )

    report = {
        "version": "disagreement_rankings_v1",
        "status": "label_free_rankings_completed",
        "registration_sha256": sha256(SPEC_FILE),
        "signals_sha256": sha256(SIGNALS_FILE),
        "ranking_code_sha256": sha256(Path(__file__)),
        "score_code_sha256": sha256(
            ROOT / "src/uncertainty/disagreement.py"
        ),
        "rankings_sha256": sha256(OUTPUT),
        "matched_targets": 42437,
        "candidates": EXPECTED_IDS,
        "candidate_count": 8,
        "ranking_records": len(saved),
        "alert_counts_per_candidate":
            spec["alert_counts"],
        "neuralcd_unsupported_reported_separately": 311,
        "individual_response_labels_read": False,
        "test_evaluated": False,
        "test_gate": "closed",
    }

    REPORT.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    print("DISAGREEMENT RANKINGS VERIFIED")
    print("Matched targets:", n)
    print("Candidates:", len(EXPECTED_IDS))
    print("Ranking records:", len(saved))
    print("Alerts per candidate at 10%:", 4243)
    print("Alerts per candidate at 20%:", 8487)
    print("Alerts per candidate at 30%:", 12731)
    print("Individual response labels read: False")
    print("Test evaluated: False")
    print("Saved:", OUTPUT)
    print("Report:", REPORT)


if __name__ == "__main__":
    main()
