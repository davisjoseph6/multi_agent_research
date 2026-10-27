# IJCAI 2027 — Durable Flask Quiz API v1

Status: Local software-development demonstration only.

## Architecture

The durable Flask API uses SQLite as the authoritative
record of accepted responses and session position.

It does not share the original in-memory demo endpoints.

## API endpoints

POST /api/v1/durable/sessions

GET /api/v1/durable/sessions/{session_id}/question

POST /api/v1/durable/sessions/{session_id}/responses

Every submission requires a unique request_id.

A retry of the same logical submission must reuse
the same request_id and the same answer data.

## BKT reconstruction

The BKT model is reconstructed from persisted
practice responses rather than an independently
mutable stored mastery value.

For shadow planning, only prior practice responses
associated with the target concept are replayed.

This does not yet implement a calibrated multi-concept
learner model or cross-concept knowledge transfer.

The demonstration parameters are illustrative and
not calibrated to the proposed participants.

Independent probes are not treated as practice
learning transitions.

## Shadow planning

A newly accepted practice response is eligible
for shadow planning only when the next scheduled
item is another practice question for the same concept.

BKT reconstruction for a shadow decision uses only
the response history available through that event's
position, preventing later answers from entering
the earlier decision.

The planner's simulated permission does not constitute
real-world authorization to deliver assistance.

No hypothetical POMDP transition changes actual BKT.

No assistance is delivered to the user.

The planner's two-step simulated horizon may extend
beyond the number of available practice questions.
It is still a diagnostic rather than an executable
instructional schedule.

Shadow diagnostics are transient in-memory records.
They are not currently persisted in SQLite.

## Reliability boundaries

SQLite commits responses before optional planning.

Replayed submissions do not trigger duplicate planning.

Planning failures do not roll back accepted responses.

This implementation has no session authentication.

The opaque session identifier functions as a bearer
capability in the current local development workflow.

There is no production authorization, retention,
encryption, audit or data-governance framework.

No real participant data may be collected.

## Research limitations

The item bank is not educationally validated.

The observed mastery estimate is model-derived.

No causal learning effect has been established.

The full multi-session research protocol has
not been implemented.

The held-out test gate remains closed.
