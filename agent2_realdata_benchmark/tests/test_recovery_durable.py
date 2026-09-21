"""Synthetic tests for SQLite-backed recovery execution."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from src.recovery.controller import RecoveryContext, plan_recovery
from src.recovery.durable_execution import DurableRecoveryCoordinator
from src.recovery.execution import (
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
    model="neuralcd_v1",
    probability=0.1,
    supported=True,
    permission=True,
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
            policy="risk_only",
            risk_threshold=0.7,
            entropy_threshold=0.8,
        ),
    )

    context = RecoveryContext(
        permission_to_offer=permission,
        hint_available=True,
        scaffold_available=True,
    )

    plan = plan_recovery(decision, context=context)

    return decision, context, plan


def approval(operation_id="sim-001", option="optional_hint"):
    return SimulationApproval(
        operation_id=operation_id,
        student_id="synthetic-student",
        source_row=12,
        option=option,
        approved=True,
    )


def submit(coordinator, case=None, approved=None):
    if case is None:
        case = make_case()

    if approved is None:
        approved = approval()

    decision, context, plan = case

    return coordinator.submit(
        decision,
        context=context,
        plan=plan,
        approval=approved,
    )


@pytest.mark.parametrize(
    ("outcome", "state"),
    [
        ("ack", "simulated_succeeded"),
        ("reject", "simulated_failed"),
        ("unknown", "outcome_unknown"),
        ("raise", "outcome_unknown"),
    ],
)
def test_terminal_result_survives_restart(
    tmp_path,
    outcome,
    state,
):
    path = tmp_path / "journal.sqlite"

    first_port = SimulatedAssistancePort({
        "sim-001": outcome,
    })

    first = DurableRecoveryCoordinator(path, first_port)
    receipt = submit(first)

    assert receipt.state == state
    assert first_port.calls == ["sim-001"]

    second_port = SimulatedAssistancePort()
    second = DurableRecoveryCoordinator(path, second_port)

    assert second.get_receipt("sim-001") == receipt
    assert submit(second) == receipt
    assert second_port.calls == []

    assert second.history("sim-001") == (
        ("attempt_recorded", "simulated_dispatch_pending"),
        (state, receipt.reason),
    )


def test_crash_before_dispatch_never_retries(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "journal.sqlite"

    first_port = SimulatedAssistancePort()

    def crash_before_dispatch(_approval):
        raise KeyboardInterrupt("synthetic process interruption")

    monkeypatch.setattr(
        first_port,
        "dispatch",
        crash_before_dispatch,
    )

    first = DurableRecoveryCoordinator(path, first_port)

    with pytest.raises(KeyboardInterrupt):
        submit(first)

    assert first_port.calls == []

    # A new coordinator represents the restarted process.
    second_port = SimulatedAssistancePort()
    second = DurableRecoveryCoordinator(path, second_port)

    pending = second.get_receipt("sim-001")

    assert pending.state == "attempt_recorded"
    assert submit(second) == pending
    assert second_port.calls == []

    with pytest.raises(ValueError, match="already has"):
        submit(
            second,
            approved=approval("sim-002"),
        )

    with pytest.raises(ValueError, match="Stop previous"):
        second.reconcile_incomplete(
            previous_executors_stopped=False
        )

    assert second.reconcile_incomplete(
        previous_executors_stopped=True
    ) == 1

    recovered = second.get_receipt("sim-001")

    assert recovered.state == "outcome_unknown"
    assert recovered.reason == "offline_reconciliation_unconfirmed"

    assert submit(second) == recovered
    assert second_port.calls == []

    assert second.history("sim-001") == (
        ("attempt_recorded", "simulated_dispatch_pending"),
        ("outcome_unknown", "offline_reconciliation_unconfirmed"),
    )

    assert second.reconcile_incomplete(
        previous_executors_stopped=True
    ) == 0


def test_crash_after_fake_dispatch_never_retries(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "journal.sqlite"

    first_port = SimulatedAssistancePort()
    original_dispatch = first_port.dispatch

    def dispatch_then_crash(request):
        original_dispatch(request)
        raise KeyboardInterrupt("crash after fake acknowledgement")

    monkeypatch.setattr(
        first_port,
        "dispatch",
        dispatch_then_crash,
    )

    first = DurableRecoveryCoordinator(path, first_port)

    with pytest.raises(KeyboardInterrupt):
        submit(first)

    assert first_port.calls == ["sim-001"]

    second_port = SimulatedAssistancePort()
    second = DurableRecoveryCoordinator(path, second_port)

    assert second.get_receipt("sim-001").state == (
        "attempt_recorded"
    )

    assert submit(second).state == "attempt_recorded"
    assert second_port.calls == []

    second.reconcile_incomplete(
        previous_executors_stopped=True
    )

    assert second.get_receipt("sim-001").state == (
        "outcome_unknown"
    )

    # The original fake acknowledged the request, but the
    # recovered coordinator cannot establish that result.
    assert second_port.calls == []


def test_operation_id_reuse_with_changed_option_rejected(tmp_path):
    coordinator = DurableRecoveryCoordinator(
        tmp_path / "journal.sqlite",
        SimulatedAssistancePort(),
    )

    submit(coordinator)

    with pytest.raises(ValueError, match="Operation ID reused"):
        submit(
            coordinator,
            approved=approval(
                "sim-001",
                "optional_scaffold",
            ),
        )


def test_different_operation_cannot_repeat_target(tmp_path):
    coordinator = DurableRecoveryCoordinator(
        tmp_path / "journal.sqlite",
        SimulatedAssistancePort(),
    )

    submit(coordinator)

    with pytest.raises(ValueError, match="already has"):
        submit(
            coordinator,
            approved=approval("sim-002"),
        )


def test_different_model_cannot_repeat_target(tmp_path):
    path = tmp_path / "journal.sqlite"

    first = DurableRecoveryCoordinator(
        path,
        SimulatedAssistancePort(),
    )

    submit(first)

    second_port = SimulatedAssistancePort()

    second = DurableRecoveryCoordinator(
        path,
        second_port,
    )

    with pytest.raises(ValueError, match="already has"):
        submit(
            second,
            case=make_case(model="bkt_v1"),
            approved=approval("sim-002"),
        )

    assert second_port.calls == []


@pytest.mark.parametrize(
    "case",
    [
        {"probability": 0.9},
        {"supported": False},
        {"permission": False},
    ],
)
def test_nonproposal_never_reserves_or_dispatches(
    tmp_path,
    case,
):
    port = SimulatedAssistancePort()

    coordinator = DurableRecoveryCoordinator(
        tmp_path / "journal.sqlite",
        port,
    )

    with pytest.raises(ValueError, match="Only proposed"):
        submit(
            coordinator,
            case=make_case(**case),
        )

    assert coordinator.get_receipt("sim-001") is None
    assert port.calls == []


def test_two_coordinators_share_atomic_reservation(tmp_path):
    path = tmp_path / "journal.sqlite"

    port_a = SimulatedAssistancePort()
    port_b = SimulatedAssistancePort()

    a = DurableRecoveryCoordinator(path, port_a)
    b = DurableRecoveryCoordinator(path, port_b)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(submit, a)
        second = pool.submit(submit, b)

        receipts = [
            first.result(),
            second.result(),
        ]

    assert sum(map(len, (port_a.calls, port_b.calls))) == 1

    assert all(
        receipt.state in {
            "attempt_recorded",
            "simulated_succeeded",
        }
        for receipt in receipts
    )

    assert a.get_receipt("sim-001").state == (
        "simulated_succeeded"
    )

    assert a.history("sim-001") == (
        ("attempt_recorded", "simulated_dispatch_pending"),
        ("simulated_succeeded", "simulator_acknowledged"),
    )


def test_explicit_approval_required(tmp_path):
    coordinator = DurableRecoveryCoordinator(
        tmp_path / "journal.sqlite",
        SimulatedAssistancePort(),
    )

    denied = SimulationApproval(
        operation_id="sim-001",
        student_id="synthetic-student",
        source_row=12,
        option="optional_hint",
        approved=False,
    )

    with pytest.raises(ValueError, match="approval"):
        submit(coordinator, approved=denied)

    assert coordinator.get_receipt("sim-001") is None


def test_label_is_not_an_execution_input(tmp_path):
    coordinator = DurableRecoveryCoordinator(
        tmp_path / "journal.sqlite",
        SimulatedAssistancePort(),
    )

    decision, context, plan = make_case()

    with pytest.raises(TypeError):
        coordinator.submit(
            decision,
            context=context,
            plan=plan,
            approval=approval(),
            observed_correct=0,
        )

    assert coordinator.get_receipt("sim-001") is None


def test_only_simulator_is_accepted(tmp_path):
    with pytest.raises(TypeError):
        DurableRecoveryCoordinator(
            tmp_path / "journal.sqlite",
            object(),
        )


def test_reconciliation_requires_explicit_boolean(tmp_path):
    coordinator = DurableRecoveryCoordinator(
        tmp_path / "journal.sqlite",
        SimulatedAssistancePort(),
    )

    with pytest.raises(TypeError):
        coordinator.reconcile_incomplete(
            previous_executors_stopped=1
        )
