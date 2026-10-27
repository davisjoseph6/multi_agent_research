# IJCAI 2027 — Fixed Quiz Session Engine v1

Status: Local software-development component.

## Implemented behavior

- Accept a versioned immutable question sequence.
- Validate the supplied item bank.
- Support multiple practice questions.
- Support distinct independent probes.
- Require practice before independent probes.
- Return questions without answer keys.
- Accept one answer per sequential item.
- Reject duplicate or out-of-order submissions.
- Record correctness privately.
- Maintain independent in-memory session instances.

## Explicit limitations

This component is not yet connected to Flask.

No BKT updates or POMCP actions are performed here.

No assistance is offered or delivered.

The item bank is not a validated educational instrument.

The sequence does not implement the full pre-test,
three-session and post-test research protocol.

There is no durable storage or atomic transaction model.

Concurrent requests are not supported.

No human-study use is authorized.

## Next integration requirements

- Connect the engine to a versioned application endpoint.
- Preserve the existing demonstration API.
- Coordinate one accepted practice response with one BKT update.
- Introduce durable SQLite transactions.
- Record assessment outcomes separately from practice updates.
- Support policy-specific intervention decision points.
- Validate the complete experimental schedule.

The held-out test gate remains closed.
