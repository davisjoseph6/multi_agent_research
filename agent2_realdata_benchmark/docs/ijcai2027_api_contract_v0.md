# IJCAI 2027 — Prototype API Contract v0

Status: Local development proposal; awaiting team confirmation.

## Development endpoints

- GET /api/v1/demo/health
- POST /api/v1/demo/sessions
- GET /api/v1/demo/sessions/{session_id}/question
- POST /api/v1/demo/sessions/{session_id}/responses

## Session start

Returns an opaque random session identifier.
No student name, email, or academic identifier is collected.

## Question response

Returns a question ID, concept ID, question kind,
prompt, and answer options.

Never returns the correct answer or scoring key.

## Answer submission

Request:
{
  "item_id": "demo_main_1",
  "choice_id": "B"
}

The backend checks the active question and
records the response without revealing correctness.

Duplicate or out-of-order submissions are rejected.

## Development restrictions

This demonstration uses two placeholder questions.
It does not implement BKT updates or POMCP planning.
Its fixed no-offer behavior is not an adaptive policy.
It has no persistent database or authentication.
It must not be exposed for real student recruitment.

## Future research API extensions

- Versioned item bank with real item-skill mappings.
- Verified pre-response belief-state estimation.
- Planner policy selection and action feasibility.
- Distinct assistance offer, delivery and use events.
- Independent probe and research outcome logging.
- Durable session persistence.
- Approved participant assignment and safeguards.
- Access-controlled research exports.
