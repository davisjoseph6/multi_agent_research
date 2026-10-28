# IJCAI 2027 — Fixed-Summary HTTP Integration v1

Status: Local-only demonstration infrastructure.

## Modes

Default `create_durable_app`: unassisted; existing behavior preserved.

With `fixed_summary=True`: uses the atomic gated SQLite repository.

## Assistance endpoints

- `GET /api/v1/durable/sessions/<id>/assistance`
- `POST /api/v1/durable/sessions/<id>/assistance/decision`
- `POST /api/v1/durable/sessions/<id>/assistance/delivery`

The unassisted mode does not register these endpoints.

## Contract

Practice-answer acceptance and offer creation are committed together in SQLite.
The question endpoint withholds the next question while an offer is unresolved.
The SQLite repository rejects attempts to submit the next response directly.
Decline permits progress without displaying the resource.
Accept only records acceptance: the resource body remains hidden until explicit delivery.
Delivery is idempotent and requires acceptance.
Session and offer state survive restart. The repository-mode stamp prevents ordinary cross-mode opening.

## Research limitations

The resource is selected by a fixed demonstration policy, **not** POMCP.
POMCP remains a hypothetical shadow diagnostic.
The fixed-summary browser page is not enabled in this step.
Backend delivery does not establish browser rendering, reading, comprehension, or improved learning.
Educational content and assessment items remain illustrative and unvalidated.
No real participant data may be collected. The held-out test gate remains closed.
