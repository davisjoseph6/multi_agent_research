#!/usr/bin/env python3
"""Evaluate preregistered event policies on validation outcomes only.

All policy decisions are generated before response labels are loaded.
No test data, model fitting, or intervention simulation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.uncertainty.bridge import signal_record
from src.uncertainty.event_detector import (
    TriggerConfig,
    detect_event,
    SIGNAL_FIELDS,
)


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/data"

SPEC_FILE = DOCS / "event_detection_experiment_v1.json"
BRIDGE_FILE = DOCS / "uncertainty_validation_bridge_v1.json"

SIGNALS_FILE = (
    ROOT / "results/uncertainty/validation_signals_v1.parquet"
)

BKT_FILE = (
    ROOT / "results/bkt/frozen_v1_validation_predictions.parquet"
)

OUTPUT = DOCS / "event_detection_validation_v1.json"

DECISIONS = (
    ROOT
    / "results/uncertainty/event_detection_selected_v1.parquet"
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def score(flags, negative):
    """Confusion matrix where a negative response is a positive event."""

    flags = np.asarray(flags, dtype=bool)
    negative = np.asarray(negative, dtype=bool)

    if flags.ndim != 1 or negative.ndim != 1:
        raise ValueError("Expected one-dimensional arrays")

    if len(flags) != len(negative) or len(flags) == 0:
        raise ValueError("Invalid paired evaluation population")

    tp = int(np.sum(flags & negative))
    fp = int(np.sum(flags & ~negative))
    fn = int(np.sum(~flags & negative))
    tn = int(np.sum(~flags & ~negative))

    n = len(flags)
    alerts = tp + fp

    assert tp + fp + fn + tn == n
    assert tp + fn > 0
    assert fp + tn > 0

    return {
        "count": n,
        "negative_responses": tp + fn,
        "positive_responses": fp + tn,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "alerts": alerts,
        "alert_rate": alerts / n,
        "precision": tp / alerts if alerts else None,
        "recall": tp / (tp + fn),
        "false_positive_rate": fp / (fp + tn),
    }


def select_candidate(records, policy_order):
    """Apply the registered lexicographic selection rule."""

    eligible = [
        row for row in records
        if row["within_alert_budget"]
    ]

    if not eligible:
        raise RuntimeError("No eligible policy")

    def key(row):
        return (
            -row["metrics"]["tp"],
            row["metrics"]["fp"],
            row["metrics"]["alerts"],
            policy_order.index(row["policy"]),
            row["risk_threshold"],
            row["entropy_threshold"],
        )

    return min(eligible, key=key)


def main():
    if OUTPUT.exists() or DECISIONS.exists():
        raise FileExistsError(
            "Evaluation artifacts exist; refusing to overwrite"
        )

    spec = read(SPEC_FILE)
    bridge = read(BRIDGE_FILE)

    assert spec["status"] == (
        "registered_before_label_evaluation"
    )
    assert spec["validation_response_labels_accessed"] is False
    assert spec["test_evaluated"] is False
    assert spec["test_gate"] == "closed"

    assert spec["candidate_count_per_model"] == 25
    assert spec["model_candidate_count"] == 50
    assert len(spec["candidates"]) == 25
    assert spec["selection_target_count"] == 42437
    assert spec["alert_budget_fraction"] == 0.30
    assert spec["target"] == "correct_equals_zero"

    assert spec["models"] == ["bkt_v1", "neuralcd_v1"]

    sources = {
        "signals": SIGNALS_FILE,
        "bridge_report": BRIDGE_FILE,
        "bkt_freeze": DOCS / "bkt_v1_frozen.json",
        "neuralcd_freeze": DOCS / "neuralcd_v1_frozen.json",
        "event_detector":
            ROOT / "src/uncertainty/event_detector.py",
        "event_bridge": ROOT / "src/uncertainty/bridge.py",
        "test_gate": ROOT / "docs/phase6_test_gate_v1.md",
    }

    for name, path in sources.items():
        if sha256(path) != spec["source_sha256"][name]:
            raise RuntimeError(f"Registered source changed: {name}")

    assert sha256(SIGNALS_FILE) == bridge["output_sha256"]
    assert sha256(BKT_FILE) == bridge["bkt_predictions_sha256"]

    assert bridge["no_response_labels_read"] is True
    assert bridge["test_evaluated"] is False

    # PHASE A: Create decisions using LABEL-FREE signals only.
    signals = pd.read_parquet(SIGNALS_FILE)

    if set(signals.columns) != SIGNAL_FIELDS:
        raise RuntimeError("Unexpected signal columns")

    if any(
        name in signals.columns
        for name in ("correct", "observed_correct", "outcome")
    ):
        raise RuntimeError("Response labels entered signal dataset")

    assert len(signals) == 85496

    if signals.duplicated(["source_row", "model"]).any():
        raise RuntimeError("Duplicate model-target pair")

    bkt = signals.loc[
        signals["model"].eq("bkt_v1")
    ].sort_values("source_row").reset_index(drop=True)

    neural = signals.loc[
        signals["model"].eq("neuralcd_v1")
    ].sort_values("source_row").reset_index(drop=True)

    assert len(bkt) == len(neural) == 42748

    np.testing.assert_array_equal(
        bkt["source_row"].to_numpy(),
        neural["source_row"].to_numpy(),
    )

    np.testing.assert_array_equal(
        bkt["student_id"].to_numpy(),
        neural["student_id"].to_numpy(),
    )

    assert bkt["status"].eq("supported").all()

    supported = neural["status"].eq("supported").to_numpy()
    unsupported = neural["status"].eq(
        "unsupported_training_item"
    ).to_numpy()

    assert int(supported.sum()) == 42437
    assert int(unsupported.sum()) == 311
    assert np.all(supported | unsupported)

    value_columns = [
        "p_correct",
        "failure_risk",
        "predictive_entropy_nats",
        "normalized_predictive_entropy",
    ]

    assert neural.loc[
        unsupported, value_columns
    ].isna().all().all()

    bkt_records = bkt.to_dict(orient="records")

    neural_records = neural.loc[
        supported
    ].to_dict(orient="records")

    assert len(bkt_records) == 42748
    assert len(neural_records) == 42437

    # Every registered policy is applied by the ACTUAL detector,
    # not by a separate approximation of its threshold logic.
    flags_by_model = {
        "bkt_v1": [],
        "neuralcd_v1": [],
    }

    for candidate in spec["candidates"]:
        config = TriggerConfig(**candidate)

        for model, records in (
            ("bkt_v1", bkt_records),
            ("neuralcd_v1", neural_records),
        ):
            decisions = [
                detect_event(record, config)
                for record in records
            ]

            if any(
                decision.status not in ("flag", "no_flag")
                or decision.flagged is None
                for decision in decisions
            ):
                raise RuntimeError(
                    f"Invalid supported decision: {model}"
                )

            flags_by_model[model].append(
                np.fromiter(
                    (decision.flagged for decision in decisions),
                    dtype=bool,
                    count=len(decisions),
                )
            )

    assert all(
        len(flags_by_model[model]) == 25
        for model in spec["models"]
    )

    # Unsupported items abstain under every registered policy.
    for candidate in spec["candidates"]:
        config = TriggerConfig(**candidate)

        for row in neural.loc[
            unsupported, ["source_row", "student_id"]
        ].itertuples(index=False):
            record = signal_record(
                source_row=int(row.source_row),
                student_id=str(row.student_id),
                model="neuralcd_v1",
                supported=False,
                probability=None,
            )

            decision = detect_event(record, config)

            if (
                decision.status != "abstain"
                or decision.flagged is not None
            ):
                raise RuntimeError(
                    "Unsupported item was not an abstention"
                )

    print(
        "ALL 50 LABEL-FREE CANDIDATE DECISIONS GENERATED",
        flush=True,
    )

    # PHASE B: Labels enter only after all decisions exist.
    outcomes = pd.read_parquet(
        BKT_FILE,
        columns=[
            "source_row",
            "student_id",
            "observed_correct",
        ],
    ).sort_values("source_row").reset_index(drop=True)

    assert len(outcomes) == 42748
    assert outcomes["source_row"].is_unique

    np.testing.assert_array_equal(
        outcomes["source_row"].to_numpy(),
        bkt["source_row"].to_numpy(),
    )

    np.testing.assert_array_equal(
        outcomes["student_id"].astype(str).to_numpy(),
        bkt["student_id"].astype(str).to_numpy(),
    )

    y = outcomes["observed_correct"].to_numpy()

    if not np.isin(y, [0, 1]).all():
        raise RuntimeError("Invalid binary response labels")

    negative_full = y == 0
    negative_matched = negative_full[supported]

    assert len(negative_matched) == 42437

    results = {}
    selections = {}

    for model in spec["models"]:
        candidates = []

        for index, candidate in enumerate(spec["candidates"]):
            all_flags = flags_by_model[model][index]

            matched_flags = (
                all_flags[supported]
                if model == "bkt_v1"
                else all_flags
            )

            metrics = score(
                matched_flags,
                negative_matched,
            )

            assert metrics["count"] == 42437

            row = {
                **candidate,
                "metrics": metrics,
                "within_alert_budget": (
                    metrics["alert_rate"]
                    <= spec["alert_budget_fraction"]
                ),
            }

            candidates.append(row)

        assert len(candidates) == 25

        control = candidates[0]

        assert control["policy"] == "no_trigger"
        assert control["metrics"]["alerts"] == 0

        selected = select_candidate(
            candidates,
            spec["policy_order"],
        )

        results[model] = candidates
        selections[model] = selected

    assert sum(len(v) for v in results.values()) == 50

    # Report separate, full-coverage BKT performance under
    # its selected policy. NeuralCD abstentions remain separate.
    bkt_selected_index = spec["candidates"].index({
        key: selections["bkt_v1"][key]
        for key in (
            "policy",
            "risk_threshold",
            "entropy_threshold",
        )
    })

    full_bkt_metrics = score(
        flags_by_model["bkt_v1"][bkt_selected_index],
        negative_full,
    )

    assert full_bkt_metrics["count"] == 42748

    # Preserve selected decisions without outcome labels.
    decision_frames = []

    for model, frame in (
        ("bkt_v1", bkt),
        ("neuralcd_v1", neural),
    ):
        chosen = selections[model]

        index = spec["candidates"].index({
            key: chosen[key]
            for key in (
                "policy",
                "risk_threshold",
                "entropy_threshold",
            )
        })

        if model == "bkt_v1":
            selected_flags = pd.Series(
                flags_by_model[model][index],
                dtype="boolean",
            )
        else:
            selected_flags = pd.Series(
                pd.NA,
                index=range(len(frame)),
                dtype="boolean",
            )

            selected_flags.loc[supported] = (
                flags_by_model[model][index]
            )

        decision_frames.append(pd.DataFrame({
            "source_row": frame["source_row"],
            "student_id": frame["student_id"],
            "model": model,
            "status": frame["status"],
            "flagged": selected_flags,
            "policy": chosen["policy"],
            "risk_threshold": chosen["risk_threshold"],
            "entropy_threshold": chosen["entropy_threshold"],
        }))

    decision_table = pd.concat(
        decision_frames,
        ignore_index=True,
    ).sort_values(
        ["source_row", "model"]
    ).reset_index(drop=True)

    assert len(decision_table) == 85496
    assert not decision_table.duplicated(
        ["source_row", "model"]
    ).any()

    missing_flags = decision_table["flagged"].isna()

    assert int(missing_flags.sum()) == 311
    assert decision_table.loc[
        missing_flags, "status"
    ].eq("unsupported_training_item").all()

    DECISIONS.parent.mkdir(parents=True, exist_ok=True)

    decision_table.to_parquet(
        DECISIONS,
        index=False,
    )

    assert len(pd.read_parquet(DECISIONS)) == 85496

    report = {
        "version": "event_detection_validation_v1",
        "status": "validation_policy_selection_completed",
        "registration_sha256": sha256(SPEC_FILE),
        "evaluation_code_sha256": sha256(Path(__file__)),
        "signals_sha256": sha256(SIGNALS_FILE),
        "label_source_sha256": sha256(BKT_FILE),
        "selected_decisions_sha256": sha256(DECISIONS),
        "matched_targets": 42437,
        "eligible_primary_targets": 42748,
        "neuralcd_abstentions": 311,
        "candidate_results": results,
        "selected": selections,
        "selected_bkt_full_coverage": full_bkt_metrics,
        "interpretation": (
            "Offline detection of observed negative responses, "
            "not intervention need or causal recovery. Selection "
            "uses validation outcomes; these are development metrics."
        ),
        "validation_response_labels_accessed_for_scoring": True,
        "test_evaluated": False,
        "test_gate": "closed",
    }

    OUTPUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("\nEVENT DETECTION EVALUATION COMPLETE")

    for model in spec["models"]:
        print(f"\n{model}:")
        print(json.dumps(selections[model], indent=2))

    print("\nBKT full coverage:")
    print(json.dumps(full_bkt_metrics, indent=2))
    print("\nNeuralCD abstentions: 311")
    print("Test evaluated: False")
    print("Saved:", OUTPUT)
    print("Selected decisions:", DECISIONS)


if __name__ == "__main__":
    main()
