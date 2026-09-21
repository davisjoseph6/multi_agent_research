#!/usr/bin/env python3
"""Register event-detection experiment before reading validation labels."""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/data"

SIGNALS = (
    ROOT
    / "results/uncertainty/validation_signals_v1.parquet"
)

BRIDGE = DOCS / "uncertainty_validation_bridge_v1.json"
NEURAL_FREEZE = DOCS / "neuralcd_v1_frozen.json"
BKT_FREEZE = DOCS / "bkt_v1_frozen.json"

OUTPUT = DOCS / "event_detection_experiment_v1.json"

RISK_THRESHOLDS = (0.5, 0.7, 0.9)
ENTROPY_THRESHOLDS = (0.5, 0.8, 0.95)

POLICY_ORDER = (
    "no_trigger",
    "risk_only",
    "entropy_only",
    "risk_or_entropy",
    "risk_and_entropy",
)


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


def main():
    if OUTPUT.exists():
        raise FileExistsError(
            f"Registration already exists: {OUTPUT}"
        )

    bridge = read(BRIDGE)
    neural_freeze = read(NEURAL_FREEZE)

    assert BKT_FREEZE.is_file()
    assert neural_freeze["status"] == (
        "frozen_uncalibrated_baseline"
    )

    assert neural_freeze["test_evaluated"] is False

    assert bridge["status"] == (
        "label_free_validation_signals"
    )

    assert bridge["no_response_labels_read"] is True
    assert bridge["no_intervention_policy_applied"] is True
    assert bridge["test_evaluated"] is False

    assert bridge["eligible_primary_targets"] == 42748
    assert bridge["total_signal_records"] == 85496
    assert bridge["bkt_supported"] == 42748
    assert bridge["neuralcd_supported"] == 42437
    assert bridge["neuralcd_unsupported"] == 311

    assert sha256(SIGNALS) == bridge["output_sha256"]

    gate = ROOT / "docs/phase6_test_gate_v1.md"

    assert gate.is_file()
    assert "GATE CLOSED" in gate.read_text(
        encoding="utf-8"
    )

    candidates = [
        {
            "policy": "no_trigger",
            "risk_threshold": 0.7,
            "entropy_threshold": 0.8,
        }
    ]

    for risk in RISK_THRESHOLDS:
        candidates.append({
            "policy": "risk_only",
            "risk_threshold": risk,
            "entropy_threshold": 0.8,
        })

    for entropy in ENTROPY_THRESHOLDS:
        candidates.append({
            "policy": "entropy_only",
            "risk_threshold": 0.7,
            "entropy_threshold": entropy,
        })

    for policy in (
        "risk_or_entropy",
        "risk_and_entropy",
    ):
        for risk, entropy in itertools.product(
            RISK_THRESHOLDS,
            ENTROPY_THRESHOLDS,
        ):
            candidates.append({
                "policy": policy,
                "risk_threshold": risk,
                "entropy_threshold": entropy,
            })

    assert len(candidates) == 25

    assert len({
        (
            c["policy"],
            c["risk_threshold"],
            c["entropy_threshold"],
        )
        for c in candidates
    }) == 25

    for candidate in candidates:
        assert candidate["policy"] in POLICY_ORDER

    spec = {
        "version": "event_detection_experiment_v1",
        "status": "registered_before_label_evaluation",
        "purpose": (
            "Offline detection of observed negative responses; "
            "not intervention-benefit or recovery evaluation."
        ),
        "target": "correct_equals_zero",
        "models": ["bkt_v1", "neuralcd_v1"],
        "selection_population": (
            "same_42437_neuralcd_supported_validation_targets"
        ),
        "selection_target_count": 42437,
        "eligible_primary_target_count": 42748,
        "neuralcd_unsupported_target_count": 311,
        "candidate_count_per_model": 25,
        "model_candidate_count": 50,
        "risk_thresholds": list(RISK_THRESHOLDS),
        "entropy_thresholds": list(ENTROPY_THRESHOLDS),
        "policy_order": list(POLICY_ORDER),
        "candidates": candidates,
        "alert_budget_fraction": 0.30,
        "selection_rule": (
            "Among candidates flagging at most 30 percent of "
            "matched targets, maximize true-negative-response "
            "detections (TP); break ties by fewer false-positive "
            "alerts (FP), fewer total alerts, policy_order, "
            "risk_threshold ascending, entropy_threshold ascending."
        ),
        "confusion_matrix": {
            "positive_detection": "flag_and_correct_equals_zero",
            "false_positive": "flag_and_correct_equals_one",
            "false_negative": "no_flag_and_correct_equals_zero",
            "true_negative": "no_flag_and_correct_equals_one",
        },
        "zero_alert_precision": None,
        "metrics": [
            "true_positives",
            "false_positives",
            "false_negatives",
            "true_negatives",
            "precision",
            "recall",
            "false_positive_rate",
            "alert_rate",
        ],
        "abstention_policy": (
            "Unsupported NeuralCD targets are abstentions, "
            "not false negatives or no-flag predictions."
        ),
        "bootstrap_policy": (
            "Student-cluster analysis of selected policies is "
            "exploratory and does not correct for selection bias."
        ),
        "source_sha256": {
            "signals": sha256(SIGNALS),
            "bridge_report": sha256(BRIDGE),
            "bkt_freeze": sha256(BKT_FREEZE),
            "neuralcd_freeze": sha256(NEURAL_FREEZE),
            "event_detector": sha256(
                ROOT / "src/uncertainty/event_detector.py"
            ),
            "event_bridge": sha256(
                ROOT / "src/uncertainty/bridge.py"
            ),
            "test_gate": sha256(gate),
        },
        "validation_response_labels_accessed": False,
        "test_evaluated": False,
        "test_gate": "closed",
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("EVENT DETECTION EXPERIMENT REGISTERED")
    print("Models:", len(spec["models"]))
    print("Policies per model:", len(candidates))
    print("Total model-policy configurations:", 50)
    print("Selection targets:", 42437)
    print("Maximum alert rate:", 0.30)
    print("Validation response labels accessed: False")
    print("Test evaluated: False")
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
