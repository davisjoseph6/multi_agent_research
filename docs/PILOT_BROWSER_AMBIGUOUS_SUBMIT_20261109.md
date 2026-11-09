# Local fictional preview — ambiguous response and exactly-once retry hardening

**2026-11-09. DRAFT. SYNTHETIC ONLY. NO HUMAN ENROLLMENT.**

## Identified failure mode

An HTTP request to `POST /preview/api/act` can commit successfully in SQLite while the browser never receives the success response because of a dropped connection. The earlier fictional preview generated a **new** `request_id` on every submission attempt. If the learner retried after an ambiguous reply, the server could reject the new request as stale/completed. The underlying store already protects exactly-once replays keyed by `(pid,request_id)`, but the browser was not using that guarantee reliably across retries.

## Implemented isolated UI change

The fictional JavaScript now creates a frozen `submissionAttempt` **once for each selected action** with a randomly generated `request_id`, `action_id`, selected arm and response. On ambiguous failure:

- The action remains on screen with a clearly labelled **retry same fictional response** control.
- Previously selected inputs are locked from editing to ensure retries use the same payload and therefore receive the same stored replay result; changing the response under an existing request ID is intentionally rejected by the server.
- Clicking retry resends **the exact original request ID and response**. A successful replay explicitly displays that a previously saved response was confirmed.
- The existing Refresh action reconciles against authoritative server state. If the original response was committed, the UI loads the next action. If not, it presents the still-pending action for a fresh explicit choice.
- The browser cannot recruit humans, approve visits, change arms for real randomization, or contact the external VPS.

Regression tests verify the script generates one ID per action attempt and that a duplicate HTTP submission with exactly the same action+request+payload is accepted once and replayed once, with the pretest score counted once. **The source-level JavaScript test is not a substitute for a real browser+accessibility/network-fault test.**

## Required manual browser QA

From the **isolated local fictional preview**, use Chromium/Firefox on WSL loopback only. In a developer-test session, intercept a single action request, allow the server to process it but simulate a dropped browser response; verify retry keeps the action ID and request ID unchanged, the form cannot be altered between retries, and no extra pretest/practice record is created. Repeat with a request dropped *before* reaching the server, and Refresh after ambiguous acknowledgement. Repeat for the M-VAS field and optional recovery status. Then perform keyboard, screen reader, zoom and mobile checks with independent accessibility review before any real-student use.

Do **not** run a packet-dropping test against the active IONOS fictional operator demonstration or any participant data. Human RCT privacy/identity/consent requirements remain external release blockers.
