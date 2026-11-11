# Research V2 — Private fictional browser engineering runbook

**Date:** 11 November 2026
**Branch:** research/ijcai2027-proposed-research-v2-gates-20261111
**Status:** SYNTHETIC ONLY — not authorized for human enrollment, live emails, or public deployment.

## Implemented software

The browser binds only 127.0.0.1, port 8774 by default, and uses a private
nonce, same-origin and JSON request validation, no-store, frame denial,
referrer suppression and a strict content security policy. It has no real
recruitment, identity, consent or administration route. It displays F1–F6
fictional aliases and periods, not private tokens or assigned treatment arms.
A web-page nonce is NOT authenticated participant identity.

Six pre-enrolled fictional learners exercise all crossover sequences.
A learner completes 16 fake pretest, 55 fake practice and 16 fake posttest
items in each of three periods. All 261 unique normal question IDs are
synthetic arithmetic scaffolds, NOT peer-reviewed behavioral-economics items.

The browser persists server-scored answers, mandatory two-error Arm-A
recovery and its original wrong-option anchor, one-time instructional
DROP_2 retry, continued/paused state, and current-period BKT traces.
Pre/post correctness is not returned item by item. Mastery is withheld
during independent assessment and incomplete pre/post scores are hidden.

A separate fictional contact SQLite database supports opt-in, pause,
resume and opt-out. It accepts reserved .test email domains only.
The bilingual notice worker captures due reminders in memory, never
sending email via SMTP/API/network. Exactly-once real sending is NOT
provided by the local fictional SQLite idempotency key.

## Run in WSL from the pre-existing worktree

1. Enter the worktree: cd ~/ijcai_v2_validation
2. Confirm it is clean: git status --porcelain
3. Fetch latest: git fetch origin
4. Switch detached: git switch --detach origin/research/ijcai2027-proposed-research-v2-gates-20261111
5. Enter project: cd agent2_realdata_benchmark
6. Activate environment: source .venv/bin/activate
7. Check dependencies: python -m pip check
8. Start: python -m scripts.research_v2_fictional_browser --port 8774
9. In the local machine browser, visit http://127.0.0.1:8774

The launcher uses a temporary SQLite directory, deleted on process exit.
Do NOT expose this endpoint to a public interface, reverse proxy, VPS,
or third-party tunnel.

## Automated verification

From agent2_realdata_benchmark, run these two scripts:

    python -m scripts.research_v2_fulljourney_smoke
    python -m scripts.research_v2_reminder_dry_run

Run the targeted tests:

    python -m pytest -q tests/test_research_v2_proposal.py tests/test_research_v2_preflight.py tests/test_research_v2_reminder_outbox.py tests/test_research_v2_reminder_dry_run.py tests/test_research_v2_crossover_fixture.py tests/test_research_v2_fulljourney_smoke.py tests/test_research_v2_mastery_trace.py tests/test_research_v2_fictional_browser_http.py

Run the broad self-contained regression:

    python -m pytest -q --ignore=tests/test_assist2009_splits.py -k "not test_reference_forward_equivalence"

Test release denial:

    python -m scripts.research_v2_preflight

Expected: BLOCKED_NOT_APPROVED with process status 2. The five
ASSIST2009 tests and one external NeuralCD equivalence test require
legitimate separate research fixtures, not supplied by cloud CI.

## Outstanding for any real student study

- Independently approved 261-question EN/FR behavioral-economics bank
  and reviewed question-specific resources, answer-key checks and provenance.
- Genuine institutional consent, authenticated participant accounts,
  identity verification, privacy/data retention and governance.
- Real consent-based sender with signed resume links, provider-side
  idempotency, bounce handling and secure production secrets.
- An independently approved EN/FR fatigue instrument and timing.
- Approved change from the original parallel RCT to the proposed
  crossover, including carryover/period effects, sample-size and analysis.
- Independent accessibility and security evaluation, load tests,
  backup/restore, TLS/domain production deployment, and all signed
  institutional release evidence.

No code in this isolated preview supersedes the frozen original trial.
The draft PR must not be merged as production or exposed on the VPS.
