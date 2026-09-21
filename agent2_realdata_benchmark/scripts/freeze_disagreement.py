#!/usr/bin/env python3
"""Freeze the registered disagreement result without loading labels."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.register_disagreement import SOURCES


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/data"

SPEC = DOCS / "disagreement_experiment_v1.json"
RANK_REPORT = DOCS / "disagreement_rankings_v1.json"
RESULT = DOCS / "disagreement_validation_v1.json"

RANKINGS = (
    ROOT / "results/uncertainty/disagreement_rankings_v1.parquet"
)

OUTPUT = DOCS / "disagreement_v1_frozen.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024), b""
        ):
            digest.update(block)
    return digest.hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    if OUTPUT.exists():
        raise FileExistsError(
            f"Disagreement freeze already exists: {OUTPUT}"
        )

    spec = read(SPEC)
    ranks = read(RANK_REPORT)
    result = read(RESULT)

    require(
        spec["status"]
        == "registered_before_disagreement_outcome_analysis",
        "Registration status changed",
    )
    require(
        ranks["status"] == "label_free_rankings_completed",
        "Rankings are incomplete",
    )
    require(
        result["status"] == "validation_disagreement_evaluated",
        "Evaluation is incomplete",
    )

    require(
        ranks["registration_sha256"]
        == result["registration_sha256"]
        == sha256(SPEC),
        "Registration identity mismatch",
    )

    require(
        result["ranking_report_sha256"] == sha256(RANK_REPORT),
        "Ranking report changed",
    )
    require(
        result["rankings_sha256"]
        == ranks["rankings_sha256"]
        == sha256(RANKINGS),
        "Ranking artifact changed",
    )
    require(
        result["evaluation_code_sha256"]
        == sha256(ROOT / "scripts/evaluate_disagreement.py"),
        "Evaluation implementation changed",
    )
    require(
        ranks["ranking_code_sha256"]
        == sha256(ROOT / "scripts/build_disagreement_rankings.py"),
        "Ranking builder changed",
    )
    require(
        ranks["score_code_sha256"]
        == sha256(ROOT / "src/uncertainty/disagreement.py"),
        "Candidate score code changed",
    )

    require(
        set(spec["source_sha256"]) == set(SOURCES),
        "Registered source inventory changed",
    )

    for name, path in SOURCES.items():
        require(
            sha256(path) == spec["source_sha256"][name],
            f"Registered source changed: {name}",
        )

    require(
        spec["matched_targets"]
        == result["matched_targets"]
        == 42437,
        "Matched population changed",
    )
    require(
        spec["alert_counts"]
        == {"0.1": 4243, "0.2": 8487, "0.3": 12731},
        "Alert budgets changed",
    )
    require(
        spec["candidate_count"]
        == result["candidate_count"]
        == 8,
        "Candidate count changed",
    )
    require(
        result["primary_alert_count"] == 12731,
        "Primary alert count changed",
    )
    require(
        result["neuralcd_abstentions_outside_population"] == 311,
        "Abstention count changed",
    )

    require(
        spec["test_gate"]
        == ranks["test_gate"]
        == result["test_gate"]
        == "closed",
        "Test gate is not closed",
    )
    require(
        all(
            item["test_evaluated"] is False
            for item in (spec, ranks, result)
        ),
        "Test evaluation detected",
    )

    registered = {
        entry["id"]: entry["alpha"]
        for entry in spec["candidate_scores"]
    }

    candidates = result["candidate_results"]

    require(
        [row["candidate_id"] for row in candidates]
        == list(registered),
        "Candidate order changed",
    )

    expected_tp = {
        "neuralcd_risk": 7253,
        "bkt_risk": 6702,
        "mean_risk": 7252,
        "max_risk": 7239,
        "neuralcd_risk_plus_disagreement_a0.25": 7184,
        "neuralcd_risk_plus_disagreement_a0.5": 7150,
        "neuralcd_risk_plus_disagreement_a1": 6961,
        "neuralcd_risk_plus_disagreement_a2": 6326,
    }

    require(
        set(expected_tp) == set(registered),
        "Unexpected registered candidate identities",
    )

    for row in candidates:
        name = row["candidate_id"]

        require(
            row["alpha"] == registered[name],
            f"Alpha mismatch: {name}",
        )

        for fraction, alert_count in spec["alert_counts"].items():
            metrics = row["budgets"][fraction]

            require(
                metrics["count"] == 42437
                and metrics["alerts"] == alert_count
                and metrics["tp"] + metrics["fp"] == alert_count
                and (
                    metrics["tp"] + metrics["fp"]
                    + metrics["fn"] + metrics["tn"]
                ) == 42437,
                f"Confusion-matrix mismatch: {name}, {fraction}",
            )

        require(
            row["budgets"]["0.3"]["tp"] == expected_tp[name],
            f"Primary detection count changed: {name}",
        )

    family = [
        row for row in candidates
        if registered[row["candidate_id"]] is not None
    ]

    require(
        len(family) == 5,
        "Incorrect disagreement selection family",
    )

    independently_selected = min(
        family,
        key=lambda row: (
            -row["budgets"]["0.3"]["tp"],
            registered[row["candidate_id"]],
        ),
    )

    require(
        independently_selected
        == result["selected_disagreement_family"],
        "Registered selection rule mismatch",
    )

    require(
        independently_selected["candidate_id"]
        == "neuralcd_risk"
        and independently_selected["alpha"] == 0.0,
        "Unexpected selected disagreement configuration",
    )

    comparisons = result[
        "paired_primary_comparisons_vs_neuralcd_risk"
    ]

    require(
        set(comparisons) == set(expected_tp),
        "Missing paired comparison",
    )

    for name, row in comparisons.items():
        require(
            row["net_additional_negative_responses"]
            == expected_tp[name] - expected_tp["neuralcd_risk"],
            f"Paired detection mismatch: {name}",
        )
        require(
            row["newly_flagged_negative_responses"]
            - row["no_longer_flagged_negative_responses"]
            == row["net_additional_negative_responses"],
            f"Reallocation accounting mismatch: {name}",
        )

    frozen = {
        "version": "disagreement_v1",
        "status": "frozen_development_disagreement_result",
        "registration_sha256": sha256(SPEC),
        "ranking_report_sha256": sha256(RANK_REPORT),
        "ranking_artifact_sha256": sha256(RANKINGS),
        "validation_report_sha256": sha256(RESULT),
        "evaluation_code_sha256": sha256(
            ROOT / "scripts/evaluate_disagreement.py"
        ),
        "matched_targets": 42437,
        "primary_alert_count": 12731,
        "neuralcd_abstentions_outside_population": 311,
        "primary_true_positives": expected_tp,
        "selected_candidate": "neuralcd_risk",
        "selected_alpha": 0.0,
        "interpretation": (
            "None of the four registered positive-alpha "
            "disagreement variants improved negative-response "
            "detections over NeuralCD risk at the primary fixed "
            "alert budget on this reused validation population. "
            "No causal recovery effect or independently calibrated "
            "epistemic uncertainty was evaluated."
        ),
        "individual_response_labels_read_during_freeze": False,
        "test_evaluated": False,
        "test_access_authorized": False,
    }

    OUTPUT.write_text(
        json.dumps(frozen, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("DISAGREEMENT V1 FREEZE VERIFIED")
    print("Matched targets: 42437")
    print("Primary alerts per candidate: 12731")
    print("Selected candidate: neuralcd_risk")
    print("Selected alpha: 0.0")
    print("Individual response labels read: False")
    print("Test evaluated: False")
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
