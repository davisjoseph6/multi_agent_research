"""Process-level synthetic fault tests for durable execution."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from src.recovery.controller import RecoveryContext, plan_recovery
from src.recovery.durable_execution import DurableRecoveryCoordinator
from src.recovery.execution import (
    SimulatedAssistancePort,
    SimulationApproval,
)
from src.uncertainty.bridge import signal_record
from src.uncertainty.event_detector import TriggerConfig, detect_event


ROOT = Path(__file__).resolve().parents[1]


# Executed in a separate interpreter, not within pytest's process.
CHILD = r'''
import os
from pathlib import Path
import sys

from src.recovery.controller import RecoveryContext, plan_recovery
from src.recovery.durable_execution import DurableRecoveryCoordinator
from src.recovery.execution import (
    SimulatedAssistancePort,
    SimulationApproval,
)
from src.uncertainty.bridge import signal_record
from src.uncertainty.event_detector import TriggerConfig, detect_event

mode = sys.argv[1]
database = Path(sys.argv[2])
marker = Path(sys.argv[3])

signal = signal_record(
    source_row=12,
    student_id="synthetic-student",
    model="neuralcd_v1",
    supported=True,
    probability=0.1,
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
    permission_to_offer=True,
    hint_available=True,
    scaffold_available=True,
)

plan = plan_recovery(decision, context=context)

approval = SimulationApproval(
    operation_id="process-test-001",
    student_id="synthetic-student",
    source_row=12,
    option="optional_hint",
    approved=True,
)

port = SimulatedAssistancePort()
original_dispatch = port.dispatch

def injected_dispatch(request):
    if mode == "crash_before":
        os._exit(73)

    response = original_dispatch(request)

    # Independent evidence that the fake dispatch method ran.
    fd = os.open(
        str(marker),
        os.O_WRONLY | os.O_CREAT | os.O_APPEND,
        0o600,
    )

    try:
        os.write(fd, b"simulated-dispatch\n")
        os.fsync(fd)
    finally:
        os.close(fd)

    if mode == "crash_after":
        os._exit(74)

    return response

port.dispatch = injected_dispatch

coordinator = DurableRecoveryCoordinator(database, port)

coordinator.submit(
    decision,
    context=context,
    plan=plan,
    approval=approval,
)
'''


def make_case():
    signal = signal_record(
        source_row=12,
        student_id="synthetic-student",
        model="neuralcd_v1",
        supported=True,
        probability=0.1,
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
        permission_to_offer=True,
        hint_available=True,
        scaffold_available=True,
    )

    plan = plan_recovery(decision, context=context)

    approval = SimulationApproval(
        operation_id="process-test-001",
        student_id="synthetic-student",
        source_row=12,
        option="optional_hint",
        approved=True,
    )

    return decision, context, plan, approval


def submit(coordinator):
    decision, context, plan, approval = make_case()

    return coordinator.submit(
        decision,
        context=context,
        plan=plan,
        approval=approval,
    )


def launch(mode, database, marker):
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            CHILD,
            mode,
            str(database),
            str(marker),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def marker_count(marker):
    if not marker.exists():
        return 0

    return len(marker.read_text(encoding="utf-8").splitlines())


def verify_sqlite(database):
    connection = sqlite3.connect(database)

    try:
        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        operations = connection.execute(
            "SELECT COUNT(*) FROM attempts"
        ).fetchone()[0]

        events = connection.execute(
            "SELECT COUNT(*) FROM execution_events"
        ).fetchone()[0]
    finally:
        connection.close()

    assert integrity == "ok"

    return operations, events


@pytest.mark.parametrize(
    ("mode", "exit_code", "expected_dispatches"),
    [
        ("crash_before", 73, 0),
        ("crash_after", 74, 1),
    ],
)
def test_subprocess_crash_does_not_retry(
    tmp_path,
    mode,
    exit_code,
    expected_dispatches,
):
    database = tmp_path / "journal.sqlite"
    marker = tmp_path / "simulator_calls.txt"

    child = launch(mode, database, marker)

    stdout, stderr = child.communicate(timeout=20)

    assert child.returncode == exit_code, (
        f"stdout={stdout}\nstderr={stderr}"
    )

    assert marker_count(marker) == expected_dispatches

    restarted_port = SimulatedAssistancePort()

    restarted = DurableRecoveryCoordinator(
        database,
        restarted_port,
    )

    pending = restarted.get_receipt("process-test-001")

    assert pending is not None
    assert pending.state == "attempt_recorded"

    assert submit(restarted) == pending
    assert restarted_port.calls == []

    assert verify_sqlite(database) == (1, 1)

    assert restarted.reconcile_incomplete(
        previous_executors_stopped=True
    ) == 1

    resolved = restarted.get_receipt("process-test-001")

    assert resolved.state == "outcome_unknown"
    assert resolved.reason == "offline_reconciliation_unconfirmed"

    assert submit(restarted) == resolved
    assert restarted_port.calls == []

    assert verify_sqlite(database) == (1, 2)

    assert restarted.history("process-test-001") == (
        ("attempt_recorded", "simulated_dispatch_pending"),
        ("outcome_unknown", "offline_reconciliation_unconfirmed"),
    )


def test_two_processes_share_one_operation(tmp_path):
    database = tmp_path / "journal.sqlite"
    marker = tmp_path / "simulator_calls.txt"

    # Initialize the schema before launching competing processes.
    DurableRecoveryCoordinator(
        database,
        SimulatedAssistancePort(),
    )

    first = launch("normal", database, marker)
    second = launch("normal", database, marker)

    output_first = first.communicate(timeout=20)
    output_second = second.communicate(timeout=20)

    assert first.returncode == 0, output_first
    assert second.returncode == 0, output_second

    assert marker_count(marker) == 1

    restarted_port = SimulatedAssistancePort()

    restarted = DurableRecoveryCoordinator(
        database,
        restarted_port,
    )

    receipt = restarted.get_receipt("process-test-001")

    assert receipt is not None
    assert receipt.state == "simulated_succeeded"

    assert submit(restarted) == receipt
    assert restarted_port.calls == []

    assert verify_sqlite(database) == (1, 2)

    assert restarted.history("process-test-001") == (
        ("attempt_recorded", "simulated_dispatch_pending"),
        ("simulated_succeeded", "simulator_acknowledged"),
    )
