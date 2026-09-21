# Phase 6 — Recovery controller contract v1

Status: software prototype specification.

The controller consumes a frozen event-detector decision and
explicit pre-decision context.

Context contains:
- explicit permission to offer optional assistance;
- whether a hint resource is currently available;
- whether a scaffolding resource is currently available.

The controller does not receive response labels or future outcomes.

A no_flag decision produces no action.

An abstain decision remains an abstention and cannot be
silently converted to no_flag or an automatic intervention.

A flag without explicit permission produces no assistance proposal.

A permitted flag proposes exactly the available help options.
If no resource is available, the controller defers.

A proposal is not delivery. No hint or scaffolding content
is generated, displayed, or recorded as administered.

The controller does not:
- fit or modify BKT or NeuralCD;
- modify the frozen event-detection policies;
- select thresholds;
- infer true student mastery;
- estimate intervention benefit;
- access validation or test labels.

The initial evaluation consists of synthetic software tests.
All real-world educational-effectiveness claims remain out of scope.

The held-out test gate remains closed.
