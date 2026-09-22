# Intervention-Effect Evidence — Version 1

Status: Draft research specification.
Supervisor approval: Not established.
Human study approval: Not established.
Implementation status: Not implemented.

## 1. Research objective

Establish what evidence is required to estimate
whether optional pedagogical interventions improve
independently measured subsequent performance.

No intervention effect has been established.

## 2. Historical action-code interpretation

The repository interprets first_action as:

- 0: answer attempt.
- 1: hint request.
- 2: scaffold request.

These describe observed student interaction behavior.

Code 0 is not a randomized no-intervention group.

Code 1 is not assignment to optional_hint.

Code 2 is not assignment to optional_scaffold.

The historical codes do not independently establish
intervention delivery or receipt.

## 3. Existing observational evidence

The training-only recovery audits describe
subsequent student interactions.

The shared-skill follow-up requires:

- A different subsequent ASSISTment.
- At least one shared annotated skill.

Its conditional correctness rate uses only
subsequent answer attempts as the denominator.

A subsequent help request must not be silently
classified as an incorrect answer attempt.

Conditioning on subsequent attempts can create
selection bias.

Voluntary help-seeking is confounded.

These audits do not identify causal effects.

## 4. Proposed study arms

Candidate policies, subject to approval:

- Standard instruction without an additional offer.
- Standard instruction plus an optional hint offer.
- Standard instruction plus an optional scaffold offer.

The comparison must preserve ordinary educational
support and participant protections.

An offer is distinct from actual delivery and use.

No study arm is approved or implemented.

## 5. Proposed primary estimand

For eligible difficulty events, compare the
probability of independent probe success under
assignment to each approved policy.

The primary interpretation should distinguish
assignment from intervention receipt.

An intention-to-treat comparison concerns the
effect of assigned policy, not necessarily the
effect of receiving or using an intervention.

The comparison population and time horizon must
be prespecified.

## 6. Proposed identification strategy

A suitably designed randomized comparison may
identify assigned-policy effects.

Randomization unit, allocation procedure,
eligibility, contamination, repeated events
and interference require explicit treatment.

Observational group differences cannot substitute
for random assignment without a separately
justified identification strategy.

No identification assumptions are verified yet.

## 7. Outcome measurement

Use the independent recovery outcome protocol.

Primary candidate:

First-attempt correctness on a distinct,
unhinted, target-concept probe.

Match assessment schedules and control probe
difficulty across comparison groups.

A single successful probe does not establish
durable mastery.

## 8. Required study records

Record, subject to privacy and ethics approval:

- Eligibility and target concept.
- Pre-assignment information.
- Assigned policy and assignment probability.
- Intervention availability and permission.
- Offer, delivery and actual use separately.
- Probe assignment and first-attempt result.
- Probe nonresponse and dropout reasons.
- Learner identifier for repeated-event analysis.

Do not infer delivery from a help-request code.

## 9. Analysis requirements

Prespecify the primary analysis and comparison.

Account for repeated observations per learner.

Report group sizes, missing outcomes,
uncertainty and protocol deviations.

Specify missing-data handling before analysis.

Sample size and statistical power are not
established in this document.

No effect sizes are currently established.

## 10. Approval and implementation gates

Before collecting new human intervention data:

- Obtain supervisor agreement on the question.
- Establish institutional ethics requirements.
- Approve eligibility and comparison policies.
- Fix the outcome and analysis protocol.
- Validate intervention delivery logging.

Do not implement human randomization or delivery
based solely on this draft.

## 11. Current evidence boundaries

The existing controller remains proposal-based.

Execution remains simulation-only.

No causal intervention-effect model is validated.

No frozen research artifact is modified.

The held-out test gate remains closed.
