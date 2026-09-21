"""Tests for deterministic, label-free event detection."""

from dataclasses import FrozenInstanceError

import pytest

from src.uncertainty.bridge import signal_record
from src.uncertainty.event_detector import (
    TriggerConfig,
    detect_event,
)


def signal(p=0.25, *, supported=True):
    return signal_record(
        source_row=12,
        student_id="student-A",
        model="neuralcd_v1",
        supported=supported,
        probability=p if supported else None,
    )


def config(policy):
    return TriggerConfig(
        policy=policy,
        risk_threshold=0.7,
        entropy_threshold=0.8,
    )


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        ("no_trigger", False),
        ("risk_only", True),
        ("entropy_only", True),
        ("risk_or_entropy", True),
        ("risk_and_entropy", True),
    ],
)
def test_p_quarter_policy_outcomes(policy, expected):
    decision = detect_event(signal(0.25), config(policy))

    assert decision.flagged is expected
    assert decision.status == (
        "flag" if expected else "no_flag"
    )


def test_high_failure_risk_but_low_entropy():
    item = signal(0.01)

    risk = detect_event(item, config("risk_only"))
    entropy = detect_event(item, config("entropy_only"))
    combined = detect_event(item, config("risk_or_entropy"))

    assert risk.flagged is True
    assert entropy.flagged is False
    assert combined.flagged is True


def test_high_entropy_without_crossing_risk_threshold():
    item = signal(0.5)

    assert detect_event(
        item, config("risk_only")
    ).flagged is False

    assert detect_event(
        item, config("entropy_only")
    ).flagged is True

    assert detect_event(
        item, config("risk_or_entropy")
    ).flagged is True

    assert detect_event(
        item, config("risk_and_entropy")
    ).flagged is False


def test_high_correctness_does_not_trigger():
    item = signal(0.9)

    for policy in (
        "risk_only",
        "entropy_only",
        "risk_or_entropy",
        "risk_and_entropy",
    ):
        assert detect_event(
            item, config(policy)
        ).flagged is False


@pytest.mark.parametrize(
    "policy",
    [
        "no_trigger",
        "risk_only",
        "entropy_only",
        "risk_or_entropy",
        "risk_and_entropy",
    ],
)
def test_unsupported_item_always_abstains(policy):
    decision = detect_event(
        signal(supported=False),
        config(policy),
    )

    assert decision.status == "abstain"
    assert decision.flagged is None
    assert decision.reason == "unsupported_item"


def test_response_label_cannot_enter_signal():
    item = signal()
    item["observed_correct"] = 1

    with pytest.raises(ValueError, match="label-free"):
        detect_event(item, config("risk_only"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("failure_risk", 0.01),
        ("normalized_predictive_entropy", 0.01),
        ("predictive_entropy_nats", 0.01),
    ],
)
def test_inconsistent_signals_rejected(field, value):
    item = signal()
    item[field] = value

    with pytest.raises(ValueError, match="Inconsistent"):
        detect_event(item, config("risk_only"))


def test_invalid_policy_rejected():
    with pytest.raises(ValueError, match="Unregistered"):
        config("secret_policy")


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("risk_threshold", -0.01),
        ("risk_threshold", 1.01),
        ("risk_threshold", float("nan")),
        ("entropy_threshold", float("inf")),
    ],
)
def test_invalid_threshold_rejected(name, value):
    parameters = {
        "policy": "risk_only",
        "risk_threshold": 0.7,
        "entropy_threshold": 0.8,
    }
    parameters[name] = value

    with pytest.raises(ValueError):
        TriggerConfig(**parameters)


def test_boolean_threshold_rejected():
    with pytest.raises(TypeError):
        TriggerConfig(
            policy="risk_only",
            risk_threshold=True,
            entropy_threshold=0.8,
        )


def test_config_and_decision_are_immutable():
    settings = config("risk_only")
    decision = detect_event(signal(), settings)

    with pytest.raises(FrozenInstanceError):
        settings.risk_threshold = 0.2

    with pytest.raises(FrozenInstanceError):
        decision.flagged = False


def test_decision_preserves_identity():
    decision = detect_event(
        signal(), config("risk_only")
    )

    assert decision.source_row == 12
    assert decision.student_id == "student-A"
    assert decision.model == "neuralcd_v1"
    assert decision.policy == "risk_only"
