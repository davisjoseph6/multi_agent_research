# T03 — Recovery Policy Versus Finite-Horizon Optimizer

Status: Policy mismatch identified; repair not selected.
Source: Rejected IJCAI-ECAI 2026 manuscript, pp. 3-4.
Related obligations: T01, T02, T03, T04, T05.

## 1. Source assumption

Assumption A2-prime postulates the existence of a
recovery policy pi_rec and a window W >= 1 satisfying
uniform negative expected drift in degraded states.

This is an existential statement.

## 2. Source algorithm

Algorithm 1 invokes finite-horizon optimization when
D(b) > tau.

Its objective combines expected future mastery distance
and a weighted fatigue cost.

The pseudocode selects the first action of an optimal
H-horizon policy.

It does not explicitly impose the A2-prime drift
condition as an optimization constraint.

The admissible recovery-policy class is insufficiently
specified in the original manuscript.

## 3. Constructed example

Consider one concept with exact belief and distance d.

Parameters:

tau = 0.6
epsilon_target = 0.5
H = 1
lambda = 1
gamma = 0.5

Available actions:

Recovery:
next distance = max(0, d - 0.4)
fatigue cost = 1

Nominal:
next distance = d
fatigue cost = 0

Both actions are assumed admissible to the optimizer.
This admissibility is an explicit example assumption,
not an established implementation detail.

For every degraded state d > 0.6, recovery decreases
distance by exactly 0.4.

Consequently, the recovery policy satisfies A2-prime
on degraded states with W = 1 and delta = 0.4.

At d = 0.8:

J_recovery = 0.4 + 1 = 1.4
J_nominal = 0.8 + 0 = 0.8

The stated optimization objective selects nominal.

The resulting distance remains 0.8.

Repeated optimization selects nominal indefinitely.

The target d <= 0.5 is never reached.

## 4. Mathematical finding

Existence of a negative-drift policy does not imply
that an unconstrained fatigue-penalized optimizer
selects that policy.

The finite-horizon objective and A2-prime are
different mathematical requirements.

The example demonstrates a missing logical
implication under the specified admissible actions.

It does not establish that every interpretation
of the original theorem is false.

## 5. Questions requiring resolution

- Is the nominal action admissible inside recovery planning?
- Does the optimizer restrict itself to certified policies?
- Is fatigue allowed to outweigh predicted mastery gain?
- Is the finite-horizon optimization solved exactly?
- Does replanning preserve a W-step drift guarantee?
- What happens when no drift-certified action exists?
- Does a finite quiz budget prevent reaching the target?

## 6. Candidate repairs

Option A:
Restrict the optimizer to policies satisfying an
appropriate, verifiable recovery condition.

Option B:
Prove a negative-drift condition directly for the
actual action-selection and switching algorithm.

Option C:
Retain a conditional theorem about the assumed
recovery policy without claiming Algorithm 1
inherits its guarantee.

These repairs are alternatives, not proven solutions.

No mathematical repair is selected by this audit.

## 7. Evidence boundaries

This example is synthetic mathematical analysis.

It does not model measured pedagogical action effects.

It does not establish student learning improvements.

The current Phase 6 controller proposes assistance
options but does not implement the original MPC
objective or certify a negative-drift policy.

No frozen model or experimental artifact is changed.

The held-out test gate remains closed.
