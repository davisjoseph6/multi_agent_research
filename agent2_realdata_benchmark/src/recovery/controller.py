"""Fail-closed, pre-response recovery action planner.

Produces proposals only. Does not deliver pedagogical actions,
consume response outcomes, or alter frozen model parameters.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.uncertainty.event_detector import (
    POLICIES,
    TriggerDecision,
)


@dataclass(frozen=True)
class RecoveryContext:
    """Explicit information available before any action is offered."""

    permission_to_offer: bool
    hint_available: bool
    scaffold_available: bool

    def __post_init__(self):
        for name in (
            "permission_to_offer",
            "hint_available",
            "scaffold_available",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be explicitly boolean")


@dataclass(frozen=True)
class RecoveryPlan:
    """A proposed disposition; never evidence of action delivery."""

    source_row: int
    student_id: str
    model: str
    policy: str
    detector_status: str
    disposition: str
    proposed_options: tuple[str, ...]
    reason: str


def _validate_decision(decision: TriggerDecision) -> None:
    if type(decision) is not TriggerDecision:
        raise TypeError("Expected a frozen TriggerDecision")

    if type(decision.source_row) is not int or decision.source_row < 0:
        raise ValueError("Invalid source row")

    if (
        not isinstance(decision.student_id, str)
        or not decision.student_id.strip()
    ):
        raise ValueError("Invalid student identifier")

    if decision.model not in ("bkt_v1", "neuralcd_v1"):
        raise ValueError("Unknown frozen model")

    if decision.policy not in POLICIES:
        raise ValueError("Unknown event policy")

    valid_states = {
        "flag": (True, {"threshold_condition_met"}),
        "no_flag": (
            False,
            {
                "threshold_condition_not_met",
                "control_policy",
            },
        ),
        "abstain": (None, {"unsupported_item"}),
    }

    if decision.status not in valid_states:
        raise ValueError("Unknown event status")

    expected_flag, reasons = valid_states[decision.status]

    if decision.flagged is not expected_flag:
        raise ValueError("Inconsistent flag and status")

    if decision.reason not in reasons:
        raise ValueError("Inconsistent detector reason")

    if (
        decision.status == "abstain"
        and decision.model != "neuralcd_v1"
    ):
        raise ValueError("BKT cannot abstain for unsupported items")

    if (
        decision.reason == "control_policy"
        and decision.policy != "no_trigger"
    ):
        raise ValueError("Invalid control-policy reason")

    if (
        decision.policy == "no_trigger"
        and (
            decision.status != "no_flag"
            or decision.reason != "control_policy"
        )
    ):
        # The one exception is an unsupported NeuralCD item:
        # the detector preserves abstention even for no_trigger.
        if decision.status != "abstain":
            raise ValueError("Inconsistent no-trigger decision")


def plan_recovery(
    decision: TriggerDecision,
    *,
    context: RecoveryContext,
) -> RecoveryPlan:
    """Create one deterministic, label-free action proposal."""

    _validate_decision(decision)

    if type(context) is not RecoveryContext:
        raise TypeError("Expected RecoveryContext")

    common = {
        "source_row": decision.source_row,
        "student_id": decision.student_id,
        "model": decision.model,
        "policy": decision.policy,
        "detector_status": decision.status,
    }

    if decision.status == "abstain":
        return RecoveryPlan(
            **common,
            disposition="abstain",
            proposed_options=(),
            reason="unsupported_prediction",
        )

    if decision.status == "no_flag":
        return RecoveryPlan(
            **common,
            disposition="no_action",
            proposed_options=(),
            reason="event_not_flagged",
        )

    if not context.permission_to_offer:
        return RecoveryPlan(
            **common,
            disposition="blocked",
            proposed_options=(),
            reason="permission_not_granted",
        )

    options = []

    if context.hint_available:
        options.append("optional_hint")

    if context.scaffold_available:
        options.append("optional_scaffold")

    if not options:
        return RecoveryPlan(
            **common,
            disposition="deferred",
            proposed_options=(),
            reason="no_assistance_resource_available",
        )

    return RecoveryPlan(
        **common,
        disposition="proposed",
        proposed_options=tuple(options),
        reason="permitted_assistance_options_available",
    )
