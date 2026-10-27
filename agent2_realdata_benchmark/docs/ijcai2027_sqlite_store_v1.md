# IJCAI 2027 — Durable Quiz Storage v1

Status: Local development infrastructure only.

## Implemented

- File-backed SQLite session storage.
- Item-bank version and content digest checks.
- Atomic accepted response and position update.
- Request-identifier-based idempotent retry.
- Original submission completion status preserved on replay.
- Rejection of conflicting submissions.
- SQLite writer serialization.
- Restart recovery.
- Private response history.
- Reconstruction of BKT from saved practice outcomes.

## Transaction model

A submission begins with BEGIN IMMEDIATE.

The repository checks current position and request identity.

Response insertion and position advancement occur
inside the same SQLite transaction.

Any database failure rolls back both changes.

## Scientific boundaries

No real student data may be collected by this prototype.

The repository is not authenticated or access-controlled.

There is no encryption or approved retention policy.

The current session engine is still separate from Flask.

BKT replay is demonstrated in tests, but is not yet
integrated with the durable API workflow.

POMCP shadow diagnostics are not durably stored.

The item bank remains illustrative and unvalidated.

The human-study protocol is not implemented.

## Next requirements

- Integrate SQLite with a new versioned Flask endpoint.
- Add server-side session authentication or authorization.
- Reconstruct BKT from committed practice responses.
- Run shadow planning without writing simulated
  transitions into actual learner-state history.
- Define research-event schemas and timestamps.
- Review privacy, access control and ethics requirements.
- Test simultaneous HTTP submissions and server restarts.

The held-out test gate remains closed.
