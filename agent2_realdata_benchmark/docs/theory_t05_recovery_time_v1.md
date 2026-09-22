# T05 — Recovery-Time Bound and Stopping-Time Audit

Status: Conditional bound identified; original corollary unproved.
Related obligations: T01, T02, T03, T04, T05.

## 1. Research question

Determine which recovery-time guarantee follows
from a drift condition for the actually executed policy.

The original corollary and the June 22 team's proposed
replacement must be audited separately.

## 2. Definitions

Let X_t = D(b_t) be a nonnegative adapted process.

Let rho be a proposed recovery target.

Define:

T_rho = inf{t >= 0 : X_t <= rho}.

T_rho is measured from the initial state or the
explicitly defined beginning of a recovery episode.

## 3. Counterexample to a bound without overshoot

Proposed expression:

E[T_rho] <= (X_0 - rho) / delta.

Set:

X_0 = 0.6
rho = 0.5
delta = 0.5

For every state x > rho, define the next state as zero.

The conditional drift is -x < -0.5.

From X_0 = 0.6, the first hitting time is exactly 1.

However:

(X_0 - rho) / delta = 0.2.

Therefore the proposed inequality fails.

The process overshoots the target boundary.

## 4. Conditional one-step drift result

Assume:

- X_t is nonnegative and adapted.
- X_0 = x_0 > rho is fixed.
- Relevant conditional expectations exist.
- T_rho is the first hitting time of X_t <= rho.
- For every t < T_rho, the actual executed policy
  satisfies the conditional drift inequality:

  E[X_(t+1) - X_t | F_t] <= -delta.

- delta > 0 is uniform before recovery.

Then:

E[T_rho] <= x_0 / delta.

This is a conditional mathematical statement.
Its assumptions have not been established for
Algorithm 1 or measured educational interventions.

## 5. Proof of the conditional result

Define the stopped process:

Y_t = X_(t min T_rho).

The drift assumption and the tower property imply:

E[Y_(t+1)] <= E[Y_t] - delta * P(T_rho > t).

Sum from t = 0 to N-1:

E[Y_N] + delta * E[min(T_rho, N)] <= x_0.

Because Y_N >= 0:

E[min(T_rho, N)] <= x_0 / delta.

Monotone convergence as N tends to infinity yields:

E[T_rho] <= x_0 / delta.

In particular, the hitting time is finite
almost surely under these assumptions.

## 6. Window-length qualification

The manuscript's recovery assumption uses W-step
drift, not necessarily one-step drift.

A window-based result requires a specified
checkpoint process and conditional drift at every
pre-target checkpoint under the executed policy.

For a valid checkpoint hitting-time bound of
x_0 / delta windows, the corresponding elapsed-time
bound may include the factor W.

That statement does not follow merely from drift
for an existing policy on states D > tau.

Intermediate states, switching and window boundaries
require separate treatment.

No W-step theorem is marked proved here.

## 7. High-probability qualification

An expectation bound alone supports a Markov bound:

P(T_rho > m) <= x_0 / (delta * m)

for positive m under the one-step assumptions.

A stronger concentration bound requires its own
argument and any additional necessary assumptions.

The original Corollary 1 has not yet been verified.

## 8. Relationship to previous audits

T01: Recovery target and switching threshold may differ.

T02: Positivity of the proposed drift constant is
not established under the source assumptions alone.

T03: An effective policy's existence does not imply
selection by the optimizer.

T04: The full switched policy can cease progressing
before reaching a smaller target.

All these issues must be resolved before applying
a recovery-time theorem to Algorithm 1.

## 9. Evidence boundaries

The counterexample and proof are mathematical analyses.

No real-world action-effect model has been validated.

No student recovery or learning improvement is established.

No theorem repair is selected.

No frozen experiment or model is modified.

The held-out test gate remains closed.
