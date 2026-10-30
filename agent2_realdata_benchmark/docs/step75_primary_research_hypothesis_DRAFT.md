# Step 75 — Primary Research Hypothesis

Status: DRAFT — NOT FROZEN OR SUPERVISOR APPROVED

## Main objective

Develop and rigorously evaluate a novel,
budget-constrained, belief-aware recovery policy
for adaptive learning under uncertainty.

The objective is an original, technically sound
AI contribution suitable for IJCAI 2027.

## Candidate algorithms

A: POMCP-based adaptive recovery, currently V5.
B: Greedy adaptive learning without recovery.
C: Fixed nonadaptive instructional sequence.

V3 POMCP and rule-based recovery are additional
algorithmic comparators and ablations.

This experimental identity is provisional.

## Primary computational research question

Under identical learner models, item access,
instructional budgets and random conditions,
does the proposed recovery policy improve
learning outcomes or recovery efficiency over
strong alternative decision policies?

## Candidate primary human-study hypothesis

If an authorized human RCT is conducted,
Group A produces a higher independent post-test
score than Group B, accounting for pre-test score.

The outcome definition, estimand, sample size,
missing-data rules and analysis require approval
before recruitment.

## Mandatory evidence before policy selection

1. Verify algorithmic novelty against prior work.
2. Explain why the proposed algorithm differs
   substantially from existing POMCP adaptations.
3. Test actual intervention activation frequency.
4. Compare equal-budget learning outcomes.
5. Include model misspecification and noisy beliefs.
6. Report computational runtime and uncertainty.
7. Include greedy, fixed, unguarded POMCP and
   rule-based recovery comparisons.
8. Preserve negative and unfavorable results.
9. Audit mathematical claims independently.
10. Obtain research-supervisor approval.

## Current evidence

V3 has a reproduced zero-drift counterexample.

V5 corrected 29 of 33 original zero-gain
selections across 52 paired synthetic cases.

V5 activated zero times in 58 ordinary synthetic
planner decisions.

These observations do not demonstrate
improved educational effectiveness.

## Decision

Final policy: UNDECIDED
Primary endpoint: PROVISIONAL
Novelty assessment: REQUIRED
Supervisor approval: NOT RECEIVED

Do not preregister or initiate an RCT using
this draft as an approved protocol.
