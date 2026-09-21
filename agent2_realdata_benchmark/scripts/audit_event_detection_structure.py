#!/usr/bin/env python3
"""Audit selected trigger geometry and overlap without response labels.

This is post-selection interpretation, not a new policy search.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.uncertainty.predictive import signal_from_probability


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/data"

SPEC_FILE = DOCS / "event_detection_experiment_v1.json"
REPORT_FILE = DOCS / "event_detection_validation_v1.json"
BRIDGE_FILE = DOCS / "uncertainty_validation_bridge_v1.json"

SIGNALS_FILE = (
    ROOT / "results/uncertainty/validation_signals_v1.parquet"
)

DECISIONS_FILE = (
    ROOT / "results/uncertainty/event_detection_selected_v1.parquet"
)

OUTPUT = DOCS / "event_detection_structure_audit_v1.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def upper_entropy_cutoff(threshold):
    """Upper solution of normalized Bernoulli entropy = threshold."""
    low, high = 0.5, 1.0

    for _ in range(80):
        middle = (low + high) / 2.0
        entropy = signal_from_probability(
            middle
        ).normalized_predictive_entropy

        if entropy >= threshold:
            low = middle
        else:
            high = middle

    return (low + high) / 2.0


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)

    spec = read(SPEC_FILE)
    report = read(REPORT_FILE)
    bridge = read(BRIDGE_FILE)

    assert report["registration_sha256"] == sha256(SPEC_FILE)
    assert report["selected_decisions_sha256"] == sha256(
        DECISIONS_FILE
    )
    assert bridge["output_sha256"] == sha256(SIGNALS_FILE)

    assert report["test_evaluated"] is False
    assert report["test_gate"] == "closed"

    selected_bkt = report["selected"]["bkt_v1"]
    selected_neural = report["selected"]["neuralcd_v1"]

    assert (
        selected_bkt["policy"],
        selected_bkt["risk_threshold"],
        selected_bkt["entropy_threshold"],
    ) == ("risk_or_entropy", 0.5, 0.95)

    assert (
        selected_neural["policy"],
        selected_neural["risk_threshold"],
    ) == ("risk_only", 0.5)

    # These files contain signals and decisions, not response outcomes.
    signals = pd.read_parquet(SIGNALS_FILE)
    decisions = pd.read_parquet(DECISIONS_FILE)

    forbidden = {"correct", "observed_correct", "outcome"}

    assert not forbidden.intersection(signals.columns)
    assert not forbidden.intersection(decisions.columns)

    assert len(signals) == len(decisions) == 85496

    keys = ["source_row", "student_id", "model", "status"]

    assert not signals.duplicated(
        ["source_row", "model"]
    ).any()

    assert not decisions.duplicated(
        ["source_row", "model"]
    ).any()

    joined = decisions.merge(
        signals,
        on=keys,
        how="inner",
        validate="one_to_one",
    )

    assert len(joined) == 85496

    bkt = joined.loc[
        joined["model"] == "bkt_v1"
    ].copy()

    neural = joined.loc[
        joined["model"] == "neuralcd_v1"
    ].copy()

    assert len(bkt) == len(neural) == 42748
    assert bkt["status"].eq("supported").all()
    assert bkt["flagged"].notna().all()

    unsupported = neural[
        "status"
    ].eq("unsupported_training_item")

    assert int(unsupported.sum()) == 311
    assert neural.loc[
        unsupported, "flagged"
    ].isna().all()

    supported_neural = neural.loc[~unsupported].copy()

    assert len(supported_neural) == 42437
    assert supported_neural["flagged"].notna().all()

    p = bkt["p_correct"].to_numpy(dtype=float)
    entropy = bkt[
        "normalized_predictive_entropy"
    ].to_numpy(dtype=float)

    observed_bkt_flags = bkt[
        "flagged"
    ].astype(bool).to_numpy()

    assert np.isfinite(p).all()
    assert np.isfinite(entropy).all()

    # Independently reconstruct the selected logical policy.
    logical_flags = (
        (1.0 - p >= 0.5)
        | (entropy >= 0.95)
    )

    np.testing.assert_array_equal(
        observed_bkt_flags,
        logical_flags,
    )

    cutoff = upper_entropy_cutoff(0.95)

    # For this particular OR configuration, the union of the
    # two intervals is one contiguous probability threshold.
    equivalent_risk_only = p <= cutoff

    np.testing.assert_array_equal(
        observed_bkt_flags,
        equivalent_risk_only,
    )

    neural_p = supported_neural[
        "p_correct"
    ].to_numpy(dtype=float)

    observed_neural_flags = supported_neural[
        "flagged"
    ].astype(bool).to_numpy()

    np.testing.assert_array_equal(
        observed_neural_flags,
        neural_p <= 0.5,
    )

    bkt_matched = bkt[[
        "source_row", "student_id", "flagged"
    ]].merge(
        supported_neural[[
            "source_row", "student_id", "flagged"
        ]],
        on=["source_row", "student_id"],
        how="inner",
        validate="one_to_one",
        suffixes=("_bkt", "_neural"),
    )

    assert len(bkt_matched) == 42437

    fb = bkt_matched[
        "flagged_bkt"
    ].astype(bool).to_numpy()

    fn = bkt_matched[
        "flagged_neural"
    ].astype(bool).to_numpy()

    overlap = {
        "both_flag": int(np.sum(fb & fn)),
        "bkt_only_flag": int(np.sum(fb & ~fn)),
        "neuralcd_only_flag": int(np.sum(~fb & fn)),
        "neither_flags": int(np.sum(~fb & ~fn)),
    }

    assert sum(overlap.values()) == 42437

    assert (
        overlap["both_flag"] + overlap["bkt_only_flag"]
        == selected_bkt["metrics"]["alerts"]
    )

    assert (
        overlap["both_flag"] + overlap["neuralcd_only_flag"]
        == selected_neural["metrics"]["alerts"]
    )

    unsupported_rows = set(
        neural.loc[unsupported, "source_row"].tolist()
    )

    bkt_alerts_on_neuralcd_unsupported = int(
        bkt.loc[
            bkt["source_row"].isin(unsupported_rows),
            "flagged",
        ].astype(bool).sum()
    )

    assert (
        selected_bkt["metrics"]["alerts"]
        + bkt_alerts_on_neuralcd_unsupported
        == report["selected_bkt_full_coverage"]["alerts"]
    )

    result = {
        "version": "event_detection_structure_audit_v1",
        "status": "selected_policy_structure_verified",
        "registration_sha256": sha256(SPEC_FILE),
        "validation_report_sha256": sha256(REPORT_FILE),
        "signals_sha256": sha256(SIGNALS_FILE),
        "selected_decisions_sha256": sha256(DECISIONS_FILE),
        "bkt_selected_policy": "risk_or_entropy",
        "bkt_equivalent_probability_cutoff": cutoff,
        "bkt_equivalent_failure_risk_threshold": 1.0 - cutoff,
        "bkt_exact_decision_mismatches": 0,
        "neuralcd_exact_decision_mismatches": 0,
        "matched_targets": 42437,
        "matched_flag_overlap": overlap,
        "neuralcd_abstentions": 311,
        "bkt_alerts_on_neuralcd_unsupported":
            bkt_alerts_on_neuralcd_unsupported,
        "interpretation": (
            "The selected BKT OR policy is equivalent to a "
            "single probability cutoff. This is a mathematical "
            "description, not a new registered candidate or "
            "a revised policy selection. Overlap is descriptive."
        ),
        "individual_response_labels_read": False,
        "test_evaluated": False,
        "test_gate": "closed",
    }

    OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("EVENT-DETECTION STRUCTURE AUDIT PASSED")
    print("BKT probability cutoff:", cutoff)
    print("Equivalent failure-risk threshold:", 1.0 - cutoff)
    print("BKT decision mismatches: 0")
    print("NeuralCD decision mismatches: 0")
    print("Matched flag overlap:")
    print(json.dumps(overlap, indent=2))
    print(
        "BKT alerts on NeuralCD-unsupported targets:",
        bkt_alerts_on_neuralcd_unsupported,
    )
    print("Individual response labels read: False")
    print("Test evaluated: False")
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
