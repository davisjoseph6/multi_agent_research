# Step 69 — Experimental Design Decisions

Project: IJCAI 2027 Self-Healing Learning Intervention

Status: SUPERVISOR DECISIONS PENDING

Date: 2026-10-29

## 1. Research objective

Determine whether an adaptive instructional assistance
policy produces a measurable improvement in actual
student learning compared with a prespecified baseline.

The study must distinguish predictive accuracy,
assistance delivery, and causal learning effects.

## 2. Intervention to be evaluated

Option A:
Existing BKT mastery-threshold assistance policy.

Option B:
Original POMCP-based self-healing controller,
after implementation and independent verification.

Option C:
Separate experiments evaluating both approaches.

Supervisor decision: PENDING.

## 3. Candidate experimental conditions

Currently implemented:

- Control: no optional summary offers.
- Fixed summary: offer at each eligible practice boundary.
- Adaptive threshold: offer based on BKT mastery estimate.

These conditions must be finalized before
randomized participant enrollment.

## 4. Primary scientific comparison

Candidate primary comparison:

Adaptive assistance versus fixed-summary assistance.

Rationale:
Tests whether conditional assistance targeting
provides an advantage over a nonadaptive policy.

Important limitation:
Different policies may produce different
assistance exposure. The study must distinguish
policy-level effects from the effect of adaptation
at comparable assistance doses.

Alternative primary comparison:
Adaptive assistance versus no-assistance control.

Supervisor decision: PENDING.

## 5. Primary learning outcome

The present independent probe is insufficiently
validated as a primary research outcome.

Proposed direction:

Develop an independent multi-item assessment of
conceptual understanding and transfer, with
documented validity and scoring reliability.

Consider:
- Baseline assessment.
- Immediate post-intervention assessment.
- Delayed retention assessment.
- Parallel or appropriately equated test forms.
- Independent assessment items not presented
  during training or assistance.

Final instrument: PENDING.

## 6. Primary estimand and analysis

Candidate estimand:
The intention-to-treat effect of assignment
to the selected adaptive policy versus the
prespecified comparator on post-intervention
learning performance.

Candidate analysis:
Baseline-adjusted comparison of the randomized
groups, accounting for the actual randomization
unit and any prespecified clustering.

The exact statistical model, primary time point,
missing-outcome strategy and uncertainty
quantification must be prespecified.

Supervisor decision: PENDING.

## 7. Sample size

Not determined.

Required inputs:
- Primary outcome scale.
- Minimum educationally meaningful effect.
- Outcome variance or justified pilot estimate.
- Significance level.
- Desired statistical power.
- Randomization unit and clustering.
- Anticipated missing outcomes.
- Number of primary comparisons.

Do not invent a sample-size target.

## 8. Randomization and governance

Before real recruitment:
- Confirm the responsible institution.
- Obtain applicable research approvals.
- Finalize consent and privacy procedures.
- Finalize inclusion and exclusion criteria.
- Finalize allocation and analysis protocols.
- Confirm secure participant enrollment.
- Prespecify outcomes and analyses.

## 9. Publication claims

Engineering tests alone do not establish
learning improvement.

Synthetic scripted learners cannot provide
causal evidence about real student learning.

A successful trial of BKT-based assistance
does not automatically validate the POMCP
self-healing controller.

## 10. Supervisor decisions required

1. Final intervention/controller.
2. Primary comparator.
3. Primary outcome and measurement time point.
4. Target population and recruitment feasibility.
5. Responsible institution and approvals.
6. Statistical analysis and sample-size planning.

No real participants are authorized by
this document.

## 11. Historical supervisor specification — 2026-10-29 review

The supervisor's earlier 12-page technical document
has been recovered and examined.

It specifies:

- Group A: self-healing adaptive quiz.
- Group B: greedy adaptive quiz without recovery.
- Group C: fixed-sequence quiz without adaptation.
- Eight Behavioral Economics concepts.
- Learner-specific knowledge-state tracking.
- A degradation-triggered four-action recovery sequence.
- Three sessions per learner.
- Sixteen-item pre-test and post-test.
- A proposed target of 75 completing learners.
- Fatigue surveys and interaction logging.

The currently implemented control, fixed-summary,
and BKT-threshold conditions do not reproduce
these three experimental groups.

The historical proposal is therefore the provisional
engineering reference, not an approved RCT protocol.

Important unresolved matters:

- Rule-based recovery versus POMCP planning.
- Correct Bayesian knowledge-tracing equations.
- Concealed randomization instead of predictable rotation.
- Validated educational outcomes.
- Sample-size justification.
- Institutional ethics and data-protection authorization.
- Supervisor confirmation of the final protocol.

No human-participant enrollment is authorized
by this historical specification.
