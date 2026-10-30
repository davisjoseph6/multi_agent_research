# Step 95 — V5 opt-in belief-support guard

Status: ENGINEERING DEVELOPMENT / SYNTHETIC ONLY

## Finding

The immutable V3 planner's deterministic 240-simulation, seed-71 witness
selects an action targeting mastered Utility when Nudge Theory is unmastered.
That produces zero expected true-deficit decrease under the supplied synthetic
transition model. The original V3 planner and its counterexample tests are
preserved unchanged.

## Proposed V5 policy

The V5 opt-in planner runs the original POMCP search and records its result.
If the selected action has exactly zero *belief-expected* acquisition, and
another legal action has positive acquisition, it applies a deterministic
maximum-immediate-acquisition fallback. The trace records original and final
actions and an explicit `guard_applied` flag.

This is a **new hybrid POMCP + one-step fallback policy**, not a repair of the
underlying UCT search. It changes the intervention and requires separate
comparison and prospective protocol specification.

## Mathematical scope

For concept belief b_j and synthetic acquisition rate r_a, the model's
one-step expected decrease in the latent deficit is `(1-b_j) * r_a / 8`.
This is calculated under the model's assumptions. Even a positive quantity
is **not** evidence that the fully observed true state will improve: the
belief may be incorrect. Resource costs, long-term value, and human learning
validity are not established by this guard.

There is no strictly positive uniform drift guarantee across all beliefs,
states, configurations, and candidate sets. In particular, zero acquisition
rates and already-mastered concepts invalidate such a guarantee.

## Deployment boundary

Do not silently substitute V5 for V3 in an ongoing SQLite study. This module
is currently a candidate decision rule only. Integration must create a new
version-locked protocol identity and fresh synthetic database, and needs full
three-arm regression tests plus a pre-specified scientific comparison.

Never use this as evidence for real human RCT effectiveness or an approved
human-participant system.
