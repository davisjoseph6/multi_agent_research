# T05 — Conditional Recovery Concentration Theorem

Status: Candidate mathematical theorem.
Theorem application to Algorithm 1: NOT ESTABLISHED.

## 1. One-step assumptions

Let X_t be adapted, with 0 <= X_t <= 1.

Fix 0 <= rho < x_0 <= 1 and delta > 0.

T = inf{t >= 0 : X_t <= rho}.

Assume that for every t < T:

E[X_(t+1) - X_t | F_t] <= -delta.

This condition must hold for the executed policy.

## 2. Concentration result

For every positive integer m satisfying:

delta*m > x_0 - rho,

P(T > m) <= exp(
  -2*(delta*m - (x_0-rho))^2/m
).

A sufficient integer choice for confidence 1-alpha is:

m = ceil(max(
  2*(x_0-rho)/delta,
  2*ln(1/alpha)/delta^2
)).

Here alpha is in (0,1).

Then P(T <= m) >= 1-alpha.

## 3. Proof

Set Y_t = X_(min(t,T)).

Y_t is adapted and lies in [0,1].

Define martingale differences:

xi_(t+1) = Y_(t+1) - E[Y_(t+1)|F_t].

Their conditional ranges have length at most 1.

Before T, the drift inequality implies:

Y_(t+1) - Y_t <= -delta + xi_(t+1).

On the event T > m, summation gives:

Y_m <= x_0 - delta*m + sum(i=1..m) xi_i.

Since T > m also implies Y_m > rho:

sum(i=1..m) xi_i > delta*m - (x_0-rho).

Apply the bounded-difference martingale
Hoeffding inequality to obtain the stated tail.

For the sufficient m, the tail is at most:

exp(-delta^2*m/2) <= alpha.

This proves the conditional one-step result.

## 4. W-step checkpoint result

Let W be a positive integer.

Define Z_j = X_(j*W) and:

S = inf{j >= 0 : Z_j <= rho}.

Assume for every j < S:

E[Z_(j+1)-Z_j | F_(j*W)] <= -delta.

Assume the executed policy and checkpoint
process remain defined for this horizon.

The one-step proof applies to Z_j.

The ordinary first hitting time satisfies:

T <= W*S.

Consequently:

P(T <= W*m) >= 1-alpha

for the same sufficient choice of m.

This is conditional on checkpoint drift
for the actual executed policy.

## 5. Limits

The original A2-prime existence assumption
does not establish drift for Algorithm 1.

Drift only above tau does not establish drift
outside a smaller target rho.

The checkpoint result does not prove recovery
under early quiz termination.

This theorem does not prove the original
corollary under its original assumptions.

No intervention-effect guarantee is established.

No frozen experimental artifact is changed.

The held-out test gate remains closed.
