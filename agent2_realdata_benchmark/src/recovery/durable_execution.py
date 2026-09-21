"""Durable, simulation-only execution with conservative crash recovery."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
from threading import RLock
import sqlite3

from src.recovery.controller import (
    RecoveryContext,
    RecoveryPlan,
    plan_recovery,
)
from src.recovery.execution import (
    ExecutionReceipt,
    SimulatedAssistancePort,
    SimulatedRejection,
    SimulatedUnknown,
    SimulationApproval,
)
from src.uncertainty.event_detector import TriggerDecision


class DurableRecoveryCoordinator:
    """Persistent idempotency for a simulation-only assistance port."""

    def __init__(self, db_path, port: SimulatedAssistancePort):
        if type(port) is not SimulatedAssistancePort:
            raise TypeError("Only the in-process simulator is permitted")

        path = Path(db_path).expanduser()

        if path.is_symlink():
            raise ValueError("Database path must not be a symlink")

        self._path = path.resolve()

        if not self._path.parent.is_dir():
            raise FileNotFoundError(
                f"Database directory does not exist: {self._path.parent}"
            )

        self._port = port
        self._lock = RLock()

        with self._transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attempts (
                    operation_id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    source_row INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN (
                            'attempt_recorded',
                            'simulated_succeeded',
                            'simulated_failed',
                            'outcome_unknown'
                        )
                    ),
                    UNIQUE(student_id, source_row)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    FOREIGN KEY(operation_id)
                        REFERENCES attempts(operation_id)
                )
            """)

        # Limit ordinary local-file visibility for this prototype.
        os.chmod(self._path, 0o600)

    def _connect(self):
        conn = sqlite3.connect(
            str(self._path),
            timeout=15,
        )
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    @contextmanager
    def _transaction(self):
        conn = self._connect()

        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _decode(payload):
        return ExecutionReceipt(**json.loads(payload))

    @staticmethod
    def _encode(receipt):
        return json.dumps(
            asdict(receipt),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def submit(
        self,
        decision: TriggerDecision,
        *,
        context: RecoveryContext,
        plan: RecoveryPlan,
        approval: SimulationApproval,
    ) -> ExecutionReceipt:
        """Reserve durably, dispatch once, then record the outcome."""

        if type(plan) is not RecoveryPlan:
            raise TypeError("Expected RecoveryPlan")

        if type(approval) is not SimulationApproval:
            raise TypeError("Expected SimulationApproval")

        expected = plan_recovery(
            decision,
            context=context,
        )

        if plan != expected:
            raise ValueError(
                "Proposal does not match current decision and context"
            )

        if plan.disposition != "proposed":
            raise ValueError("Only proposed assistance can be submitted")

        if approval.approved is not True:
            raise ValueError("Explicit simulation approval required")

        if (
            approval.student_id != plan.student_id
            or approval.source_row != plan.source_row
        ):
            raise ValueError("Approval target does not match proposal")

        if approval.option not in plan.proposed_options:
            raise ValueError("Approved option is unavailable")

        fingerprint = json.dumps(
            {
                "decision": asdict(decision),
                "context": asdict(context),
                "plan": asdict(plan),
                "approval": asdict(approval),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

        operation_id = approval.operation_id

        with self._lock:
            # Transaction 1: claim and record the target BEFORE dispatch.
            with self._transaction() as conn:
                existing = conn.execute(
                    """
                    SELECT fingerprint, receipt_json
                    FROM attempts
                    WHERE operation_id = ?
                    """,
                    (operation_id,),
                ).fetchone()

                if existing is not None:
                    previous_fingerprint, receipt_json = existing

                    if previous_fingerprint != fingerprint:
                        raise ValueError(
                            "Operation ID reused with different parameters"
                        )

                    return self._decode(receipt_json)

                claimed = conn.execute(
                    """
                    SELECT operation_id
                    FROM attempts
                    WHERE student_id = ? AND source_row = ?
                    """,
                    (plan.student_id, plan.source_row),
                ).fetchone()

                if claimed is not None:
                    raise ValueError(
                        "Target already has a recorded execution attempt"
                    )

                initial = ExecutionReceipt(
                    operation_id=operation_id,
                    student_id=plan.student_id,
                    source_row=plan.source_row,
                    model=plan.model,
                    policy=plan.policy,
                    option=approval.option,
                    state="attempt_recorded",
                    reason="simulated_dispatch_pending",
                    attempts=1,
                )

                conn.execute(
                    """
                    INSERT INTO attempts (
                        operation_id, student_id, source_row,
                        fingerprint, receipt_json, state
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        operation_id,
                        plan.student_id,
                        plan.source_row,
                        fingerprint,
                        self._encode(initial),
                        initial.state,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO execution_events (
                        operation_id, state, reason
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        operation_id,
                        initial.state,
                        initial.reason,
                    ),
                )

            # The reservation transaction has now committed.
            # A process crash from here onward must NOT cause a retry.
            try:
                acknowledgement = self._port.dispatch(approval)

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
                state = "outcome_unknown"
                reason = "unexpected_simulator_exception"

            # BaseException, such as simulated KeyboardInterrupt,
            # deliberately propagates. The durable reservation remains.
            final = replace(
                initial,
                state=state,
                reason=reason,
            )

            # Transaction 2: finalize and journal the simulated result.
            with self._transaction() as conn:
                current = conn.execute(
                    """
                    SELECT receipt_json, state
                    FROM attempts
                    WHERE operation_id = ?
                    """,
                    (operation_id,),
                ).fetchone()

                if current is None:
                    raise RuntimeError("Reserved operation disappeared")

                receipt_json, current_state = current

                if current_state != "attempt_recorded":
                    # Another coordinator may have reconciled it.
                    # Never overwrite a recorded result.
                    return self._decode(receipt_json)

                conn.execute(
                    """
                    UPDATE attempts
                    SET receipt_json = ?, state = ?
                    WHERE operation_id = ?
                      AND state = 'attempt_recorded'
                    """,
                    (
                        self._encode(final),
                        final.state,
                        operation_id,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO execution_events (
                        operation_id, state, reason
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        operation_id,
                        final.state,
                        final.reason,
                    ),
                )

            return final

    def get_receipt(self, operation_id: str):
        """Inspect persisted state without dispatching anything."""

        if type(operation_id) is not str or not operation_id.strip():
            raise ValueError("Invalid operation ID")

        conn = self._connect()

        try:
            row = conn.execute(
                """
                SELECT receipt_json FROM attempts
                WHERE operation_id = ?
                """,
                (operation_id,),
            ).fetchone()
        finally:
            conn.close()

        return None if row is None else self._decode(row[0])

    def history(self, operation_id: str):
        """Return the persisted transition history in insertion order."""

        if type(operation_id) is not str or not operation_id.strip():
            raise ValueError("Invalid operation ID")

        conn = self._connect()

        try:
            rows = conn.execute(
                """
                SELECT state, reason
                FROM execution_events
                WHERE operation_id = ?
                ORDER BY event_id
                """,
                (operation_id,),
            ).fetchall()
        finally:
            conn.close()

        return tuple(rows)

    def reconcile_incomplete(
        self,
        *,
        previous_executors_stopped: bool,
    ) -> int:
        """Conservatively resolve orphaned attempts while offline.

        The caller must externally ensure prior executors stopped.
        This boolean is not proof of process quiescence.
        """

        if type(previous_executors_stopped) is not bool:
            raise TypeError("Quiescence declaration must be boolean")

        if not previous_executors_stopped:
            raise ValueError("Stop previous executors before reconciliation")

        with self._lock:
            with self._transaction() as conn:
                pending = conn.execute(
                    """
                    SELECT operation_id, receipt_json
                    FROM attempts
                    WHERE state = 'attempt_recorded'
                    ORDER BY operation_id
                    """
                ).fetchall()

                for operation_id, receipt_json in pending:
                    final = replace(
                        self._decode(receipt_json),
                        state="outcome_unknown",
                        reason="offline_reconciliation_unconfirmed",
                    )

                    conn.execute(
                        """
                        UPDATE attempts
                        SET receipt_json = ?, state = ?
                        WHERE operation_id = ?
                          AND state = 'attempt_recorded'
                        """,
                        (
                            self._encode(final),
                            final.state,
                            operation_id,
                        ),
                    )

                    conn.execute(
                        """
                        INSERT INTO execution_events (
                            operation_id, state, reason
                        ) VALUES (?, ?, ?)
                        """,
                        (
                            operation_id,
                            final.state,
                            final.reason,
                        ),
                    )

                return len(pending)
