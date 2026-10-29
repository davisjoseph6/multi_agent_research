# Step 93 — Mathematical Claim Audit

Status: PROVISIONAL; INDEPENDENT REVIEW REQUIRED

Source:
Original rejected IJCAI 2026 manuscript,
Section 4, theoretical guarantees.

## Finding 1 — Incorrect positivity implication

The manuscript invokes:

delta = (p * epsilon - eta) / n

The stated conditions p > 0.5 and eta < epsilon
do not establish delta > 0.

Example:
p = 3/5, epsilon = 1, eta = 4/5, n = 1.

Then delta = -1/5.

The displayed margin needs eta < p * epsilon
to be positive. Its derivation from the actual
transition model must also be verified.

## Finding 2 — Probability threshold

A success probability at or below one-half
does not alone imply impossibility of recovery.

If success removes a deficit and failure leaves
the deficit unchanged, repeated attempts with
p = 2/5 have finite expected hitting time 5/2.

The original proposition requires qualification
and a precisely stated model class.

## Finding 3 — Finite recovery cap

For independent attempts with success probability
3/5 and a maximum of two attempts:

P(no recovery) = (2/5)^2 = 4/25.

Negative expected drift during an active recovery
policy does not imply certain recovery when the
actual controller terminates after two attempts.

## Finding 4 — Degradation definition

Eight initial mastery beliefs of 0.2 give
D = 0.8 under the mean-mastery deficit metric.

A threshold of 0.5 is exceeded before any
observed deterioration.

Absolute deficit and deterioration over time
must be clearly distinguished.

## Candidate narrower result

For a nonnegative adapted deficit process,
suppose the actual executed policy satisfies a
uniform negative stopped drift of at least delta
before entering the target set.

Under suitable integrability assumptions,
a standard additive-drift argument bounds
expected hitting time in terms of initial
deficit divided by delta.

This result does not automatically cover
finite recovery caps, arbitrary disturbances,
incorrect beliefs, or approximate POMCP choices.

## Publication status

The original general recovery guarantee,
high-probability bound and cost-dominance
proposition remain unverified.

Passing counterexample tests checks exact
arithmetic. It does not prove a new theorem,
validate real learning, or replace expert review.

No human-participant study is authorized.
