#!/usr/bin/env python3
"""Register cross-model disagreement analysis without loading outcomes."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/data"
RESULTS = ROOT / "results/uncertainty"

OUTPUT = DOCS / "disagreement_experiment_v1.json"

SIGNALS = RESULTS / "validation_signals_v1.parquet"

SOURCES = {
    "signals": SIGNALS,
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


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024), b""
        ):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    if OUTPUT.exists():
        raise FileExistsError(
            f"Existing disagreement registration: {OUTPUT}"
        )

    for name, path in SOURCES.items():
        if not path.is_file():
            raise FileNotFoundError(f"{name}: {path}")

    bridge = read(SOURCES["bridge"])
    neural = read(SOURCES["neuralcd_freeze"])
    event = read(SOURCES["event_freeze"])

    assert bridge["status"] == "label_free_validation_signals"
    assert bridge["output_sha256"] == sha256(SIGNALS)
    assert bridge["no_response_labels_read"] is True
    assert bridge["neuralcd_supported"] == 42437
    assert bridge["neuralcd_unsupported"] == 311

    assert neural["status"] == "frozen_uncalibrated_baseline"
    assert event["status"] == (
        "frozen_development_selected_policies"
    )

    assert neural["test_evaluated"] is False
    assert event["test_evaluated"] is False
    assert event["test_access_authorized"] is False

    assert "GATE CLOSED" in (
        SOURCES["test_gate"].read_text(encoding="utf-8")
    )

    n = 42437

    budgets = {
        str(fraction): math.floor(fraction * n)
        for fraction in (0.10, 0.20, 0.30)
    }

    assert budgets == {
        "0.1": 4243,
        "0.2": 8487,
        "0.3": 12731,
    }

    alphas = [0.0, 0.25, 0.5, 1.0, 2.0]

    candidate_scores = [
        {
            "id": "neuralcd_risk",
            "definition": "1 - p_neuralcd",
            "alpha": 0.0,
        },
        {
            "id": "bkt_risk",
            "definition": "1 - p_bkt",
            "alpha": None,
        },
        {
            "id": "mean_risk",
            "definition": (
                "((1 - p_neuralcd) + (1 - p_bkt)) / 2"
            ),
            "alpha": None,
        },
        {
            "id": "max_risk",
            "definition": (
                "max(1 - p_neuralcd, 1 - p_bkt)"
            ),
            "alpha": None,
        },
    ]

    candidate_scores.extend({
        "id": f"neuralcd_risk_plus_disagreement_a{alpha:g}",
        "definition": (
            "(1 - p_neuralcd) + alpha * "
            "abs(p_neuralcd - p_bkt)"
        ),
        "alpha": alpha,
    } for alpha in alphas if alpha > 0)

    assert len(candidate_scores) == 8
    assert len({c["id"] for c in candidate_scores}) == 8

    spec = {
        "version": "disagreement_experiment_v1",
        "status": "registered_before_disagreement_outcome_analysis",
        "models": ["bkt_v1", "neuralcd_v1"],
        "population": "matched_validation_supported_targets",
        "matched_targets": n,
        "unsupported_neuralcd_targets": 311,
        "target": "observed_correct_equals_zero",
        "disagreement_definition":
            "abs(p_neuralcd - p_bkt)",
        "candidate_scores": candidate_scores,
        "candidate_count": len(candidate_scores),
        "primary_alert_fraction": 0.30,
        "alert_counts": budgets,
        "ranking_rule": "descending_score",
        "tie_breaker": (
            "ascending_SHA256_of_UTF8("
            "'phase6_disagreement_v1|' + "
            "student_id + '|' + str(source_row)); "
            "then ascending source_row"
        ),
        "primary_outcome": (
            "number_of_observed_negative_responses_flagged_"
            "at_exactly_12731_alerts"
        ),
        "additional_metrics": [
            "precision",
            "recall",
            "false_positive_count",
            "false_positive_rate",
            "alert_overlap",
        ],
        "descriptive_budget_fractions": [0.10, 0.20],
        "primary_comparison": (
            "Each nonzero-alpha disagreement score versus "
            "neuralcd_risk at the identical alert count. "
            "Also report bkt_risk, mean_risk and max_risk."
        ),
        "candidate_selection": (
            "Among neuralcd_risk and the four disagreement "
            "variants, maximize true positives at 12731 alerts; "
            "break exact ties by smaller alpha. "
            "Selection is development-only."
        ),
        "zero_alert_policy": "not_applicable",
        "unsupported_policy": (
            "Exclude unsupported NeuralCD targets from this "
            "matched-population study; report 311 separately."
        ),
        "scientific_limitations": (
            "Reuses validation outcomes previously used for "
            "model and event-policy selection. Disagreement is "
            "not independently calibrated epistemic uncertainty. "
            "No intervention is performed and no causal "
            "recovery outcome is measured."
        ),
        "source_sha256": {
            name: sha256(path)
            for name, path in SOURCES.items()
        },
        "individual_response_labels_read": False,
        "test_evaluated": False,
        "test_gate": "closed",
    }

    OUTPUT.write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("DISAGREEMENT EXPERIMENT REGISTERED")
    print("Matched targets:", n)
    print("Candidate scores:", len(candidate_scores))
    print("Primary alert count:", budgets["0.3"])
    print("Individual response labels read: False")
    print("Test evaluated: False")
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
