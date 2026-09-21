# Phase 6 — Durable simulated recovery execution v1

Status: simulation-only software prototype.

This is a separate SQLite-backed coordinator. The existing
in-memory coordinator remains unchanged.

The coordinator independently recomputes the recovery plan.
Only a flagged, permitted proposal with one explicitly approved
available option can reach the simulator.

The operation ID uniquely identifies one request.
A student-and-source-row target can be claimed only once,
including across different prediction models and policies.

Operation IDs cannot be reused with different parameters.

The coordinator commits an attempt_recorded state before
calling the in-process simulator.

The reservation and final state are stored in SQLite.
Each state transition is also entered in an append-only
application-level event table within its database transaction.

A duplicate operation never invokes the simulator again.

Simulator results:
- simulated_succeeded: simulator acknowledgement;
- simulated_failed: explicit simulator rejection;
- outcome_unknown: acknowledgement unavailable.

A crash between reservation and finalization leaves
attempt_recorded in the database.

On restart, an incomplete operation is not dispatched again.
Its outcome must not be inferred from the absence of a receipt.

An explicit offline reconciliation can conservatively change
attempt_recorded to outcome_unknown. The caller must first
ensure all earlier execution processes have stopped.

The coordinator cannot independently verify that all other
processes are stopped. Reconciliation is an operator-controlled
simulation procedure, not an automated production guarantee.

SQLite uniqueness constraints serialize reservations across
coordinator instances sharing the same local database.

Durability is conditional on the filesystem and SQLite's
commit guarantees. This prototype has no distributed consensus,
authenticated approvals or production recovery mechanism.

Only SimulatedAssistancePort is accepted.
No student-facing or external delivery interface exists.

A simulated acknowledgement is not real delivery.
No student recovery or learning improvement is measured.

No current or future response labels are accepted.
Frozen models and event policies remain unchanged.
The held-out test gate remains closed.
