# Fictional pilot acceptance audit — read only

**2026-11-09 — SYNTHETIC SOFTWARE EVIDENCE ONLY. NO HUMAN ENROLLMENT OR SCIENTIFIC VALIDATION.**

This increment extends the existing local-only browser demonstration on user-verified commit 5b53b9d (1,349 tests passed). It **does not modify the browser, runtime, service, WSGI factory, or VPS**.

Added:
- `src/prototype/pilot_fictional_acceptance_audit.py`: offline **read-only** inspection of precisely three fictional A/B/C records. Opens SQLite with `mode=ro`, `query_only=ON`, consistent read transaction; never seeds data or updates any record.
- `scripts/pilot_fictional_acceptance_audit.py`: simple CLI, prints JSON report; returns exit status 0 only for `PASS_SYNTHETIC_ONLY`.
- `tests/test_pilot_fictional_acceptance_audit.py`: five new tests including complete 3-arm synthetic rehearsal with all fatigue responses 99/99, incomplete sessions, tampered fatigue response, symlink/nonfictional DB refusal, and an extra fictional person.

## Inspect the previously completed local browser rehearsal

Use the **same Python virtual environment** as the successful WSL test commands, from `agent2_realdata_benchmark` in an isolated checkout of this audit branch:

```bash
PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m scripts.pilot_fictional_acceptance_audit
```

By default reads ONLY:

    ~/.cache/ijcai2027_fictional_browser_preview/fictional_browser_preview.sqlite3

Never passes real student identities, content or answer keys into the report. Does **not** modify the database. For a report saved without changing data:

```bash
"$PY" -m scripts.pilot_fictional_acceptance_audit > "$HOME/ijcai_fictional_readonly_audit.json"
```

All three fictional participants must have exactly:
- Three completed visits and 72–120 *virtual* hours between the end of one visit and the start of the next.
- 16 pretest responses in Visit 1, 55 distinct practice questions distributed 20/20/15 across Visits 1/2/3, and 16 posttest questions in Visit 3.
- Exactly one M-VAS response immediately before and after each of three practice blocks (six readings, each an integer 0–100). Form responses must match saved participant state.
- Arm A at most two optional recovery resource actions per visit (resources do not count as practice questions); Arms B/C no recovery actions.
- No pending/unrendered actions, inconsistent public/private item IDs, exposed answer keys in public question payloads, or selected action drift.
- Matching policy version and 41-simulation **fictional** browser configuration, with SQLite `integrity_check=ok` and no FK issues.

The resulting `PASS_SYNTHETIC_ONLY` is **not evidence** of statistical learning effects, psychometric validity, real student enrollment authorization, security accreditation, time-on-task compliance, actual supervised attendance, or a production pilot.

### Expected audit of the user's present fictional DB

Based on the user's last read-only snapshot, all three arms are at `complete` with six ratings of 99 (99/99 for each visit). Thus per-visit fatigue differences are **0,0,0**. The audit should report these without making scientific claims, provided all recorded actions and item IDs pass. Note: the auditor has not yet been executed on the user's machine.

### Test commands

```bash
"$PY" -m pytest -q tests/test_pilot_fictional_acceptance_audit.py
"$PY" -m pytest -q
```

Prior verified baseline was 1,349 tests. Five added tests suggest 1,354 if they pass, but this is not a verified result until executed.

## Remaining steps before human-study software readiness

- Frozen, independently-reviewed candidate with real server-derived timestamps, concealed block randomization, participant authorization/consent and staff roles.
- Approved content: all 95 questions, 32 resources, a validated and appropriately translated/signed-off fatigue instrument.
- Confirm pilot protocol and SAP/power model, specified estimands and Arm A's additional recovery-content intervention exposure.
- Independent browser/accessibility, external security, concurrency/load, failure/restore/backup and device testing; actual production hosting/TLS/monitoring/privacy procedures.
- Institutional ethics/DPO approvals and formal written authorization BEFORE any real participant enrollment.

Keep the existing IONOS fictional VPS demonstration isolated and unchanged. Never deploy this audit branch as the live RCT.
