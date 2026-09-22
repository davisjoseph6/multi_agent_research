# T01 — Recovery Target and Switching Threshold

Status: Mathematical issue identified; repair not yet selected.
Source: Rejected IJCAI-ECAI 2026 manuscript.
Related proof obligations: T01, T03, T04, T05.

## 1. Source-defined objects

The manuscript defines:

D(b) = expected normalized L1 distance to full mastery.

Degradation occurs when:

D(b) > tau.

Algorithm 1 selects the recovery planner when D(b) > tau
and selects the nominal policy otherwise.

The proof refers to a target set B_epsilon, but its
relationship to tau is insufficiently specified.

## 2. Proposed formal definitions

Candidate recovery target:

B_epsilon = {b : D(b) <= epsilon_target}.

Candidate recovery hitting time:

T_epsilon = inf{t >= t_d : D(b_t) <= epsilon_target}.

The set and hitting time above are audit proposals,
not definitions silently attributed to the manuscript.

We must distinguish epsilon_target, the mastery tolerance,
from epsilon_gain, the per-concept improvement parameter
in the single-step sufficient condition A2.

The relationship between epsilon_target and tau must be
stated explicitly in any revised theorem.

## 3. Switching gap

Assume:

0 < epsilon_target < tau < 1.

Algorithm 1 switches to the nominal policy when D(b) <= tau.

It is possible that:

epsilon_target < D(b) <= tau.

In this region the recovery target has not been reached,
but Algorithm 1 does not select the recovery planner.

The manuscript does not establish that the nominal policy
will necessarily drive this intermediate region into
B_epsilon.

## 4. Constructed counterexample

Consider one concept, exact belief about its mastery,
and deterministic action transitions.

Parameters:

epsilon_target = 0.1
tau = 0.6
initial distance = 0.9

Recovery action:

D_next = max(0, D_current - 0.2).

Nominal action:

D_next = D_current.

While D > tau, the recovery action has drift -0.2.

Consequently, the recovery policy satisfies the
one-step negative-drift requirement on all degraded
states, with W = 1 and delta = 0.2.

Algorithm 1 generates:

t = 0: D = 0.9, recovery selected.
t = 1: D = 0.7, recovery selected.
t = 2: D = 0.5, nominal selected.
t >= 2: D = 0.5 indefinitely.

The proposed recovery target D <= 0.1 is never reached.

This example isolates a switching-policy gap.
It does not establish that all interpretations of
the original theorem are false.

## 5. Candidate mathematical repairs

Option A: Define recovery as return to D <= tau.

This aligns the target with the existing trigger,
but changes the interpretation of the target and
requires a fresh recovery-time proof.

Option B: Keep the smaller target epsilon_target.

Then the controller must remain in recovery mode
until the smaller target is reached, or the nominal
policy must satisfy an additional sufficient condition
in the intermediate region.

Option C: Establish a common drift or reachability
condition for the complete switched policy.

A2-prime, as stated for an existing recovery policy,
is not automatically a drift condition for Algorithm 1.

No repair is selected by this audit.

## 6. Additional proof questions

- Is the recovery target based on belief distance
  or independently measured student performance?
- Is the trigger threshold larger than the target?
- Is recovery deactivated immediately or with hysteresis?
- What happens when the quiz terminates before recovery?
- Does the optimizer implement the assumed policy?
- Can the switching rule cause repeated recovery episodes?
- What is the precise stopping time in Corollary 1?

## 7. Evidence boundaries

This is a mathematical counterexample constructed
for proof analysis, not an ASSISTments experiment.

It does not demonstrate or disprove instructional
effectiveness on real learners.

No model, experimental artifact, threshold or policy
has been changed.

The held-out test gate remains closed.
