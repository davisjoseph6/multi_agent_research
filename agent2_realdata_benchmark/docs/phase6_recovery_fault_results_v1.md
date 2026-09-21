# Phase 6 — Recovery fault evaluation results v1

Status: completed synthetic software evaluation.

Original evaluation registration: b655964.
Durable implementation: ef568d5.

The process-level fault evaluation passed all three tests.
The combined regression suite passed 180 tests.

Crash before dispatch:
- The process exited with code 73.
- Zero simulated dispatches were recorded.
- The reservation survived restart.
- No duplicate dispatch occurred.

Crash after simulated dispatch:
- The process exited with code 74.
- One simulated dispatch was recorded.
- The reservation survived restart.
- No duplicate dispatch occurred.
- The outcome was conservatively reconciled as unknown.

Concurrent submission:
- Two processes submitted the same operation.
- Exactly one simulated dispatch was recorded.
- One operation and two journal transitions persisted.

SQLite integrity checks passed in all three scenarios.

The structured report records code, protocol and test-log
checksums, including whether the protocol was editorially
changed after registration.

These results concern local SQLite and a simulated port only.

No real assistance was delivered.
No student learning benefit was evaluated.
No validation or held-out test observations were used.

The held-out test gate remains closed.
