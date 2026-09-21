#!/usr/bin/env python3
"""Score registered disagreement rankings using validation labels only.

Verifies every candidate's label-free ranking before opening outcomes.
Never accesses the held-out test partition.
"""

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

SPEC = DOCS / "disagreement_experiment_v1.json"
RANK_REPORT = DOCS / "disagreement_rankings_v1.json"
BRIDGE = DOCS / "uncertainty_validation_bridge_v1.json"

RANKINGS = RESULTS / "disagreement_rankings_v1.parquet"
SIGNALS = RESULTS / "validation_signals_v1.parquet"

BKT_LABEL_SOURCE = (
    ROOT / "results/bkt/frozen_v1_validation_predictions.parquet"
)

OUTPUT = DOCS / "disagreement_validation_v1.json"

BUDGETS = (
    ("0.1", "alert_10"),
    ("0.2", "alert_20"),
    ("0.3", "alert_30"),
)

SIGNAL_COLUMNS = [
    "source_row",
    "student_id",
    "model",
    "status",
    "p_correct",
]

RANK_COLUMNS = [
    "candidate_id",
    "source_row",
    "student_id",
    "rank",
    "score",
    "alert_10",
    "alert_20",
    "alert_30",
]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def score_budget(labels, count):
    """Score the first count ranked targets; event is response zero."""

    labels = np.asarray(labels)

    if labels.ndim != 1 or len(labels) == 0:
        raise ValueError("Invalid label array")

    if not np.isin(labels, [0, 1]).all():
        raise ValueError("Labels must be binary")

    if isinstance(count, bool) or not isinstance(
        count, (int, np.integer)
    ):
        raise TypeError("Alert count must be an integer")

    if not 0 < count <= len(labels):
        raise ValueError("Invalid alert count")

    negative = labels == 0
    total_negative = int(negative.sum())
    total_positive = len(labels) - total_negative

    if not total_negative or not total_positive:
        raise ValueError("Both outcome classes are required")

    tp = int(negative[:count].sum())
    fp = count - tp
    fn = total_negative - tp
    tn = total_positive - fp

    require(
        tp + fp + fn + tn == len(labels),
        "Confusion-matrix accounting failed",
    )

    return {
        "count": int(len(labels)),
        "negative_responses": total_negative,
        "positive_responses": total_positive,
        "alerts": int(count),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "alert_rate": count / len(labels),
        "precision": tp / count,
        "recall": tp / total_negative,
        "false_positive_rate": fp / total_positive,
    }


def select_registered(results, spec):
    """Apply the frozen primary selection rule, with smaller-alpha tie."""

    registered = {
        row["id"]: row["alpha"]
        for row in spec["candidate_scores"]
    }

    eligible = [
        result
        for result in results
        if registered[result["candidate_id"]] is not None
    ]

    if len(eligible) != 5:
        raise RuntimeError("Expected baseline and four alpha variants")

    return min(
        eligible,
        key=lambda result: (
            -result["budgets"]["0.3"]["tp"],
            registered[result["candidate_id"]],
        ),
    )


def main():
    if OUTPUT.exists():
        raise FileExistsError(
            f"Evaluation report already exists: {OUTPUT}"
        )

    spec = read(SPEC)
    ranking_report = read(RANK_REPORT)
    bridge = read(BRIDGE)

    require(
        spec["status"]
        == "registered_before_disagreement_outcome_analysis",
        "Invalid registration status",
    )

    require(
        ranking_report["status"] == "label_free_rankings_completed",
        "Rankings were not completed",
    )

    require(
        ranking_report["registration_sha256"] == sha256(SPEC),
        "Ranking registration mismatch",
    )

    require(
        ranking_report["rankings_sha256"] == sha256(RANKINGS),
        "Ranking file changed",
    )

    require(
        ranking_report["ranking_code_sha256"]
        == sha256(ROOT / "scripts/build_disagreement_rankings.py"),
        "Ranking builder changed",
    )

    require(
        ranking_report["score_code_sha256"]
        == sha256(ROOT / "src/uncertainty/disagreement.py"),
        "Scoring and ranking implementation changed",
    )

    require(
        ranking_report["signals_sha256"] == sha256(SIGNALS)
        == bridge["output_sha256"],
        "Signal file changed",
    )

    require(
        sha256(BKT_LABEL_SOURCE)
        == bridge["bkt_predictions_sha256"],
        "Validation label source changed",
    )

    require(
        spec["matched_targets"] == 42437
        and spec["candidate_count"] == 8
        and spec["alert_counts"] == {
            "0.1": 4243,
            "0.2": 8487,
            "0.3": 12731,
        },
        "Registered experiment differs",
    )

    require(
        spec["individual_response_labels_read"] is False
        and spec["test_evaluated"] is False
        and spec["test_gate"] == "closed"
        and ranking_report["individual_response_labels_read"] is False
        and ranking_report["test_evaluated"] is False,
        "Registered data access conditions changed",
    )

    # PHASE A: verify decisions using ONLY label-free artifacts.
    rankings = pd.read_parquet(RANKINGS)
    signals = pd.read_parquet(
        SIGNALS,
        columns=SIGNAL_COLUMNS,
    )

    require(
        rankings.columns.tolist() == RANK_COLUMNS,
        "Unexpected ranking schema",
    )
    require(
        signals.columns.tolist() == SIGNAL_COLUMNS,
        "Unexpected signal projection",
    )

    require(
        len(rankings) == 8 * 42437
        and len(signals) == 85496,
        "Incorrect artifact size",
    )

    require(
        not rankings.duplicated(
            ["candidate_id", "source_row"]
        ).any(),
        "Duplicate candidate-target row",
    )

    require(
        not {"correct", "observed_correct", "outcome"}
        .intersection(rankings.columns),
        "Labels found in ranking artifact",
    )

    bkt = signals.loc[
        signals["model"].eq("bkt_v1")
    ]

    neural = signals.loc[
        signals["model"].eq("neuralcd_v1")
    ]

    require(
        len(bkt) == len(neural) == 42748,
        "Unexpected model coverage",
    )

    require(
        bkt["status"].eq("supported").all(),
        "Unexpected BKT abstention",
    )

    unsupported = neural["status"].eq(
        "unsupported_training_item"
    )

    require(
        int(unsupported.sum()) == 311
        and neural.loc[unsupported, "p_correct"].isna().all(),
        "NeuralCD unsupported accounting failed",
    )

    paired = bkt.merge(
        neural.loc[
            neural["status"].eq("supported")
        ],
        on="source_row",
        how="inner",
        validate="one_to_one",
        suffixes=("_bkt", "_neural"),
    ).sort_values("source_row").reset_index(drop=True)

    require(
        len(paired) == 42437,
        "Incorrect matched population",
    )

    require(
        (
            paired["student_id_bkt"].astype(str).to_numpy()
            == paired["student_id_neural"].astype(str).to_numpy()
        ).all(),
        "Paired student mismatch",
    )

    sources = paired["source_row"].to_numpy(dtype=np.int64)
    students = paired["student_id_bkt"].astype(str).to_numpy()

    computed_scores = candidate_scores(
        paired["p_correct_neural"].to_numpy(dtype=float),
        paired["p_correct_bkt"].to_numpy(dtype=float),
    )

    ids = [
        item["id"] for item in spec["candidate_scores"]
    ]

    require(
        list(computed_scores) == ids
        and ranking_report["candidates"] == ids,
        "Candidate identities changed",
    )

    ordered_groups = {}

    for candidate_id in ids:
        group = rankings.loc[
            rankings["candidate_id"].eq(candidate_id)
        ].sort_values("rank").reset_index(drop=True)

        require(
            len(group) == 42437,
            f"Candidate coverage mismatch: {candidate_id}",
        )

        np.testing.assert_array_equal(
            group["rank"].to_numpy(),
            np.arange(1, 42438),
        )

        expected_order = rank_indices(
            computed_scores[candidate_id],
            students,
            sources,
        )

        np.testing.assert_array_equal(
            group["source_row"].to_numpy(),
            sources[expected_order],
        )

        np.testing.assert_array_equal(
            group["student_id"].astype(str).to_numpy(),
            students[expected_order],
        )

        np.testing.assert_allclose(
            group["score"].to_numpy(dtype=float),
            computed_scores[candidate_id][expected_order],
            rtol=0,
            atol=1e-12,
        )

        for fraction, column in BUDGETS:
            limit = spec["alert_counts"][fraction]

            np.testing.assert_array_equal(
                group[column].to_numpy(),
                group["rank"].to_numpy() <= limit,
            )

            require(
                int(group[column].sum()) == limit,
                f"Incorrect alert count: {candidate_id}",
            )

        ordered_groups[candidate_id] = group

    print(
        "ALL EIGHT RANKINGS VERIFIED WITHOUT RESPONSE LABELS",
        flush=True,
    )

    # PHASE B: read validation labels strictly for scoring.
    outcomes = pd.read_parquet(
        BKT_LABEL_SOURCE,
        columns=[
            "source_row",
            "student_id",
            "observed_correct",
        ],
    )

    require(
        len(outcomes) == 42748
        and outcomes["source_row"].is_unique,
        "Validation label population mismatch",
    )

    outcomes["student_id"] = outcomes["student_id"].astype(str)

    paired_identity = pd.DataFrame({
        "source_row": sources,
        "student_id": students,
    })

    matched_labels = paired_identity.merge(
        outcomes,
        on=["source_row", "student_id"],
        how="left",
        validate="one_to_one",
    )

    require(
        len(matched_labels) == 42437
        and matched_labels["observed_correct"].notna().all(),
        "Matched outcome identities differ",
    )

    labels_by_source = matched_labels.set_index(
        "source_row"
    )["observed_correct"]

    require(
        np.isin(
            labels_by_source.to_numpy(),
            [0, 1],
        ).all(),
        "Nonbinary outcome labels",
    )

    candidate_results = []

    for candidate_id in ids:
        group = ordered_groups[candidate_id]

        ranked_labels = labels_by_source.loc[
            group["source_row"].to_numpy()
        ].to_numpy()

        budgets = {
            fraction: score_budget(
                ranked_labels,
                spec["alert_counts"][fraction],
            )
            for fraction, _ in BUDGETS
        }

        candidate_results.append({
            "candidate_id": candidate_id,
            "alpha": next(
                item["alpha"]
                for item in spec["candidate_scores"]
                if item["id"] == candidate_id
            ),
            "budgets": budgets,
        })

    selected = select_registered(
        candidate_results,
        spec,
    )

    # Exact-budget paired comparison: changing the ranking
    # reallocates alerts; it does not create additional capacity.
    primary_k = spec["alert_counts"]["0.3"]
    baseline_group = ordered_groups["neuralcd_risk"]
    baseline_set = set(
        baseline_group["source_row"].iloc[:primary_k]
    )

    comparisons = {}

    for candidate_id in ids:
        candidate_set = set(
            ordered_groups[candidate_id][
                "source_row"
            ].iloc[:primary_k]
        )

        gained = candidate_set - baseline_set
        lost = baseline_set - candidate_set

        gained_negative = int(
            (labels_by_source.loc[list(gained)] == 0).sum()
        ) if gained else 0

        lost_negative = int(
            (labels_by_source.loc[list(lost)] == 0).sum()
        ) if lost else 0

        candidate_tp = next(
            row["budgets"]["0.3"]["tp"]
            for row in candidate_results
            if row["candidate_id"] == candidate_id
        )

        baseline_tp = next(
            row["budgets"]["0.3"]["tp"]
            for row in candidate_results
            if row["candidate_id"] == "neuralcd_risk"
        )

        require(
            len(gained) == len(lost),
            "Alert budgets differ",
        )

        require(
            gained_negative - lost_negative
            == candidate_tp - baseline_tp,
            "Paired comparison accounting failed",
        )

        comparisons[candidate_id] = {
            "alerts_reallocated": len(gained),
            "newly_flagged_negative_responses":
                gained_negative,
            "no_longer_flagged_negative_responses":
                lost_negative,
            "net_additional_negative_responses":
                candidate_tp - baseline_tp,
        }

    result = {
        "version": "disagreement_validation_v1",
        "status": "validation_disagreement_evaluated",
        "registration_sha256": sha256(SPEC),
        "ranking_report_sha256": sha256(RANK_REPORT),
        "rankings_sha256": sha256(RANKINGS),
        "evaluation_code_sha256": sha256(Path(__file__)),
        "validation_label_source_sha256":
            sha256(BKT_LABEL_SOURCE),
        "matched_targets": 42437,
        "candidate_count": 8,
        "primary_alert_count": primary_k,
        "neuralcd_abstentions_outside_population": 311,
        "candidate_results": candidate_results,
        "selected_disagreement_family": selected,
        "paired_primary_comparisons_vs_neuralcd_risk":
            comparisons,
        "interpretation": (
            "Development-set negative-response detection at "
            "fixed alert counts. Previously reused validation "
            "outcomes preclude independent confirmatory claims. "
            "No intervention benefit or epistemic calibration "
            "has been established."
        ),
        "individual_validation_labels_read_for_scoring": True,
        "test_evaluated": False,
        "test_gate": "closed",
    }

    OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("\nDISAGREEMENT VALIDATION COMPLETE")
    print("Primary alert count:", primary_k)

    for row in candidate_results:
        metrics = row["budgets"]["0.3"]
        print(
            row["candidate_id"],
            "TP=", metrics["tp"],
            "FP=", metrics["fp"],
            "precision=", round(metrics["precision"], 6),
            "recall=", round(metrics["recall"], 6),
        )

    print("\nRegistered disagreement-family selection:")
    print(
        selected["candidate_id"],
        "alpha=", selected["alpha"],
        "TP=", selected["budgets"]["0.3"]["tp"],
    )

    print("\nPaired comparisons against NeuralCD risk:")
    print(json.dumps(comparisons, indent=2))

    print("\nTest evaluated: False")
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
