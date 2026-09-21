# Phase 6 — Durable recovery fault evaluation v1

Status: prespecified synthetic software evaluation.

Subject:
SQLite-backed DurableRecoveryCoordinator v1.

No real students, learning records, intervention delivery,
validation observations or held-out test outcomes are used.

Scenario A: terminate a subprocess immediately before
the simulator's dispatch method records a call.

Expected:
- subprocess exit code 73;
- durable attempt_recorded receipt survives;
- zero simulated dispatches;
- a new coordinator does not dispatch again;
- offline reconciliation produces outcome_unknown.

Scenario B: record a simulated dispatch, persist an
independent test marker, then terminate the subprocess
before the coordinator finalizes its SQLite receipt.

Expected:
- subprocess exit code 74;
- exactly one recorded simulated dispatch;
- durable attempt_recorded receipt survives;
- a new coordinator does not dispatch again;
- offline reconciliation produces outcome_unknown.

Scenario C: two subprocesses submit the same operation
against the same local SQLite database concurrently.

Expected:
- both subprocesses exit successfully;
- exactly one simulated dispatch in total;
- one durable operation record;
- final receipt simulated_succeeded;
- one reservation and one finalization journal event.

The independent marker is synthetic test instrumentation,
not proof of external delivery.

All scenarios require a successful SQLite integrity check.

No real intervention is performed.
No recovery or learning benefit is estimated.
No existing models, event policies or frozen reports are changed.

The held-out test gate remains closed.
