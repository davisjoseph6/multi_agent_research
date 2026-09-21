"""Synthetic tests for the fail-closed recovery planner."""

from dataclasses import FrozenInstanceError

import pytest

from src.recovery.controller import (
    RecoveryContext,
    plan_recovery,
)
from src.uncertainty.bridge import signal_record
from src.uncertainty.event_detector import (
    TriggerConfig,
    TriggerDecision,
    detect_event,
)


def context(
    permission=True,
    hint=True,
    scaffold=True,
):
    return RecoveryContext(
        permission_to_offer=permission,
        hint_available=hint,
        scaffold_available=scaffold,
    )


def decision(
    p=0.1,
    *,
    supported=True,
    policy="risk_only",
    model="neuralcd_v1",
):
    signal = signal_record(
        source_row=12,
        student_id="synthetic-student",
        model=model,
        supported=supported,
        probability=p if supported else None,
    )

    return detect_event(
        signal,
        TriggerConfig(
            policy=policy,
            risk_threshold=0.7,
            entropy_threshold=0.8,
        ),
    )


def test_flag_proposes_both_available_options():
    result = plan_recovery(
        decision(),
        context=context(),
    )

    assert result.detector_status == "flag"
    assert result.disposition == "proposed"
    assert result.proposed_options == (
        "optional_hint",
        "optional_scaffold",
    )


def test_no_flag_cannot_propose_assistance():
    result = plan_recovery(
        decision(p=0.9),
        context=context(),
    )

    assert result.disposition == "no_action"
    assert result.proposed_options == ()


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
def test_unsupported_item_remains_abstention(policy):
    result = plan_recovery(
        decision(supported=False, policy=policy),
        context=context(),
    )

    assert result.disposition == "abstain"
    assert result.detector_status == "abstain"
    assert result.proposed_options == ()


def test_permission_absent_blocks_flagged_assistance():
    result = plan_recovery(
        decision(),
        context=context(permission=False),
    )

    assert result.disposition == "blocked"
    assert result.reason == "permission_not_granted"
    assert result.proposed_options == ()


def test_no_resources_defers():
    result = plan_recovery(
        decision(),
        context=context(hint=False, scaffold=False),
    )

    assert result.disposition == "deferred"
    assert result.proposed_options == ()


def test_hint_only():
    result = plan_recovery(
        decision(),
        context=context(scaffold=False),
    )

    assert result.proposed_options == ("optional_hint",)


def test_scaffold_only():
    result = plan_recovery(
        decision(),
        context=context(hint=False),
    )

    assert result.proposed_options == ("optional_scaffold",)


def test_no_trigger_never_proposes():
    result = plan_recovery(
        decision(policy="no_trigger"),
        context=context(),
    )

    assert result.disposition == "no_action"
    assert result.proposed_options == ()


def test_idempotent_pure_planning():
    event = decision()
    resources = context()

    assert plan_recovery(
        event, context=resources
    ) == plan_recovery(
        event, context=resources
    )


@pytest.mark.parametrize(
    "field",
    [
        "permission_to_offer",
        "hint_available",
        "scaffold_available",
    ],
)
def test_context_rejects_non_boolean_values(field):
    values = {
        "permission_to_offer": True,
        "hint_available": True,
        "scaffold_available": True,
    }

    values[field] = 1

    with pytest.raises(TypeError):
        RecoveryContext(**values)


def test_rejects_arbitrary_mapping_and_extra_outcome():
    event = decision()

    contaminated = {
        **vars(event),
        "observed_correct": 0,
    }

    with pytest.raises(TypeError):
        plan_recovery(
            contaminated,
            context=context(),
        )


def test_rejects_inconsistent_trigger_decision():
    forged = TriggerDecision(
        source_row=12,
        student_id="synthetic-student",
        model="neuralcd_v1",
        policy="risk_only",
        status="flag",
        flagged=False,
        reason="threshold_condition_met",
    )

    with pytest.raises(ValueError, match="Inconsistent"):
        plan_recovery(
            forged,
            context=context(),
        )


def test_rejects_unrecognized_event_policy():
    forged = TriggerDecision(
        source_row=12,
        student_id="synthetic-student",
        model="neuralcd_v1",
        policy="unregistered",
        status="flag",
        flagged=True,
        reason="threshold_condition_met",
    )

    with pytest.raises(ValueError, match="Unknown"):
        plan_recovery(
            forged,
            context=context(),
        )


def test_rejects_response_label_argument():
    with pytest.raises(TypeError):
        plan_recovery(
            decision(),
            context=context(),
            observed_correct=1,
        )


def test_plan_is_immutable():
    result = plan_recovery(
        decision(),
        context=context(),
    )

    with pytest.raises(FrozenInstanceError):
        result.disposition = "delivered"
