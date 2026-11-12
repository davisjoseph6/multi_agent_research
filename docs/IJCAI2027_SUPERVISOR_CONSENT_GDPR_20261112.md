# Supervisor consent/GDPR — implementation and test matrix

Status: 12 November 2026; synthetic-only code, no live enrollment or email.
Draft PR #35 targets the existing supervisor A/B/C **parallel-group** RCT, not the superseded crossover PR.

## Added without replacing the validated engine

- Exact submitted v1.0 English/French six required consent declarations, plus separate optional open-data permission.
- Versioned English/French Annex information sheets in content/consent, with language switch and PDF builder.
- In-memory consent and screening drafts until registration; 6/8+ anonymous exclusion log only (timestamp, score, no email).
- Single SQLite transaction for versioned consent metadata, age, program, eligible learner, A/B/C rotation, SHA-256 token hash and separate private contact table.
- Case-insensitive duplicate-email refusal and no first/last names.
- Full private browser screens for information, six checkboxes, one-by-one screening, registration, quiz, stop/keep, stop/delete and debriefing.
- Safe default: old one-box shortcut disabled outside synthetic unit-test mode; no real email or human enrollment.
- Transactional stop/keep with token revocation; stop/delete removing all linked research and PII rows, with minimal deletion_log.
- Explicit offline admin operations for email-forwarded withdrawal requests, completed-only 0600 points_export.csv, and close-collection contact/known-backup cleanup.
- Synthetic daily one-shot scheduler for 24-hour reminder previews and two missed-session removals with token revocation.
- Comprehensive regression and supervisor-specific GitHub CI, with concurrency cancellation of obsolete runs.

## Acceptance cases in guide

| Guide test | Automated coverage |
|---|---|
| 1. Five of six boxes cannot proceed | consent_gdpr case 01 + HTTP |
| 2. Optional blank does not block; stored as no | consent_gdpr case 02 + HTTP |
| 3. Economics course exits without persistence | consent_gdpr case 03 + HTTP |
| 4. Six correct screening items yield anonymous exclusion | consent_gdpr case 04 + HTTP |
| 5. Four correct yield registration and hash-only token | consent_gdpr case 05 + HTTP |
| 6. Duplicate email refused | consent_gdpr case 06 + HTTP |
| 7. French version stored as fr | consent_gdpr case 07 + HTTP |
| 8. Stop/keep preserves responses and invalidates token | consent_gdpr case 08 + HTTP |
| 9. Stop/delete erases linked rows and writes single log | consent_gdpr case 09 + HTTP |
| 10. Two missed sessions remove learner | consent_gdpr case 10 + daily scheduler |
| 11. Session 3 completion produces debrief and private points export | consent_gdpr case 11 + earlier full journey |
| 12. Close collection removes contacts but keeps research | consent_gdpr case 12 + offline admin |

These are automated checks against fictional .test addresses, **not** actual delivered emails or a five-user acceptance pilot.

## Run in a new WSL worktree

    cd ~/multi_agent_research
    git fetch origin
    git worktree add --detach ../ijcai_gdpr_validation origin/research/ijcai2027-supervisor-consent-gdpr-20261112
    cd ../ijcai_gdpr_validation/agent2_realdata_benchmark
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r requirements-prototype.txt
    python -m pip install pytest==9.1.1
    python -m pytest -q tests/test_supervisor_20261111_*.py tests/test_supervisor_20261112_*.py
    python -m scripts.supervisor_consent_pdf
    python -m scripts.supervisor_fictional_browser --port 8783

The preview binds only to 127.0.0.1 and uses fictional aliases F1/F2/F3. Never open this through a public reverse proxy or the VPS.

## External approval and software release barriers

- Professor Yaacoub must fill the original Annex placeholders, approve the v1.0 legal wording and confirm formal administrative protocol validation. No text is to be silently rephrased after validation.
- A real EU data controller/hosting arrangement, independent IAM and DPO review, production TLS and audits are not delivered by the fictional preview.
- Verified real email sender, invitation/resume links, delivery acknowledgments and secret management remain disabled. A memory-only notification capture is **not** an email.
- Backup unlinking is not a physical media wipe or production erasure certification; every EU replica and archived snapshot requires documented handling.
- The exact approved fatigue instrument and per-concept recovery resources, true model training data, and five-person acceptance pilot remain independent requirements.
- The guide simultaneously requests immediate Session 1 and reminders 24 hours before each session. A reminder cannot precede immediate Session 1; supervisor clarification is required. The preview supports Session 2/3 notices only.
- The guide defines pseudonymized retention using the last-publication date, which is not yet known. A real retention scheduler must be configured and approved later.

DO NOT MERGE OR DEPLOY PR #35 as a public study merely because tests pass. Human enrollment stays forbidden.

## Fast browser recovery check (fake F1 only)

The localhost preview now has a **Quick test: trigger Group A recovery (fresh F1 only)** button.
It uses the real supervisor CSV forms, the existing BKT engine, normal SQLite
answer transactions and the four prescribed recovery steps, without modifying
the actual study protocol. It programmatically signs fictional test declarations,
passes eligibility with 4/8, registers `quick-recovery-f1@example.test`,
completes all 16 pretest items using supervisor Case 1 starting mastery, and
answers C2 quiz items 01–03 incorrectly to trigger Rule 5b.

Start with a **fresh server process** (the fixture intentionally refuses reused
databases and previously registered F1). Click the quick-test button, then click
Continue on the displayed **CONCEPT_SUMMARY**. For **DROP_2**, select one of
the two displayed answers; the two-choice grading is real. Continue through
**WORKED_EXAMPLE**, then answer the **SOCRATIC_HINT** re-attempt. The next
regular quiz question should follow, and no recovery step counts toward the
20-question session block. Wrong recovery answers can change the recovery
outcome, so the exact final question may depend on your choices.

This is **not a bypass of the live consent process**: the demo endpoint only
accepts F1 on loopback in the isolated fictional launcher, uses `.test`
contacts, rejects nonfresh state and never dispatches messages. Do not expose
the localhost test server through the VPS, a tunnel or a public reverse proxy.

Focused test: `python -m pytest -q tests/test_supervisor_20261112_recovery_quick_demo.py`.
This test automatically selects correct answers on the two graded recovery
steps and checks the expected supervisor Case 1 next item and event counts.
