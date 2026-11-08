# Six-measurement M-VAS and supervised-visit flow — DISCONNECTED DRAFT

**2026-11-09 — NOT APPROVED; NO HUMAN ENROLLMENT AUTHORIZED.** This file documents the proposed code in src/prototype/pilot_session_flow_draft.py, with tests/test_pilot_session_flow_draft.py and pilot_measurements_draft.py. The deployed fictional demo is unchanged. No human enrollment or server-side integration is enabled.

## Proposed sequence

Visit 1: authorized staff admission -> 16 independent pretest questions -> M-VAS pre -> 20 practice questions (+ optional separate Arm A recovery actions) -> M-VAS post -> visit-end timestamp -> wait.

Visit 2: authorized admission 72–120 elapsed hours after prior visit END -> M-VAS pre -> 20 practice questions -> M-VAS post -> visit-end timestamp -> wait.

Visit 3: authorized admission 72–120 elapsed hours after prior visit END -> M-VAS pre -> 15 practice questions -> M-VAS post -> 16 independent posttest questions -> complete.

Total: 16+20+20+15+16 = 87 MCQs, six single-item fatigue ratings (0..100), three visit starts and ends. Recovery resources do not count toward the 55 practice question target.

## What the current pure draft tests

1. Exactly three stages of visits; 16/20/20/15/16 MCQ targets and six M-VAS responses with correct session order.
2. Out-of-order visit/stage, repeated response and answer-after-completion rejection.
3. Explicit no-release/no-staff flags reject a visit START. **These booleans do not authenticate staff or grant real release approval; they are external conditions mocked by tests.**
4. Timezone-aware nondecreasing event timestamps; exact 72–120 elapsed hours allowed between visits, beyond rejected.
5. M-VAS strict explicit integer response 0..100, no Boolean or float coercion, separate pre/post timestamps, within-session differences, missing values remain null.
6. Immutable, independent pure transition state. The model does not store participant identifiers or real data.

## Nonnegotiable integration blockers

- The existing ContentBundle validates SIX questionnaire PROMPTS within each fatigue form and the current RCTCandidateEngine offers ONE six-item fatigue form AFTER each session, then immediately permits the next session. The new pilot needs a different source-hashed candidate, different fatigue schema, mvas_pre and mvas_post action paths, a revised progression engine, accessible browser input and new tests on a fresh pilot-only database. Never relabel the old six-item fixture as the M-VAS.
- Real release evidence, staff/identity authentication, ethics/DPO decision, eligibility, consent BEFORE randomization, external approval and attendance evidence are mandatory; client-supplied Boolean flags must never be trusted as staff authorization.
- Server-side persisted transactional action IDs, retries/idempotency and signed timing/audit records need new integration tests. The pure draft does NOT provide these.
- PI must confirm elapsed hours versus local calendar days and approved visit exceptions. An approved translated M-VAS instrument, licensing, anchoring and digital equivalence are pending.
- All 95 questions and 32 resources still require expert sign-off; protocol/SAP, independent WCAG/security tests, external HTTPS concurrency, backup/restore and formally approved recruitment are separate gates.
- Keep the current fictional.sqlite3 and operator-demo deployment entirely separate from any human participant database.
- Arm A is a bundled POMCP plus recovery package, while B/C are question-only; efficacy claims cannot isolate POMCP from resource access.

## Local review

Run the new pure tests locally from agent2_realdata_benchmark with the existing Python environment:

    python -m pytest -q tests/test_pilot_session_flow_draft.py tests/test_pilot_measurements_draft.py

Then run the full 1,312-plus tests. Never deploy this review branch to the VPS before all approval gates have been independently met.


## Second iteration — isolated synthetic persistence (2026-11-09)

Additive, disconnected modules:
- src/prototype/pilot_session_store_draft.py
- tests/test_pilot_session_store_draft.py

A new, explicitly synthetic-only SQLite file format stores participant state, stage, offered/rendered/completed placeholder actions, request-level idempotency and an append-only synthetic event audit. Only IDs prefixed SYN_PILOT_ can be issued/read; this is not staff identity verification, eligibility verification, consent or allocation. It is deliberately **not** an extension of the live RCTCandidateEngine and does **not** provide MCQ content/scoring or a web endpoint. Only synthetic choice letters are recorded.

The new tests cover three supervised visits and 93 completed actions (87 counted MCQ placeholders + six 0–100 M-VAS responses), failure to bypass session windows, invalid/duplicate responses, foreign IDs, persisted state and pending actions across restart, concurrent synthetic next-action calls, version mismatch rejection and an on-disk SQLite backup/restore with restrictive file permissions.

Caveats: caller-controlled timestamps and booleans are only acceptable in this OFFLINE synthetic test harness; they are not a human-study admission gate. Real staff authorizations must be server-generated, role-checked and audited. Backups are not encrypted or off-server, do not meet research-data operational requirements. There is no student-identifying data, no UI, no effective randomization, no clinical instrument validation, no authenticated web release, and no human enrollment.

**Run locally:** from agent2_realdata_benchmark (using its Python venv):

    python -m pytest -q tests/test_pilot_session_store_draft.py tests/test_pilot_session_flow_draft.py tests/test_pilot_measurements_draft.py
    python -m pytest -q

Prior baseline was 1,319 passed; the added nine synthetic-persistence tests would increase collection to 1,328 if all pass, but the new code has not yet been tested in the user's WSL environment.

**Do not merge/deploy this review branch to the existing operator demo or migrate its fictional database.**
