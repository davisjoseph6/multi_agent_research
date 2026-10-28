# IJCAI 2027 — Browser-Visible Fixed Summary v1

Status: Local-only instructional software demonstration.

## Explicit mode

Run `create_durable_app(..., fixed_summary=True)` with the four-item
`INSTRUCTIONAL_DEMO_ITEMS` and `INSTRUCTIONAL_DEMO_VERSION`.
The existing unassisted browser retains its original files.

## Browser sequence

1. Answer a practice item; SQLite creates an offer atomically.
2. An offered summary hides the next practice question.
3. The learner explicitly accepts or declines.
4. Accepting records a decision but releases no resource body.
5. Clicking **View accepted summary** requests delivery separately.
6. The resource body appears only after backend delivery succeeds.
7. Clicking **Continue** reveals the upcoming practice question.
8. Declining skips delivery and reveals the question.
9. The independent probe has no preceding assistance offer.

The browser uses separate tab-scoped session-storage keys for the gated
mode, including an original request ID for uncertain submission retries.
The user's explicit Continue acknowledgement is stored per offer and
per session in tab-scoped storage; after a new tab/session, an already
released summary may be shown again. This does not create another
backend delivery event.

## Persistence and trust boundaries

SQLite is authoritative. Browser state is not a security gate.
Refreshing/restarting while an offer is offered or accepted does not
resolve it automatically; the learner decides explicitly.
Delivered content is recoverable through the authenticated-by-session-ID
GET assistance endpoint for this strictly local demonstration.
**Session IDs are not secure participant authentication.**
Do not deploy to an accessible network or collect participant data.
The resource text is intentionally rendered with `textContent`.

## Scientific limitations

Offer, acceptance, backend release, browser display and actual uptake
are distinct. Browser display is not measured by the SQLite ledger.
The summary and assessment items are illustrative and unvalidated.
The policy is fixed; POMCP remains shadow-only.
This is not evidence of improved learning or a causal recovery effect.
The held-out evaluation gate remains closed.
