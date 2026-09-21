"""Synthetic-only tests for the recovery execution coordinator."""

from dataclasses import FrozenInstanceError

import pytest

from src.recovery.controller import (
    RecoveryContext,
    plan_recovery,
)
from src.recovery.execution import (
    RecoveryExecutionCoordinator,
    SimulatedAssistancePort,
    SimulationApproval,
)
from src.uncertainty.bridge import signal_record
from src.uncertainty.event_detector import (
    TriggerConfig,
    detect_event,
)


def make_case(
    *,
    probability=0.1,
    supported=True,
    model="neuralcd_v1",
    permission=True,
    hint=True,
    scaffold=True,
    policy="risk_only",
):
    signal = signal_record(
        source_row=12,
        student_id="synthetic-student",
        model=model,
        supported=supported,
        probability=probability if supported else None,
    )

    decision = detect_event(
        signal,
        TriggerConfig(
            policy=policy,
            risk_threshold=0.7,
            entropy_threshold=0.8,
        ),
    )

    context = RecoveryContext(
        permission_to_offer=permission,
        hint_available=hint,
        scaffold_available=scaffold,
    )

    plan = plan_recovery(
        decision,
        context=context,
    )

    return decision, context, plan


def approve(
    *,
    operation_id="sim-001",
    option="optional_hint",
    approved=True,
    student_id="synthetic-student",
    source_row=12,
):
    return SimulationApproval(
        operation_id=operation_id,
        student_id=student_id,
        source_row=source_row,
        option=option,
        approved=approved,
    )


def submit(coordinator, case, approval=None):
    decision, context, plan = case

    return coordinator.submit(
        decision,
        context=context,
        plan=plan,
        approval=approve() if approval is None else approval,
    )


def test_acknowledged_simulation():
    port = SimulatedAssistancePort()
    coordinator = RecoveryExecutionCoordinator(port)

    receipt = submit(coordinator, make_case())

    assert receipt.state == "simulated_succeeded"
    assert receipt.reason == "simulator_acknowledged"
    assert receipt.attempts == 1
    assert receipt.option == "optional_hint"
    assert port.calls == ["sim-001"]


@pytest.mark.parametrize(
    ("outcome", "expected_state"),
    [
        ("ack", "simulated_succeeded"),
        ("reject", "simulated_failed"),
        ("unknown", "outcome_unknown"),
        ("raise", "outcome_unknown"),
    ],
)
def test_same_operation_never_dispatches_twice(
    outcome,
    expected_state,
):
    port = SimulatedAssistancePort({
        "sim-001": outcome,
    })

    coordinator = RecoveryExecutionCoordinator(port)
    case = make_case()

    first = submit(coordinator, case)
    second = submit(coordinator, case)

    assert first == second
    assert first.state == expected_state
    assert first.attempts == 1
    assert port.calls == ["sim-001"]


@pytest.mark.parametrize(
    "state",
    [
        "no_flag",
        "abstain",
        "blocked",
        "deferred",
    ],
)
def test_nonproposals_never_reach_port(state):
    cases = {
        "no_flag": make_case(probability=0.9),
        "abstain": make_case(supported=False),
        "blocked": make_case(permission=False),
        "deferred": make_case(hint=False, scaffold=False),
    }

    port = SimulatedAssistancePort()
    coordinator = RecoveryExecutionCoordinator(port)

    with pytest.raises(ValueError, match="Only proposed"):
        submit(coordinator, cases[state])

    assert port.calls == []


def test_unapproved_request_cannot_dispatch():
    port = SimulatedAssistancePort()
    coordinator = RecoveryExecutionCoordinator(port)

    with pytest.raises(ValueError, match="approval"):
        submit(
            coordinator,
            make_case(),
            approve(approved=False),
        )

    assert port.calls == []


def test_unavailable_option_cannot_dispatch():
    port = SimulatedAssistancePort()
    coordinator = RecoveryExecutionCoordinator(port)

    with pytest.raises(ValueError, match="not available"):
        submit(
            coordinator,
            make_case(scaffold=False),
            approve(option="optional_scaffold"),
        )

    assert port.calls == []


def test_approval_must_match_student():
    port = SimulatedAssistancePort()
    coordinator = RecoveryExecutionCoordinator(port)

    with pytest.raises(ValueError, match="target"):
        submit(
            coordinator,
            make_case(),
            approve(student_id="different-student"),
        )

    assert port.calls == []


def test_approval_must_match_source_row():
    port = SimulatedAssistancePort()
    coordinator = RecoveryExecutionCoordinator(port)

    with pytest.raises(ValueError, match="target"):
        submit(
            coordinator,
            make_case(),
            approve(source_row=99),
        )

    assert port.calls == []


def test_stale_plan_is_rejected():
    decision, context, plan = make_case()

    # Permission is revoked after the earlier proposal.
    revoked = RecoveryContext(
        permission_to_offer=False,
        hint_available=True,
        scaffold_available=True,
    )

    port = SimulatedAssistancePort()
    coordinator = RecoveryExecutionCoordinator(port)

    with pytest.raises(ValueError, match="Proposal does not match"):
        coordinator.submit(
            decision,
            context=revoked,
            plan=plan,
            approval=approve(),
        )

    assert port.calls == []


def test_operation_id_cannot_change_option():
    port = SimulatedAssistancePort()
    coordinator = RecoveryExecutionCoordinator(port)
    case = make_case()

    submit(coordinator, case)

    with pytest.raises(ValueError, match="Operation ID reused"):
        submit(
            coordinator,
            case,
            approve(option="optional_scaffold"),
        )

    assert port.calls == ["sim-001"]


def test_new_operation_cannot_repeat_same_target():
    port = SimulatedAssistancePort()
    coordinator = RecoveryExecutionCoordinator(port)
    case = make_case()

    submit(coordinator, case)

    with pytest.raises(ValueError, match="already has"):
        submit(
            coordinator,
            case,
            approve(operation_id="sim-002"),
        )

    assert port.calls == ["sim-001"]


def test_second_model_cannot_duplicate_target():
    port = SimulatedAssistancePort()
    coordinator = RecoveryExecutionCoordinator(port)

    submit(coordinator, make_case(model="neuralcd_v1"))

    with pytest.raises(ValueError, match="already has"):
        submit(
            coordinator,
            make_case(model="bkt_v1"),
            approve(operation_id="sim-002"),
        )

    assert port.calls == ["sim-001"]


def test_rejected_attempt_is_not_automatically_retried():
    port = SimulatedAssistancePort({
        "sim-001": "reject",
    })

    coordinator = RecoveryExecutionCoordinator(port)
    case = make_case()

    receipt = submit(coordinator, case)

    assert receipt.state == "simulated_failed"

    with pytest.raises(ValueError, match="already has"):
        submit(
            coordinator,
            case,
            approve(operation_id="sim-002"),
        )

    assert port.calls == ["sim-001"]


def test_unknown_attempt_is_not_automatically_retried():
    port = SimulatedAssistancePort({
        "sim-001": "unknown",
    })

    coordinator = RecoveryExecutionCoordinator(port)
    case = make_case()

    receipt = submit(coordinator, case)

    assert receipt.state == "outcome_unknown"

    assert submit(coordinator, case) == receipt

    assert port.calls == ["sim-001"]


def test_approval_rejects_nonboolean_value():
    with pytest.raises(TypeError):
        approve(approved=1)


def test_approval_rejects_unknown_option():
    with pytest.raises(ValueError):
        approve(option="automatic_tutoring")


def test_simulation_port_rejects_unknown_outcome():
    with pytest.raises(ValueError):
        SimulatedAssistancePort({
            "sim-001": "real_delivery",
        })


def test_executor_rejects_non_simulated_port():
    with pytest.raises(TypeError):
        RecoveryExecutionCoordinator(object())


def test_response_label_is_not_an_execution_argument():
    coordinator = RecoveryExecutionCoordinator(
        SimulatedAssistancePort()
    )

    decision, context, plan = make_case()

    with pytest.raises(TypeError):
        coordinator.submit(
            decision,
            context=context,
            plan=plan,
            approval=approve(),
            observed_correct=0,
        )


def test_receipt_cannot_be_mutated():
    coordinator = RecoveryExecutionCoordinator(
        SimulatedAssistancePort()
    )

    receipt = submit(coordinator, make_case())

    with pytest.raises(FrozenInstanceError):
        receipt.state = "real_delivery"
