# T05 — Original Corollary 1: High-Probability Audit

Status: Original concentration argument unverified.
Source: Rejected IJCAI-ECAI 2026 manuscript, pp. 3–4.

## 1. Original source claim

Corollary 1 states that, under A1, A2-prime,
and A3–A5, there exists a recovery-time threshold
T_max with:

P(T <= T_max) >= 1 - alpha.

It additionally proposes:

T_max = O(
    (D_initial - epsilon) / delta
    + ln(1/alpha) / delta^2
).

The second expression is attributed to a
Hoeffding-type argument under bounded deviations.

The manuscript does not display a complete
concentration derivation.

## 2. Proof obligations

C01: Define the first hitting time and recovery target.

C02: Establish drift for the executed policy.

C03: Explain the conversion from W-step drift
to elapsed quiz steps.

C04: State the bounded-increment or deviation
assumptions required by the concentration argument.

C05: Derive the claimed confidence dependence.

C06: Handle target overshoot and stopping correctly.

C07: State all constants and any dependence on W.

No obligation is marked discharged.

## 3. Conditional result already established

Under the one-step assumptions in
theory_t05_recovery_time_v1.md:

E[T_rho] <= x_0 / delta.

Markov's inequality gives:

P(T_rho > m) <= x_0 / (delta * m).

For alpha in (0,1), choose:

m = ceil(x_0 / (delta * alpha)).

Then:

P(T_rho <= m) >= 1 - alpha.

This is conditional on the actual executed policy
satisfying the T05 one-step drift assumptions.

It does not establish the original logarithmic
high-probability bound.

## 4. Window qualification

A2-prime is formulated over W-step windows.

The relevant checkpoint process, stopping rule,
policy execution and elapsed-time conversion
must be defined before deriving a W-step bound.

Recovery may occur between checkpoint times.

An unrestricted trajectory may also leave
the recovery target before a later checkpoint.

The checkpoint and stopping conventions therefore
cannot be left implicit.

## 5. Current conclusion

The original Corollary 1 remains unproved.

A conditional one-step expectation bound and
Markov high-probability bound have been identified.

No corrected W-step or concentration theorem
is adopted by this document.

No frozen experimental artifact is modified.

The held-out test gate remains closed.
