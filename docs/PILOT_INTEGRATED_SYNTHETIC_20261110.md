# IJCAI 2027 — Integrated synthetic admission-to-learning exercise

**Status:** disconnected engineering acceptance / no real student enrollment.
**Do not install this into the existing private VPS browser preview.**

This branch stacks on the independently tested synthetic admission contract.
It uses two previously separate offline engines together, with temporary
SQLite data for every run. The admissions subsystem privately assigns A/B/C
with cryptographically shuffled blocks; the quiz subsystem receives that arm
only from a staff-only fixture method. The fictional participant status
response never includes the arm or any internal roster identifier.

## Reproduce without touching the VPS

Use a separate worktree and the already working Python virtualenv from the
private HTTP acceptance checkout (Ubuntu/WSL):

```bash
cd ~/multi_agent_research
git fetch origin
git worktree add --detach ../ijcai_integrated_review_20261110 \
  origin/research/ijcai2027-synthetic-admission-learning-integration-20261110
cd ../ijcai_integrated_review_20261110/agent2_realdata_benchmark
PY="$HOME/ijcai_http_acceptance_20261110/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q tests/test_pilot_integrated_synthetic_journey.py \
    tests/test_pilot_admission_controls_draft.py
"$PY" -m scripts.pilot_integrated_synthetic_journey --participants 9
```

The nine-record test is part of the regression suite. When it passes and the
workstation has sufficient memory/CPU, an additional disposable 30-record
exercise is available:

```bash
"$PY" -m scripts.pilot_integrated_synthetic_journey \
  --participants 30 --simulations 41
```

For each fictional participant, the harness enforces this chain:

1. Server-side synthetic invitation, staff fixture screening, explicit
   agreement to the exact versioned information hash
2. Concealed private randomized A/B/C assignment and independent
   role-restricted lookup by the offline research fixture
3. Synthetic record creation on the *actual* prototype adaptive-learning
   engine, using only the already allocated private treatment
4. Three interleaved synthetic attendance starts, full 16-item pretest,
   55 unique practice questions across visits 20/20/15, 16-item posttest,
   six proposed 0–100 M-VAS responses and bounded Arm A recovery,
   with four virtual days between visit starts
5. Immutable pending-action reoffer, required render acknowledgement,
   exactly-once synthetic submission and replay validation
6. Three attendance finishes, three learning finishes, matching hidden arm,
   independent aggregate study audit and independent admission integrity audit

All fixtures and role-capability bytes are generated at runtime and removed
with the temporary directory. The report contains no PID, bearer token,
participant mapping, question text or private answer. The script has no
hostname/URL parameter, HTTP runner, or enrollment route.

## What this test does not establish

The two SQLite stores still have **separate transactions**, no
cross-database commit/reconciliation protocol, no multi-process deployment,
and no real human data. The interval checks use an injected virtual clock.
The research staff are represented only by secret fixture bytes, not
verified institutionally authenticated people.

This does not supply validated consent, PI approval, student eligibility,
statistical design, real fatigue instruments, content approvals, production
database design, secure role-based web APIs, user identity, WCAG evaluation,
TLS penetration tests, independent security testing, offsite backups,
or disaster-recovery proof. It cannot open the legacy live-enrollment engine:
that engine is still unconditionally fail-closed.

This is a reproducible **integration test** of working prototype components,
not evidence that the production human trial has been built or authorized.
