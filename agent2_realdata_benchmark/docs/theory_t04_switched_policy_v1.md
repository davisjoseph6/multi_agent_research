# T04 — Recovery Guarantee for the Complete Switched Policy

Status: Full-policy proof gap identified; repair not selected.
Related obligations: T01, T02, T03, T04, T05.

## 1. Mathematical distinction

The manuscript assumes that a recovery policy exists
with a negative expected drift property.

Algorithm 1 executes a switched policy consisting of
recovery planning above tau and nominal operation
at or below tau.

The assumed policy and executed policy must not
be identified without proof.

## 2. Candidate recovery target

For this audit only:

B_target = {b : D(b) <= epsilon_target}.

Assume:

0 < epsilon_target < tau < 1.

This remains a candidate formalization rather than
an established definition from the original manuscript.

## 3. Constructed example

Consider one concept with exact belief.

Parameters:

epsilon_target = 0.1
tau = 0.6
initial distance = 0.9

Recovery transition:

D_next = max(0, D_current - 0.4).

Nominal transition:

D_next = D_current.

Recovery is selected when D > tau.

For every degraded state D > 0.6, the recovery
transition decreases distance by exactly 0.4.

Thus the recovery policy has one-step negative drift
with W = 1 and delta = 0.4 on degraded states.

The switched trajectory is:

0.9 -> 0.5 -> 0.5 -> 0.5 -> ...

At D = 0.5, recovery planning is deactivated.

However:

epsilon_target < 0.5 <= tau.

The nominal transition has zero drift there.

Consequently the candidate target is never reached,
and its first hitting time is infinite.

This example establishes a full-policy implication
gap under its stated transitions and candidate target.

It is not a counterexample satisfying every original
assumption, nor an independent educational experiment.

## 4. Required theorem conditions

A corrected theorem must specify the actual
implemented policy and its relevant drift conditions.

Possible routes include:

A. Align the recovery target with tau.

B. Continue a verified recovery policy until
   the smaller target is reached.

C. Establish appropriate progress or reachability
   conditions for the complete switched policy,
   including nominal behavior outside the target.

Any repair must also address the optimizer mismatch
in T03 and the drift assumptions in T02.

No repair is selected by this audit.

## 5. Remaining questions

- What is the stopping time?
- What is the recovery target?
- Which policy is executed in each region?
- Are drift conditions valid for that policy?
- Can recovery planning terminate prematurely?
- What happens when the quiz budget expires?
- What can be proved when the required policy
  is unavailable?

The T05 recovery-time bound remains unproved.

No frozen experiment or model is modified.

The held-out test gate remains closed.
