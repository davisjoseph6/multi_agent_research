# T02 — Single-Step Progress and Aggregate Negative Drift

Status: Mathematical issue identified; repair not selected.
Source: Rejected IJCAI-ECAI 2026 manuscript, pp. 3–4.
Related obligations: T02, T03, T05, T06.

## 1. Source claims

A2 postulates, for each unmastered concept i, an action
with probability at least p > 0.5 of increasing mastery
on that concept by at least epsilon_gain.

A4 states that worst-case degradation is bounded by eta,
where eta < epsilon_gain.

The manuscript states:

delta = (p * epsilon_gain - eta) / n > 0.

The source does not adequately specify the joint behavior
of concept improvement and degradation needed to derive
the aggregate distance bound.

## 2. Positive-drift condition for the stated formula

For the displayed delta to be positive, one must have:

p * epsilon_gain > eta.

The separate inequalities:

p > 0.5
eta < epsilon_gain

do not imply this condition.

Example:

p = 0.6
epsilon_gain = 0.05
eta = 0.04

Then:

p * epsilon_gain = 0.03 < 0.04 = eta.

Hence the manuscript's displayed delta is negative.

This shows that the given assumptions do not establish
positivity of the displayed formula. It does not show
that every system satisfying them has nonnegative drift.

## 3. Interpretation A: degradation on every step

Additional accounting assumptions:

- The selected concept gains at least epsilon_gain
  on an event of probability at least p.
- The gain is nonnegative outside the success event.
- Aggregate mastery loss elsewhere is at most eta
  on each step.
- These gains and losses correctly account for the
  change in aggregate distance.

Under these additional assumptions:

E[Delta D | b, a] <=
    -(p * epsilon_gain - eta) / n.

To obtain strict negative drift from this bound,
one must additionally require:

p * epsilon_gain > eta.

The manuscript's A2 and A4 alone do not specify all
the accounting assumptions above.

## 4. Interpretation B: degradation only on failure

Alternative additional assumptions:

- Success and failure are mutually exclusive outcomes.
- Success increases total mastery by at least epsilon_gain.
- Failure decreases total mastery by at most eta.
- Success occurs with probability at least p.

Then:

E[Delta D | b, a] <=
    -(p * epsilon_gain - (1-p) * eta) / n.

If p > 0.5 and eta < epsilon_gain, this bound
is strictly negative.

This is not automatically the manuscript's model.
The alternative requires explicit assumptions about
the full-system transition.

## 5. Local numerical example: positive drift in distance

Consider two concepts, both initially at mastery 0.5.

Select an action targeting the first concept.

With probability 0.6:
- concept 1 improves by 0.05;
- concept 2 degrades by 0.04.

With probability 0.4:
- concept 1 remains unchanged;
- concept 2 degrades by 0.04.

The expected total mastery change is:

0.6 * (0.05 - 0.04)
+ 0.4 * (-0.04)
= -0.01.

Therefore the expected normalized distance change is:

E[Delta D] = +0.005.

A symmetric targeting action can be provided for
the second concept.

This is a local illustration of missing aggregate
progress assumptions, not a globally specified
transition model satisfying every manuscript
assumption at every state.

## 6. Additional boundary question

Since mastery lies in [0,1], a concept with mastery
greater than 1-epsilon_gain cannot increase by
epsilon_gain.

The phrase "every unmastered concept" therefore
requires a precise definition or a gain condition
that accounts for the boundary.

This issue has not yet been resolved.

## 7. Required next work

- Define the transition model and probability space.
- State whether eta bounds concept-level or total loss.
- State whether degradation is unconditional or
  restricted to failure outcomes.
- Specify how gains and losses affect other concepts.
- Relate latent-state changes to belief-space distance.
- Establish the required condition uniformly over
  the relevant states and selected actions.
- Distinguish the existence of a suitable action
  from its actual selection by Algorithm 1.

No corrected theorem is selected in this audit.

No empirical or frozen research artifact is changed.

The held-out test gate remains closed.
