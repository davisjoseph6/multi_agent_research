# Full fictional study: latency phase attribution and recovery verification

**2026-11-09. DRAFT, LOCAL SYNTHETIC SOFTWARE ONLY. DO NOT DEPLOY OR ENROLL PEOPLE.**

## What has actually been verified

The user confirmed commit `fbf1c9a` has **1,379/1,379 local WSL tests passing**, clean worktree. The complete three-visit synthetic runner passed twice without application failures:

| Test | 9 participants, 3 threads, 41 simulations | 30 participants, 5 threads, 240 simulations |
|---|---:|---:|
| Completed participants | 9/9 (3/arm) | 30/30 (10/arm) |
| Completed visits | 27 | 90 |
| Pretest, practice, posttest answers | 144 / 495 / 144 | 480 / 1,650 / 480 |
| Proposed pre/post M-VAS entries | 54 | 180 |
| Arm A optional recovery actions | 18 | 60 |
| Verified request-ID replays | 135 | 450 |
| Action calls | 855 | 2,850 |
| p50 / p95 latency | 9.550 / 15.494 ms | 10.970 / **238.907** ms |
| p99 / maximum latency | 385.812 / 2,440.308 ms | **1,153.429 / 5,043.366 ms** |
| Wall duration | 9.482 s | 38.736 s |
| Failures | 0 | 0 |

The two workloads vary in **both number of concurrent participants and planner simulations**, so their latencies **cannot** be interpreted as a controlled A/B speedup test. The fictional answers and identical 15-point fatigue differences are fixtures, not actual educational outcomes, so they cannot justify any effectiveness or noninferiority claim.

The source-level release safety and research constraints are unchanged. The prior optimistic planner rewrite in PR #10 produced a **measured regression** in the first-visit test despite passing all functional tests; it remains unmerged and must not be used as a shortcut.

## What this branch adds

- **Instrumentation of the complete three-visit synthetic workload** using the previously tested `_MeasuredSyntheticStore` wrapper: captures time spent in `next_action`, `mark_rendered`, and `submit` separately; SQLite transaction-entry times for each; per-arm and per-visit latency distributions; count of actions exceeding descriptive 250 ms and 1,000 ms; ten slowest synthetic actions by arm, visit, stage and action type **without participant identifiers**.
- Retains the same three-arm engine, frozen local synthetic items, response/recovery budgets, immutable question counts, virtual timestamps and idempotency behavior. It does **not** change policy selection or production code.
- **Two isolated SQLite online-backup restore tests**: restart with a pending rendered question, verify the pending action is identical, verify a previously committed response replays exactly once, and verify arm A/B/C allocations remain separated. This is **not** an encrypted offsite backup, RPO/RTO, data-center disaster recovery or approval for human data.

SQL timing **includes Python connection creation, PRAGMAs and potential `BEGIN IMMEDIATE` wait**. It is not pure lock-wait timing and cannot isolate planner CPU vs OS scheduling without further investigation. The test omits HTTPS, browser, authentication and other real pilot operations.

## WSL commands for operator validation

From a new isolated review worktree of `research/ijcai2027-fulljourney-phase-diagnostics-20261109`, under `agent2_realdata_benchmark`:

```bash
PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"

"$PY" -m pytest -q \
  tests/test_pilot_full_journey_rehearsal.py \
  tests/test_pilot_synthetic_restart_recovery.py

# Copy frozen ASSIST2009 processed/splits from the base worktree before:
"$PY" -m pytest -q

"$PY" -m scripts.pilot_full_journey_rehearsal \
  --participants 30 --workers 5 --simulations 240 \
  > "$HOME/ijcai_threevisit_phase30_240.json"
"$PY" -m json.tool "$HOME/ijcai_threevisit_phase30_240.json"
```

Previous full suite 1,379 + **three new regression tests** = **1,382 expected** after full local fixture reconstitution, not yet verified. At minimum, review `sqlite_phase_latency_ms`, `per_arm_latency`, `per_visit_latency`, `actions_over_1000ms`, `slowest_10_actions`, and failures. Repeated independent runs under controlled host load are needed before claiming an optimization or a service-level acceptance target.

## Required next research/operations gates

Even if this entire synthetic test battery passes, **human pilot remains NO-GO**. Complete and independently approve the actual 95 questions and 32 resources, M-VAS exact wording/digital equivalence, 90/75 feasibility-vs-confirmatory sample-size rationale, registered protocol and SAP, GDPR/controller/DPO and competent ethics pathway, participant information and consent, concealed randomization, verifiable staff role/eligibility enforcement, real server-clock 3–5-day visits, secure dedicated hosting, external HTTPS and device load, WCAG and penetration testing, encrypted offsite backup with RPO/RTO and restore rehearsal, source freeze and written institutional/PI GO. These are separate deliverables requiring responsible people and actual infrastructure.

**No VPS or external host changes in this branch; no real participant data.**
