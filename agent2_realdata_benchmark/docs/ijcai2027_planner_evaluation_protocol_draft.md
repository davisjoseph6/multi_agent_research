# IJCAI 2027 — Planner Evaluation Protocol

Status: Draft for research-team and supervisor review.
No human-study approval is implied.

## Research question

Under explicitly specified synthetic learner dynamics,
does a recovery-aware belief-space planning policy achieve
higher expected net instructional utility than matched
non-planning and myopic baselines?

This question is about synthetic model performance,
not established effects on real students.

## Policies to compare

1. No assistance / fixed no-offer baseline.
2. Fixed admissible assistance policy.
3. Greedy one-step expected-utility policy.
4. POMCP-style finite-horizon planning.
5. Exact finite-horizon solver as a small-problem
   optimality reference, where tractable.

## Fair-comparison requirements

All policies must share:
- The same simulated student-state dynamics.
- The same observation model.
- The same available instructional actions.
- The same intervention costs.
- The same eligibility and permission constraints.
- The same decision opportunities.
- The same evaluation episodes.
- The same primary outcome definition.

Planning computational costs must be reported separately.

## Primary synthetic outcome

Expected discounted independent-assessment correctness
minus prespecified assistance costs.

This is model-defined utility, not actual student learning.

## Secondary outcomes

- Independent assessment correctness.
- Intervention offer frequency.
- Simulated intervention uptake.
- Intervention burden and cost.
- Planning runtime and simulation budget.
- Decision agreement and value regret versus exact planning.
- Robustness to model-parameter misspecification.
- Abstention and constraint violations.

## Model-consistency issues to resolve

1. Demo BKT guess = 0.25.
2. Toy POMDP guess = 0.20.
3. Demo BKT slip = 0.10.
4. Toy POMDP slip = 0.10.
5. Toy POMDP currently assumes an observation after each action.
6. Browser demonstration has one final independent probe.
7. Browser delivers a concept summary.
8. Toy planner represents hints and scaffolds, not
   the browser's concept-summary resource.
9. Planner uptake probabilities are hypothetical.
10. Observed acceptance and backend delivery are distinct
    from actual reading or learning.

## Required experiments

A. Small POMDP sanity check against the exact solver.
B. Matched policy comparison under known synthetic dynamics.
C. Planning-budget and runtime sensitivity.
D. Intervention-cost sensitivity.
E. Learning-effect and uptake sensitivity.
F. Observation-model and transition-model misspecification.
G. Recovery-event and constraint-handling ablations.

## Reproducibility

Prespecify scenarios, seeds, action spaces, horizons,
budgets, evaluation metrics and confidence intervals.

Keep simulator randomness separate from planning randomness.

Do not select final settings using held-out evaluations.

Preserve existing frozen Phase 6 artifacts.

## Interpretation limits

The current POMCP implementation is POMCP-style
history-indexed Monte Carlo tree search without
persistent belief particles between actual observations.

Exact planning is optimal only within the specified model.

Simulated superiority does not demonstrate
real-world educational effectiveness.

Human-participant evaluation requires appropriate
institutional approval and data safeguards.

## Decisions requiring supervisor agreement

- The central technical novelty.
- The actual intervention action catalogue.
- The learner-state and observation model.
- The real instructional sequence and assessment schedule.
- The primary research outcome.
- The comparison and ablation protocol.
- Whether and how a human pilot can be authorized.

The held-out test gate remains closed.
