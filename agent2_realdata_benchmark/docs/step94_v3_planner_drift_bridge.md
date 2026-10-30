# Step 94.5 — V3 POMCP Drift Application Audit

Status: REPRODUCED SYNTHETIC COUNTEREXAMPLE

## Model examined

Implementation:
src/prototype/study_v3_pomcp.py

Planner:
EightConceptPOMCP

The planner uses eight binary latent mastery variables,
sampled belief states, a synthetic learning model,
finite-horizon planning and Monte Carlo search.

The model has not been calibrated with real learners.

## Exact one-step drift identity

Define true deficit:

D(S) = 1 - sum(S_i)/8.

For an action a targeting concept j:

E[D(S_next)-D(S) | S,a]
    = -(p_a/8)*(1-S_j).

This follows from the implemented synthetic transition:
a mastered concept remains mastered, while an
unmastered targeted concept is acquired with
probability p_a.

Therefore, an action targeting an already-mastered
concept has zero expected deficit reduction.

## Reproduced counterexample

Planner simulations: 240
Planning horizon: 3
Random seed: 71
Remaining resource budget: 2

Belief and true state:
- Utility through Prospect Theory: mastered.
- Nudge Theory: unmastered.

The V3 planner selects:
- Action: QUESTION
- Target concept: Utility

Utility is already mastered.

Thus:
- Initial true deficit: 1/8.
- Expected one-step deficit change: 0.
- Strictly negative drift is not satisfied.

This is a counterexample to a uniform strictly
negative statewise drift assertion for this
specific implemented planner configuration.

## Interpretation

The Step 94 finite-horizon theorem is conditional
on a strictly negative drift margin.

The counterexample prevents application of that
theorem as an unconditional guarantee for V3.

It does not prove that POMCP never helps.
It does not quantify population-average performance.
It does not establish empirical learning effects.

## Further engineering work

1. Examine insufficient exploration and root
   action-value estimation.
2. Compare action choices over simulation budgets,
   seeds, beliefs and resource budgets.
3. Specify an auditable fallback when the planner
   has insufficient evidence to choose an action.
4. Benchmark any changed planner independently.
5. Preserve counterexample results rather than
   deleting unfavorable tests.
6. Revisit theorem applicability only after
   confirming the executed policy's assumptions.

No human-participant RCT is authorized by this audit.
