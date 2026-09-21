"""Deterministic, label-free event detection from frozen-model signals.

A flag is a research-system alert, not a pedagogical intervention.
Thresholds are supplied by the caller and are not optimized here.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from numbers import Real

from src.uncertainty.bridge import signal_record


POLICIES = frozenset({
    "no_trigger",
    "risk_only",
    "entropy_only",
    "risk_or_entropy",
    "risk_and_entropy",
})

SIGNAL_FIELDS = frozenset({
    "source_row",
    "student_id",
    "model",
    "status",
    "p_correct",
    "failure_risk",
    "predictive_entropy_nats",
    "normalized_predictive_entropy",
})


@dataclass(frozen=True)
class TriggerConfig:
    policy: str
    risk_threshold: float
    entropy_threshold: float

    def __post_init__(self):
        if self.policy not in POLICIES:
            raise ValueError("Unregistered trigger policy")

        for name in ("risk_threshold", "entropy_threshold"):
            value = getattr(self, name)

            if isinstance(value, bool) or not isinstance(
                value, Real
            ):
                raise TypeError(f"{name} must be real-valued")

            value = float(value)

            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")

            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0, 1]")

            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class TriggerDecision:
    source_row: int
    student_id: str
    model: str
    policy: str
    status: str
    flagged: bool | None
    reason: str


def _validate_signal(signal: Mapping) -> dict:
    if not isinstance(signal, Mapping):
        raise TypeError("Signal must be a mapping")

    if set(signal) != SIGNAL_FIELDS:
        raise ValueError(
            "Signal fields differ from the label-free bridge schema"
        )

    status = signal["status"]

    if status not in {
        "supported",
        "unsupported_training_item",
    }:
        raise ValueError("Unknown support status")

    # Reconstruct the expected signal from the probability.
    # This also checks model identity, unsupported-item rules
    # and the probability's validity.
    expected = signal_record(
        source_row=signal["source_row"],
        student_id=signal["student_id"],
        model=signal["model"],
        supported=(status == "supported"),
        probability=signal["p_correct"],
    )

    for field in SIGNAL_FIELDS:
        actual = signal[field]
        correct = expected[field]

        if isinstance(correct, float):
            if isinstance(actual, bool) or not isinstance(
                actual, Real
            ):
                raise ValueError(f"Invalid signal field: {field}")

            if not math.isclose(
                float(actual),
                correct,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError(
                    f"Inconsistent signal field: {field}"
                )
        elif actual != correct:
            raise ValueError(
                f"Inconsistent signal field: {field}"
            )

    return expected


def detect_event(
    signal: Mapping,
    config: TriggerConfig,
) -> TriggerDecision:
    """Classify one pre-response signal; never read its outcome."""

    if not isinstance(config, TriggerConfig):
        raise TypeError("config must be TriggerConfig")

    signal = _validate_signal(signal)

    common = {
        "source_row": signal["source_row"],
        "student_id": signal["student_id"],
        "model": signal["model"],
        "policy": config.policy,
    }

    if signal["status"] == "unsupported_training_item":
        return TriggerDecision(
            **common,
            status="abstain",
            flagged=None,
            reason="unsupported_item",
        )

    if config.policy == "no_trigger":
        return TriggerDecision(
            **common,
            status="no_flag",
            flagged=False,
            reason="control_policy",
        )

    risk_hit = (
        signal["failure_risk"] >= config.risk_threshold
    )

    entropy_hit = (
        signal["normalized_predictive_entropy"]
        >= config.entropy_threshold
    )

    if config.policy == "risk_only":
        flag = risk_hit
    elif config.policy == "entropy_only":
        flag = entropy_hit
    elif config.policy == "risk_or_entropy":
        flag = risk_hit or entropy_hit
    elif config.policy == "risk_and_entropy":
        flag = risk_hit and entropy_hit
    else:
        # Defensive guard even though TriggerConfig checks this.
        raise RuntimeError("Unreachable policy")

    return TriggerDecision(
        **common,
        status="flag" if flag else "no_flag",
        flagged=bool(flag),
        reason=(
            "threshold_condition_met"
            if flag else "threshold_condition_not_met"
        ),
    )
