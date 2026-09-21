# Phase 6 — Simulated recovery execution contract v1

Status: simulation-only software prototype.

The execution coordinator receives:
- a frozen event-detector decision;
- explicit pre-decision recovery context;
- the corresponding recovery proposal;
- a separate, explicit simulation approval for one option.

The coordinator independently recomputes the proposal and
rejects mismatches.

Only a proposed and explicitly approved option may be
submitted. The executor never automatically chooses
between a hint and scaffolding.

No flag, abstention, denied permission, unavailable resources,
and unapproved requests cannot reach the execution port.

The only permitted execution port is an in-process simulator.
It cannot deliver content to students or external services.

An attempt is recorded before the simulated port is called.

Possible terminal states:
- simulated_succeeded: simulator acknowledged the request;
- simulated_failed: simulator explicitly rejected the request;
- outcome_unknown: acknowledgement cannot be established.

Terminal states are not automatically retried.

Repeated submission of the same operation and parameters
returns the existing immutable record without another port call.

Reusing an operation ID with different parameters is rejected.
A different operation ID for an already claimed
student-and-source-row target is also rejected, including
when the prediction model or detection policy differs.

Idempotency is in memory, within one coordinator process only.
It does not survive a crash, restart or distributed execution.

Simulation approval is caller-supplied test context.
It is not authenticated real-world consent.

A simulator acknowledgement is not verified delivery,
student recovery or improvement in learning.

No current or future response outcomes are execution inputs.
No model, threshold or frozen policy is modified.
No validation or test observations are accessed.

The held-out test gate remains closed.
