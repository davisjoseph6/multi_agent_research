# IJCAI 2027 — Browser Demonstration v1

Status: Local-only software-development interface.

## Purpose

Provide a browser-based walkthrough of the existing
durable quiz API without introducing React dependencies.

## Features

- Start a local demonstration session.
- Display answer-key-free multiple-choice questions.
- Submit answers using unique request identifiers.
- Preserve pending submissions for safe retry.
- Resume a session using tab-scoped sessionStorage.
- Recover quiz progress after backend restart.
- Display completion without correctness feedback.

## Architecture

The browser uses the existing versioned durable API.

SQLite remains authoritative for accepted responses.

BKT reconstruction and POMCP shadow planning remain
internal backend operations.

No assistance is offered or delivered.

The interface does not implement an experimental arm,
an actual pretest, or a validated instructional session.

## Limitations

The existing question bank is illustrative.

No real participant data may be collected.

The application has no participant authentication.

The local session identifier is retained in sessionStorage.

No production privacy or retention framework is provided.

JavaScript behavior requires manual browser verification.

The interface is not the final React frontend.

The held-out test gate remains closed.
