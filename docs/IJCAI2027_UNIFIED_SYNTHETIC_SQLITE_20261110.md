# IJCAI 2027 unified single-SQLite synthetic milestone

**10 November 2026. Synthetic engineering only. No human enrollment,
verified staff identity, content/instrument approval or public hosting.**

This branch builds on the existing private VPS fictional preview,
synthetic admission contract, and separate-database A/B/C three-visit pilot.

## What changed

The **new** `UnifiedSyntheticStudyStore` constructs the pre-existing
admission and adaptive-learning synthetic schemas **in one SQLite file**,
retains their approved-for-humans=false semantics, and adds a foreign-key
linked `unified_links` table. It is not imported by the Flask preview or
any public RCT interface. Admission and quiz use the same local
`BEGIN IMMEDIATE` write transaction for combined operations.

The following boundaries now have an **all-or-nothing single-file
transaction**:

- After synthetic offline eligibility screening, consent to an exact
  fictional information hash, concealed A/B/C allocation and corresponding
  learning record creation (no orphan on mid-operation failure)
- Supervisory start of a visit, including both attendance ledger and V3
  learning-stage update, with the 72–120-hour elapsed gap constraint
- Attendance completion only after the same learner has completed the
  corresponding learning session, including atomic audit event
- Synthetic withdrawal and the learner-state tombstone; an outstanding
  question can no longer be submitted following that transition

The integration test deliberately injects failures after partial writes and
checks that the transaction rolls back completely. It reopens the database
between visits, checks allocation secrecy, runs real draft quiz actions,
tests duplicate-response idempotency, and audits linked stages/attendance.
The admission hash chain detects accidental tampering, not an attacker
with database write access.

The code does **not** provide production isolation, real consent,
real staff authentication or SSO, independent approval, encryption/key
management, retention/erasure handling, power analysis, external audit,
production load testing, or a real browser for the unified implementation.
Question delivery still uses the synthetic learning engine. This removes
the **cross-file inconsistency in the newly combined synthetic architecture**,
not every possible production failure mode.

## WSL: reproduce the single-file simulation

```bash
cd ~/multi_agent_research
git fetch origin
git worktree add --detach ../ijcai_unified_review_20261110 \
  origin/research/ijcai2027-unified-sqlite-synthetic-20261110
cd ../ijcai_unified_review_20261110/agent2_realdata_benchmark
PY="$HOME/ijcai_http_acceptance_20261110/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q \
  tests/test_pilot_unified_sqlite_synthetic.py \
  tests/test_pilot_unified_sqlite_rehearsal.py \
  tests/test_pilot_unified_vps_report_check.py
"$PY" -m scripts.pilot_unified_sqlite_rehearsal \
  --participants 30 --simulations 41
```

Expected: `PASS_SYNTHETIC_ONLY`, 30 fictional records, 90 visits,
2,610 questions, 180 proposed fatigue measurements, no network calls,
and automatic deletion of the sole temporary database.

The 30 assignments may be 10/10/10, 10/11/9, etc., because random
permuted blocks of six or nine may not align exactly with sample size 30.

## Safe VPS transfer and **offline** execution (manual only)

Only after GitHub CI and local focused tests have passed:

```bash
cd ~/ijcai_unified_review_20261110
test -z "$(git status --porcelain)" || exit 1
git rev-parse --short HEAD
VPS="<your-existing-VPS-address>"
ssh -i ~/.ssh/ijcai_preview_ed25519 "davis@$VPS" \
  'mkdir -p ~/ijcai_unified_vps_20261110'
set -o pipefail
git archive --format=tar HEAD agent2_realdata_benchmark docs | \
  ssh -i ~/.ssh/ijcai_preview_ed25519 "davis@$VPS" \
    'tar -xf - -C ~/ijcai_unified_vps_20261110'
```

SSH into the VPS, **without stopping the existing systemd service**:

```bash
cd ~/ijcai_unified_vps_20261110/agent2_realdata_benchmark
PY="$HOME/ijcai_preview_5c6bb17/.venv/bin/python"
test -x "$PY" || exit 1
"$PY" -m pytest -q \
  tests/test_pilot_unified_sqlite_synthetic.py \
  tests/test_pilot_unified_sqlite_rehearsal.py \
  tests/test_pilot_unified_vps_report_check.py
bash -n ops/rct/run_unified_fictional_vps.sh
bash ops/rct/run_unified_fictional_vps.sh
```

The batch runs as `davis` with restricted output permissions, reduced
CPU priority, timeout and a strict machine-validated synthetic-only report.
It opens **no port** and modifies no Caddy/Nginx/systemd configuration.
The existing 127.0.0.1:8766 browser preview remains untouched.

## Release checklist (not yet complete)

- Real institutional staff identity, session administration and
  participant access controls (MFA, roles, revocation, authentication)
- Privacy-approved participant dataset and retention/deletion machinery
- Independent authorization, recruitment, and research study release gates
- Content/measurement approval (95 quiz items, 32 resources, proposed M-VAS)
- Production session, clock, consent/withdrawal and scheduling user experience
- HTTPS/TLS ingress architecture, dependency/penetration/accessibility testing
- Production concurrency/device testing, monitoring, encrypted backups,
  disaster-recovery exercises and independent code review
- Six unavailable fixture-dependent legacy tests still excluded from
  self-contained CI, until their reference data and parity fixtures
  can be supplied without exposing restricted material

Human enrollment must remain disabled; a passing fictional report does
not count as a scientific outcome or a final production authorization.
