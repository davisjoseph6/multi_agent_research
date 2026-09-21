"""Simulation-only, fail-closed recovery execution.

No real delivery interface is available. Idempotency is limited
to one in-memory coordinator instance.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from src.recovery.controller import (
    RecoveryContext,
    RecoveryPlan,
    plan_recovery,
)
from src.uncertainty.event_detector import TriggerDecision


OPTIONS = frozenset({
    "optional_hint",
    "optional_scaffold",
})

SIMULATED_OUTCOMES = frozenset({
    "ack",
    "reject",
    "unknown",
    "raise",
})


class SimulatedRejection(Exception):
    """The simulator explicitly rejected an attempt."""


class SimulatedUnknown(Exception):
    """The simulator cannot establish the attempt's outcome."""


@dataclass(frozen=True)
class SimulationApproval:
    """Explicit test approval; not authenticated student consent."""

    operation_id: str
    student_id: str
    source_row: int
    option: str
    approved: bool

    def __post_init__(self):
        if (
            type(self.operation_id) is not str
            or not self.operation_id.strip()
            or len(self.operation_id) > 128
        ):
            raise ValueError("Invalid operation ID")

        if (
            type(self.student_id) is not str
            or not self.student_id.strip()
        ):
            raise ValueError("Invalid student ID")

        if (
            type(self.source_row) is not int
            or self.source_row < 0
        ):
            raise ValueError("Invalid source row")

        if self.option not in OPTIONS:
            raise ValueError("Unknown assistance option")

        if type(self.approved) is not bool:
            raise TypeError("Approval must be explicitly boolean")


@dataclass(frozen=True)
class ExecutionReceipt:
    """Immutable record of a simulated execution attempt."""

    operation_id: str
    student_id: str
    source_row: int
    model: str
    policy: str
    option: str
    state: str
    reason: str
    attempts: int


class SimulatedAssistancePort:
    """Deterministic fake; never contacts students or services."""

    def __init__(self, outcomes=None):
        outcomes = {} if outcomes is None else outcomes

        if type(outcomes) is not dict:
            raise TypeError("Simulation outcomes must be a dictionary")

        for operation_id, outcome in outcomes.items():
            if (
                type(operation_id) is not str
                or not operation_id.strip()
            ):
                raise ValueError("Invalid simulated operation ID")

            if outcome not in SIMULATED_OUTCOMES:
                raise ValueError("Unknown simulated outcome")

        self._outcomes = dict(outcomes)
        self.calls = []

    def dispatch(self, approval: SimulationApproval) -> str:
        """Record one fake call and produce the configured response."""

        self.calls.append(approval.operation_id)

        outcome = self._outcomes.get(
            approval.operation_id,
            "ack",
        )

        if outcome == "reject":
            raise SimulatedRejection(
                "Simulator explicitly rejected the request"
            )

        if outcome == "unknown":
            raise SimulatedUnknown(
                "Simulator acknowledgement unavailable"
            )

        if outcome == "raise":
            raise RuntimeError(
                "Unexpected simulated transport exception"
            )

        return "simulated_ack"


class RecoveryExecutionCoordinator:
    """One-process, one-attempt-per-target simulated coordinator."""

    def __init__(self, port: SimulatedAssistancePort):
        # Restrict v1 to the provided fake implementation.
        if type(port) is not SimulatedAssistancePort:
            raise TypeError(
                "Only SimulatedAssistancePort is allowed in v1"
            )

        self._port = port
        self._lock = RLock()

        # operation_id -> (request fingerprint, receipt)
        self._records = {}

        # (student_id, source_row) -> operation_id
        self._claimed_targets = {}

    def submit(
        self,
        decision: TriggerDecision,
        *,
        context: RecoveryContext,
        plan: RecoveryPlan,
        approval: SimulationApproval,
    ) -> ExecutionReceipt:
        """Submit at most one simulated attempt per target."""

        if type(plan) is not RecoveryPlan:
            raise TypeError("Expected RecoveryPlan")

        if type(approval) is not SimulationApproval:
            raise TypeError("Expected SimulationApproval")

        # Recompute the proposal; a fabricated or stale plan
        # cannot bypass the controller's permission rules.
        expected = plan_recovery(
            decision,
            context=context,
        )

        if plan != expected:
            raise ValueError(
                "Proposal does not match current decision and context"
            )

        if plan.disposition != "proposed":
            raise ValueError(
                "Only proposed assistance can be submitted"
            )

        if approval.approved is not True:
            raise ValueError(
                "Explicit simulation approval is required"
            )

        if (
            approval.student_id != plan.student_id
            or approval.source_row != plan.source_row
        ):
            raise ValueError(
                "Approval target does not match proposal"
            )

        if approval.option not in plan.proposed_options:
            raise ValueError(
                "Approved option is not available in proposal"
            )

        target = (
            plan.student_id,
            plan.source_row,
        )

        fingerprint = (
            plan,
            approval.student_id,
            approval.source_row,
            approval.option,
            approval.approved,
        )

        with self._lock:
            existing = self._records.get(
                approval.operation_id
            )

            if existing is not None:
                previous_fingerprint, previous_receipt = existing

                if previous_fingerprint != fingerprint:
                    raise ValueError(
                        "Operation ID reused with different parameters"
                    )

                return previous_receipt

            previous_operation = self._claimed_targets.get(target)

            if previous_operation is not None:
                raise ValueError(
                    "Target already has a recorded execution attempt"
                )

            # Claim and record BEFORE contacting the fake port.
            initial = ExecutionReceipt(
                operation_id=approval.operation_id,
                student_id=plan.student_id,
                source_row=plan.source_row,
                model=plan.model,
                policy=plan.policy,
                option=approval.option,
                state="attempt_recorded",
                reason="simulated_dispatch_pending",
                attempts=1,
            )

            self._claimed_targets[target] = approval.operation_id

            self._records[approval.operation_id] = (
                fingerprint,
                initial,
            )

            try:
                acknowledgement = self._port.dispatch(
                    approval
                )

                if acknowledgement == "simulated_ack":
                    state = "simulated_succeeded"
                    reason = "simulator_acknowledged"
                else:
                    state = "outcome_unknown"
                    reason = "unexpected_simulator_response"

            except SimulatedRejection:
                state = "simulated_failed"
                reason = "simulator_explicitly_rejected"

            except SimulatedUnknown:
                state = "outcome_unknown"
                reason = "simulator_outcome_unconfirmed"

            except Exception:
                # Unexpected exceptions are not proof that no
                # request was processed. Never retry blindly.
                state = "outcome_unknown"
                reason = "unexpected_simulator_exception"

            final = ExecutionReceipt(
                operation_id=approval.operation_id,
                student_id=plan.student_id,
                source_row=plan.source_row,
                model=plan.model,
                policy=plan.policy,
                option=approval.option,
                state=state,
                reason=reason,
                attempts=1,
            )

            self._records[approval.operation_id] = (
                fingerprint,
                final,
            )

            return final
