#!/usr/bin/env python3
"""Freeze selected event policies; do not access individual response labels."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/data"
RESULTS = ROOT / "results/uncertainty"

SPEC = DOCS / "event_detection_experiment_v1.json"
REPORT = DOCS / "event_detection_validation_v1.json"
AUDIT = DOCS / "event_detection_structure_audit_v1.json"
BRIDGE = DOCS / "uncertainty_validation_bridge_v1.json"

SIGNALS = RESULTS / "validation_signals_v1.parquet"
DECISIONS = RESULTS / "event_detection_selected_v1.parquet"

OUTPUT = DOCS / "event_detection_v1_frozen.json"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(
            f"Event policies already frozen: {OUTPUT}"
        )

    spec = read(SPEC)
    report = read(REPORT)
    audit = read(AUDIT)
    bridge = read(BRIDGE)

    require(
        spec["status"] == "registered_before_label_evaluation",
        "Invalid registration",
    )
    require(
        report["status"] == "validation_policy_selection_completed",
        "Incomplete policy selection",
    )
    require(
        report["registration_sha256"] == sha256(SPEC),
        "Registration changed",
    )
    require(
        audit["validation_report_sha256"] == sha256(REPORT),
        "Structural audit refers to another report",
    )
    require(
        audit["registration_sha256"] == sha256(SPEC),
        "Structural audit registration mismatch",
    )
    require(
        audit["status"] == "selected_policy_structure_verified",
        "Structural audit did not pass",
    )

    for item in (spec, report, audit, bridge):
        require(
            item["test_evaluated"] is False,
            "Test lock not confirmed",
        )

    require(
        report["test_gate"] == audit["test_gate"] == "closed",
        "Test gate unexpectedly open",
    )

    require(
        spec["model_candidate_count"] == 50,
        "Registered candidate count changed",
    )

    require(
        report["matched_targets"] == 42437
        and report["neuralcd_abstentions"] == 311,
        "Validation population changed",
    )

    # Check every identity recorded before label evaluation.
    registered_sources = {
        "signals": SIGNALS,
        "bridge_report": BRIDGE,
        "bkt_freeze": DOCS / "bkt_v1_frozen.json",
        "neuralcd_freeze": DOCS / "neuralcd_v1_frozen.json",
        "event_detector":
            ROOT / "src/uncertainty/event_detector.py",
        "event_bridge":
            ROOT / "src/uncertainty/bridge.py",
        "test_gate": ROOT / "docs/phase6_test_gate_v1.md",
    }

    for name, path in registered_sources.items():
        require(
            sha256(path) == spec["source_sha256"][name],
            f"Registered source changed: {name}",
        )

    require(
        sha256(SIGNALS) == report["signals_sha256"]
        == audit["signals_sha256"]
        == bridge["output_sha256"],
        "Signal dataset identity mismatch",
    )

    require(
        sha256(DECISIONS)
        == report["selected_decisions_sha256"]
        == audit["selected_decisions_sha256"],
        "Selected decisions changed",
    )

    require(
        sha256(ROOT / "scripts/evaluate_event_detection.py")
        == report["evaluation_code_sha256"],
        "Evaluation code changed",
    )

    expected = {
        "bkt_v1": ("risk_or_entropy", 0.5, 0.95),
        "neuralcd_v1": ("risk_only", 0.5, 0.8),
    }

    for model, configuration in expected.items():
        candidates = report["candidate_results"][model]
        chosen = report["selected"][model]

        require(len(candidates) == 25, "Candidate count mismatch")
        require(chosen in candidates, "Selected policy not in grid")
        require(
            chosen["within_alert_budget"] is True,
            "Selected policy violates alert budget",
        )

        actual = (
            chosen["policy"],
            chosen["risk_threshold"],
            chosen["entropy_threshold"],
        )

        require(
            actual == configuration,
            f"Unexpected selected policy for {model}",
        )

        eligible = [
            row for row in candidates
            if row["within_alert_budget"]
        ]

        independently_selected = min(
            eligible,
            key=lambda row: (
                -row["metrics"]["tp"],
                row["metrics"]["fp"],
                row["metrics"]["alerts"],
                spec["policy_order"].index(row["policy"]),
                row["risk_threshold"],
                row["entropy_threshold"],
            ),
        )

        require(
            chosen == independently_selected,
            f"Selection rule mismatch: {model}",
        )

    require(
        audit["bkt_exact_decision_mismatches"] == 0
        and audit["neuralcd_exact_decision_mismatches"] == 0,
        "Structural decision mismatch",
    )

    overlap = audit["matched_flag_overlap"]

    require(
        sum(overlap.values()) == 42437,
        "Alert-overlap accounting mismatch",
    )

    bkt_matched_alerts = (
        overlap["both_flag"] + overlap["bkt_only_flag"]
    )
    neural_matched_alerts = (
        overlap["both_flag"] + overlap["neuralcd_only_flag"]
    )

    require(
        bkt_matched_alerts
        == report["selected"]["bkt_v1"]["metrics"]["alerts"],
        "BKT matched alert count mismatch",
    )
    require(
        neural_matched_alerts
        == report["selected"]["neuralcd_v1"]["metrics"]["alerts"],
        "NeuralCD matched alert count mismatch",
    )
    require(
        bkt_matched_alerts
        + audit["bkt_alerts_on_neuralcd_unsupported"]
        == report["selected_bkt_full_coverage"]["alerts"],
        "BKT full-coverage count mismatch",
    )

    # Read only saved decisions and support statuses, never labels.
    decisions = pd.read_parquet(
        DECISIONS,
        columns=["source_row", "model", "status", "flagged"],
    )

    require(
        len(decisions) == 85496,
        "Saved decision count mismatch",
    )
    require(
        not decisions.duplicated(["source_row", "model"]).any(),
        "Duplicate model-target decision",
    )

    bkt = decisions.loc[decisions["model"] == "bkt_v1"]
    neural = decisions.loc[decisions["model"] == "neuralcd_v1"]

    require(
        len(bkt) == len(neural) == 42748,
        "Model coverage mismatch",
    )
    require(
        bkt["status"].eq("supported").all()
        and bkt["flagged"].notna().all(),
        "BKT has missing decisions",
    )

    unsupported = neural["status"].eq(
        "unsupported_training_item"
    )

    require(
        int(unsupported.sum()) == 311
        and neural.loc[unsupported, "flagged"].isna().all()
        and neural.loc[~unsupported, "flagged"].notna().all(),
        "NeuralCD abstention accounting mismatch",
    )

    frozen = {
        "version": "event_detection_v1",
        "status": "frozen_development_selected_policies",
        "registration_sha256": sha256(SPEC),
        "validation_report_sha256": sha256(REPORT),
        "structure_audit_sha256": sha256(AUDIT),
        "signals_sha256": sha256(SIGNALS),
        "selected_decisions_sha256": sha256(DECISIONS),
        "evaluation_code_sha256": sha256(
            ROOT / "scripts/evaluate_event_detection.py"
        ),
        "detector_code_sha256": sha256(
            ROOT / "src/uncertainty/event_detector.py"
        ),
        "selected": report["selected"],
        "matched_targets": 42437,
        "eligible_primary_targets": 42748,
        "neuralcd_abstentions": 311,
        "matched_flag_overlap": overlap,
        "bkt_equivalent_probability_cutoff":
            audit["bkt_equivalent_probability_cutoff"],
        "interpretation": (
            "Selected by validation negative-response detection "
            "under a 30 percent pooled alert budget. BKT's "
            "selected OR policy is equivalent to a single "
            "probability cutoff. No intervention effect established."
        ),
        "individual_response_labels_read_during_freeze": False,
        "test_evaluated": False,
        "test_access_authorized": False,
    }

    OUTPUT.write_text(
        json.dumps(frozen, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("EVENT DETECTION V1 FREEZE VERIFIED")
    print("BKT matched alerts:", bkt_matched_alerts)
    print("NeuralCD matched alerts:", neural_matched_alerts)
    print("NeuralCD abstentions:", 311)
    print("Individual response labels read: False")
    print("Test evaluated: False")
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
