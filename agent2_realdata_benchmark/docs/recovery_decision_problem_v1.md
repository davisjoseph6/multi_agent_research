# Recovery Decision Problem — Version 1

Status: Draft research specification.
Supervisor approval: Not established.
Implementation status: Not implemented.

## 1. Scientific objective

Design a recovery decision policy that selects an
appropriate pedagogical intervention for a learner
showing evidence of difficulty.

The objective is to improve independently measured
learning outcomes while accounting for intervention
costs and operational constraints.

This objective has not yet been experimentally achieved.

## 2. Existing Phase 6 implementation

The existing controller proposes available assistance
options after receiving a trigger decision.

Its available options include:

- optional_hint
- optional_scaffold

It checks permission and resource availability.

It does not estimate intervention effects.

It does not optimize a fatigue-weighted objective.

Its execution infrastructure is simulation-only.

The 45 passing execution tests establish software
behavior, not educational effectiveness.

## 3. Proposed decision inputs

A future decision policy may require:

- Learner-state estimate and prediction history.
- Degradation or risk signal.
- Available intervention options.
- Permission and operational constraints.
- Remaining quiz time or interaction budget.
- Estimated effects and uncertainty for each action.

The existing implementation does not provide all
these inputs or estimates.

## 4. Proposed action space

Initial candidate decisions:

A = {
    abstain,
    optional_hint,
    optional_scaffold
}.

Abstention means declining to select an intervention
when the evidence or required conditions are absent.

This is a proposed action space, not an assertion
that these actions have validated learning effects.

Additional instructional actions require a separate
specification and supervisor agreement.

## 5. Recovery outcome

A recovery outcome must be measured independently
of the model signal that triggered intervention.

Candidate primary outcome:

Performance on a prespecified independent recovery
probe within a defined follow-up window.

The outcome definition, probe difficulty, timing
and scoring procedure must be registered before
evaluating intervention effectiveness.

Prediction improvement alone is not evidence of
an educational recovery benefit.

## 6. Intervention-effect evidence

The available observational ASSISTments follow-ups
do not identify causal intervention effects by
themselves.

Students receiving or requesting help may differ
from students who do not receive help.

A causal action-effect model requires an appropriate
research design and defensible identification
assumptions.

No causal intervention-effect model is validated yet.

## 7. Proposed decision objective

A future policy may balance:

- Expected independently measured recovery.
- Intervention burden or fatigue.
- Computational and operational cost.
- Uncertainty and available evidence.

A precise objective function has not been selected.

No numerical intervention utility is currently
established.

## 8. Finite-session constraints

The policy must explicitly address:

- Permission and resource availability.
- Remaining interaction budget.
- Unavailable or unsupported interventions.
- Abstention when evidence is inadequate.
- Quiz termination before recovery.

An eventual-recovery theorem does not automatically
guarantee recovery within a finite quiz.

## 9. Mathematical guarantee

The conditional T05 theorem requires negative
expected drift for the policy actually executed.

The current Phase 6 controller does not establish
this premise.

A new algorithm must not inherit the original
manuscript's recovery guarantee without proof.

## 10. Evidence boundaries

No human recovery benefit is established.

No causal action-effect estimate is established.

No recovery optimization algorithm is implemented.

No frozen research artifact is modified.

The held-out test gate remains closed.

## Next research task

Specify one independently measurable recovery
outcome and a feasible intervention-effect
estimation strategy before implementing selection.
