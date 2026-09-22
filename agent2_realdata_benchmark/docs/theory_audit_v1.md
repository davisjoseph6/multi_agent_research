# IJCAI — Formal Theory Audit v1

Status: Initial proof-obligation inventory
Source: Rejected IJCAI-ECAI 2026 manuscript
Submission: 3789

## Purpose

Determine which theoretical statements are established,
which require additional assumptions, and which require
a complete proof or a more limited claim.

This audit does not modify the original manuscript.

No theorem is marked proved merely because a related
software component passes tests.

## Original mathematical objects

Section 3 defines:

- Latent learner knowledge k_t in [0,1]^n.
- Belief state b_t over knowledge states.
- Pedagogical action a_t.
- Observation o_t.
- Belief update T.
- Distance-to-mastery function D(b_t).

Section 4 introduces:

- Degradation threshold tau.
- Self-healing definition.
- Assumptions A1, A2-prime, A3, A4, A5.
- Single-step sufficient condition A2.
- Theorem 1.
- Corollary 1.
- Proposition 1.

Section 5 introduces:

- Algorithm 1: switching between nominal and recovery planning.
- Algorithm 2: greedy adaptive quiz.
- Proposition 2: cost dominance of switching.

## Proof-obligation register

| ID | Source | Claim or obligation | Initial finding | Status |
|---|---|---|---|---|
| T01 | Section 4.1, p. 2; Section 4.4, p. 3 | Define the recovery target and distinguish it from the switching threshold. | The relationship between the target set and threshold tau requires clarification. | OPEN |
| T02 | Section 4.3, p. 3; Section 4.4, p. 4 | Establish that A2 implies positive negative-drift constant delta. | The stated conditions p > 0.5 and eta < epsilon do not imply p*epsilon > eta. | OPEN |
| T03 | Theorem 1, p. 3; Algorithm 1, p. 4 | Prove that Algorithm 1 satisfies the recovery-policy assumption. | A2-prime postulates existence of a recovery policy; equivalence to the finite-horizon optimizer has not been established. | OPEN |
| T04 | Theorem 1, p. 3; Algorithm 1, p. 4 | Show recovery remains possible after switching back to the nominal policy. | The nominal policy's behavior between the target and trigger threshold needs an explicit condition or proof. | OPEN |
| T05 | Corollary 1, p. 3; proof, pp. 3-4 | Derive a finite-time high-probability recovery bound. | Bounded deviations, window length, stopping-time definition, constants and concentration steps require verification. | OPEN |
| T06 | Proposition 1, p. 3 | Establish the precise scope of the nonrecoverability claim. | Failure of a sufficient drift condition must be distinguished from impossibility for every available policy. | OPEN |
| T07 | Proposition 2, p. 4 | Prove equivalent recovery and strictly lower expected computational cost. | The required conditions on threshold behavior, planning costs and recovery equivalence need verification. | OPEN |

## Initial mathematical concern: T02

The manuscript states:

delta = (p*epsilon - eta)/n.

Positive delta requires:

p*epsilon > eta.

The stated conditions p > 0.5 and eta < epsilon
do not imply this inequality.

Illustrative parameter values:

p = 0.6
epsilon = 0.05
eta = 0.04

These satisfy the stated probability and degradation
inequalities, but p*epsilon - eta = -0.01.

This identifies a gap in the claimed sufficient-condition
argument. It does not disprove the separately assumed
negative drift in A2-prime.

The interpretation of eta and the full transition model
must be specified before deriving a corrected bound.

## Scientific boundaries

Existing Phase 6 software tests do not prove Theorem 1.

Observational ASSISTments follow-ups do not establish
that a recovery action satisfies A2-prime.

No original mathematical claim is considered verified
until its assumptions and complete proof are audited.

No frozen experimental result is modified here.

The held-out test gate remains closed.

## Next task

Begin the detailed mathematical audit of T01 and T02:
definitions, domains, quantifiers, probability conditions,
transition assumptions and the proposed drift inequality.
