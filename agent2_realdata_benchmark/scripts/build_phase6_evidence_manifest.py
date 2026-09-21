#!/usr/bin/env python3
"""Consolidate existing Phase 6 evidence without reading interaction data."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUTPUT = ROOT / "docs/data/phase6_evidence_manifest_v1.json"

SOURCES = {
    "bkt_freeze": "docs/data/bkt_v1_frozen.json",
    "neuralcd_freeze": "docs/data/neuralcd_v1_frozen.json",
    "uncertainty_bridge":
        "docs/data/uncertainty_validation_bridge_v1.json",
    "event_registration":
        "docs/data/event_detection_experiment_v1.json",
    "event_validation":
        "docs/data/event_detection_validation_v1.json",
    "event_freeze":
        "docs/data/event_detection_v1_frozen.json",
    "disagreement_registration":
        "docs/data/disagreement_experiment_v1.json",
    "disagreement_validation":
        "docs/data/disagreement_validation_v1.json",
    "disagreement_freeze":
        "docs/data/disagreement_v1_frozen.json",
    "recovery_feasibility":
        "docs/data/recovery_feasibility_train_v1.json",
    "recovery_followup":
        "docs/data/recovery_followup_train_v1.json",
    "recovery_shared_skill":
        "docs/data/recovery_shared_skill_train_v1.json",
    "recovery_fault":
        "docs/data/recovery_fault_evaluation_v1.json",
    "fault_protocol":
        "docs/phase6_recovery_fault_evaluation_v1.md",
    "fault_results":
        "docs/phase6_recovery_fault_results_v1.md",
    "durable_implementation":
        "src/recovery/durable_execution.py",
    "process_tests":
        "tests/test_recovery_durable_process.py",
    "test_gate":
        "docs/phase6_test_gate_v1.md",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024), b""
        ):
            digest.update(chunk)

    return digest.hexdigest()


def read(name):
    return json.loads(
        (ROOT / SOURCES[name]).read_text(encoding="utf-8")
    )


def main():
    if OUTPUT.exists():
        raise FileExistsError(
            f"Existing evidence manifest: {OUTPUT}"
        )

    paths = {
        name: ROOT / relative
        for name, relative in SOURCES.items()
    }

    for name, path in paths.items():
        require(
            path.is_file(),
            f"Missing source artifact: {name}: {path}",
        )

    require(
        "GATE CLOSED" in paths["test_gate"].read_text(
            encoding="utf-8"
        ),
        "Held-out test gate is not closed",
    )

    disagreement = read("disagreement_freeze")
    feasibility = read("recovery_feasibility")
    followup = read("recovery_followup")
    shared = read("recovery_shared_skill")
    fault = read("recovery_fault")

    require(
        disagreement["selected_candidate"] == "neuralcd_risk"
        and disagreement["selected_alpha"] == 0.0
        and disagreement["matched_targets"] == 42437
        and disagreement["primary_alert_count"] == 12731
        and disagreement["test_evaluated"] is False,
        "Frozen disagreement result changed",
    )

    tp = disagreement["primary_true_positives"]

    require(
        tp["neuralcd_risk"] == 7253
        and all(
            tp[name] <= 7253
            for name in (
                "neuralcd_risk_plus_disagreement_a0.25",
                "neuralcd_risk_plus_disagreement_a0.5",
                "neuralcd_risk_plus_disagreement_a1",
                "neuralcd_risk_plus_disagreement_a2",
            )
        ),
        "Registered primary disagreement findings changed",
    )

    population = feasibility["population"]

    require(
        population["training_students"] == 2951
        and population["training_interactions"] == 230387
        and population["main_problems"] == 183195,
        "Training-only population changed",
    )

    transitions = followup["transition_counts"]

    require(
        transitions["different_assistment"] == 179032
        and transitions["same_assistment"] == 1212
        and transitions["no_next_main"] == 2951,
        "Cross-ASSISTment transitions changed",
    )

    skill_counts = shared["transition_counts"]

    require(
        skill_counts["different_assistment"] == 179032
        and skill_counts["both_skill_annotated_with_overlap"]
        == 126995
        and (
            skill_counts["both_skill_annotated_with_overlap"]
            + skill_counts["both_skill_annotated_without_overlap"]
            + skill_counts["at_least_one_missing_skill_annotation"]
        ) == 179032,
        "Shared-skill accounting changed",
    )

    require(
        fault["process_tests_passed"] == 3
        and fault["combined_tests_passed"] == 180
        and fault["protocol_edited_after_registration"] is False
        and all(
            scenario["passed"]
            for scenario in fault["scenarios"].values()
        ),
        "Fault evaluation record changed",
    )

    require(
        fault["implementation_sha256"]
        == sha256(paths["durable_implementation"])
        and fault["process_test_sha256"]
        == sha256(paths["process_tests"])
        and fault["current_protocol_sha256"]
        == sha256(paths["fault_protocol"]),
        "Fault evaluation source checksum mismatch",
    )

    for name, report in (
        ("feasibility", feasibility),
        ("followup", followup),
        ("shared_skill", shared),
    ):
        require(
            report["validation_rows_returned"] == 0
            and report["test_rows_returned"] == 0
            and report["test_outcomes_evaluated"] is False
            and report["test_gate"] == "closed",
            f"Partition access condition changed: {name}",
        )

    require(
        fault["held_out_test_evaluated"] is False
        and fault["student_learning_effect_evaluated"] is False
        and fault["real_assistance_delivered"] is False,
        "Fault evaluation scientific scope changed",
    )

    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO,
        text=True,
    ).strip()

    manifest = {
        "version": "phase6_evidence_manifest_v1",
        "status": "existing_evidence_consolidated",
        "source_commit": head,
        "builder_sha256": sha256(Path(__file__)),
        "artifact_sha256": {
            name: sha256(path)
            for name, path in paths.items()
        },
        "verified_findings": {
            "disagreement": {
                "matched_targets": 42437,
                "primary_alerts_per_candidate": 12731,
                "selected_candidate":
                    disagreement["selected_candidate"],
                "selected_alpha":
                    disagreement["selected_alpha"],
                "primary_true_positives": tp,
                "evidence_type":
                    "reused_validation_development",
            },
            "recovery_feasibility": {
                "training_students":
                    population["training_students"],
                "training_interactions":
                    population["training_interactions"],
                "cross_assistment_followups":
                    transitions["different_assistment"],
                "shared_skill_followups":
                    skill_counts[
                        "both_skill_annotated_with_overlap"
                    ],
                "evidence_type":
                    "training_only_observational",
            },
            "fault_evaluation": {
                "process_tests_passed":
                    fault["process_tests_passed"],
                "combined_tests_passed":
                    fault["combined_tests_passed"],
                "protocol_edited_after_registration":
                    fault[
                        "protocol_edited_after_registration"
                    ],
                "evidence_type":
                    "synthetic_local_software_tests",
            },
        },
        "not_established": [
            "Causal benefit of hints or scaffolding",
            "Real student assistance delivery",
            "Improved student learning or mastery",
            "Distributed exactly-once delivery",
            "Independent held-out predictive confirmation",
        ],
        "interaction_rows_read_by_this_builder": False,
        "response_labels_read_by_this_builder": False,
        "new_models_fitted": False,
        "new_policies_selected": False,
        "held_out_test_evaluated": False,
        "test_gate": "closed",
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n",
        encoding="utf-8",
    )

    print("PHASE 6 EVIDENCE MANIFEST VERIFIED")
    print("Source artifacts:", len(paths))
    print("Shared-skill follow-ups: 126995")
    print("Process tests: 3")
    print("Combined tests: 180")
    print("Interaction records read: False")
    print("Test evaluated: False")
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
