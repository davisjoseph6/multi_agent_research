# IJCAI 2027 — Atomic Assistance Gate v1

Status: Local software-development component.

## Policy

The new repository implements a fixed-summary demo policy.

It does not use POMCP-selected actions.

The original unassisted repositories remain available.

## Atomic submission behavior

An accepted practice response and any eligible
fixed-policy assistance offer are committed inside
one SQLite transaction.

A failure in response persistence, offer creation
or offer-event recording rolls back the transaction.

## Progression gate

A new answer to the target practice question is
rejected if the associated offer is still:

- offered
- accepted

Progression is permitted once the offer is:

- declined
- delivered

Acceptance alone does not unlock the next question.

Backend delivery does not establish browser display
or actual learner uptake.

## Scope

Offers are created only when the current response
and next question both concern loss_aversion and
both questions are practice items.

Independent probe boundaries never receive offers.

Duplicate answer requests do not create duplicate offers.

## Important limitations

The gate is enforced through the new gated repository.
All application writes for gated sessions must use it.

The original Flask API is not yet connected to this mode.

The browser does not yet display offers.

The repository is not an authenticated participant system.

No POMCP-selected assistance is delivered.

No learning improvement or causal intervention effect
has been established.

The resource content remains illustrative and unvalidated.

The held-out test gate remains closed.
