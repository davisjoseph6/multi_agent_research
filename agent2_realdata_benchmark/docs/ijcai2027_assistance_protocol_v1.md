# IJCAI 2027 — Assistance Event Protocol v1

Status: Local software-development infrastructure only.

## Purpose

Establish explicit, durable assistance state transitions
without interpreting an offer as evidence of learning.

## Implemented

- Versioned illustrative concept-summary resource.
- Fixed manual demonstration policy.
- Eligibility limited to a real upcoming practice item.
- Separate proposed and offered events.
- Explicit acceptance or decline.
- Separate acceptance and server-side delivery operations.
- Resource body withheld until explicit delivery.
- Transactional and idempotent final decisions.
- Persistence across SQLite repository instances.
- Protection against late delivery after quiz progress.

## Scientific interpretation

Proposed is not offered.

Offered is not accepted.

Accepted is not evidence of reading or actual uptake.

Delivered is not evidence of mastery improvement.

Backend delivery means the resource was made available.
It does not prove browser rendering, reading or uptake.

No learner outcome or causal intervention effect is
estimated by this component.

The fixed demonstration resource is not a POMCP action
selected using empirically calibrated transitions.

## Current limitations

The new ledger is not yet connected to Flask or the browser.

The existing quiz API does not gate the next question
on resolution of an outstanding assistance offer.

The resource content is illustrative and unvalidated.

No actual student recruitment or study is authorized.

The system has no production authentication or
participant-consent framework.

The held-out test gate remains closed.
