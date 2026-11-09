# Three-visit disposable SQLite: DELETE vs WAL journal sensitivity

**2026-11-09. EXPERIMENT ONLY. LOCAL FICTIONAL RECORDS. NO DEPLOYMENT OR HUMAN STUDY.**

## Evidence prompting the experiment

User verified source `3980da5`: **1,382/1,382 WSL tests passed**, clean worktree, and 30/30 fictional participants completed all three visits using five threads and 240 POMCP simulations. No application failures.

| Phase measure (ms) | p50 | p95 | p99 | max |
|---|---:|---:|---:|---:|
| Complete next/render/submit action | 11.803 | 228.899 | **1279.079** | 4662.624 |
| SQLite transaction entry, summed across action phases | 0.234 | 209.410 | **1263.723** | 4647.243 |
| next_action total | 4.484 | 121.477 | 989.096 | 4656.773 |
| next_action SQLite entry | 0.065 | 104.942 | 981.188 | 4647.090 |

Across 2,850 complete action calls, **41 exceeded 1 second**. Slow examples are present in all three arms and across visits 1–3, not only the POMCP-intensive Arm A. Timings include connection setup, PRAGMAs, SQLite BEGIN IMMEDIATE lock acquisition, and OS scheduling; they do **not** isolate lock-wait time causally.

## Narrowest safe experiment

This research branch adds a `journal_mode` selection **only to the local disposable full-journey test harness**:

- `delete` (default): SQLite's rollback journal, reproducing the original local rehearsal storage behavior.
- `wal`: explicitly enable write-ahead logging after the brand-new temporary synthetic store is initialized, **before creating any fictional participant**.
- Never change an existing SQLite database on disk, the original fictional three-person browser file, operator/VPS database, research data, real-study information, installed packages, or the published pilot state machine.
- Report the verified SQLite journal mode and explicitly state that WAL **does not allow multiple concurrent writers**, is **not an approved production database design**, and this is not evidence of production capacity.
- WAL can help readers proceed concurrently with a writer and affect commit latency, but does not eliminate serialized writes under one SQLite database. The previous optimistic-planner rewrite (PR #10) was a latency regression and remains excluded.

**Both configurations use the exact same high-level three-visit test workflow** and verify 16 pretest + 55 practice + 16 posttest, six proposed fatigue readings, A/B/C balancing, <=2 A recoveries per visit, zero B/C recoveries, replay-safe responses and 3–5-day virtual spacing. Synthetic item choices and random planner state are **not fixed or paired** across runs; results remain noisy.

## WSL verification

From the new isolated review worktree under `agent2_realdata_benchmark`:

```bash
PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q tests/test_pilot_full_journey_rehearsal.py tests/test_pilot_synthetic_restart_recovery.py
# After copying the private frozen ASSIST2009 fixtures:
"$PY" -m pytest -q
```

The previous WSL full suite was 1,382 passing tests; this branch adds **two**, so 1,384 are expected **only if the new tests and all regression tests actually pass on WSL**.

Run on a locally idle WSL filesystem, **not** against VPS or any public server:

```bash
"$PY" -m scripts.pilot_full_journey_rehearsal \
  --participants 30 --workers 5 --simulations 240 --journal-mode delete \
  > "$HOME/ijcai_fulljourney_delete_240.json"

"$PY" -m scripts.pilot_full_journey_rehearsal \
  --participants 30 --workers 5 --simulations 240 --journal-mode wal \
  > "$HOME/ijcai_fulljourney_wal_240.json"
```

Run **at least three separate paired repetitions** of both modes before drawing a conclusion; alternate ordering across pairs (DELETE→WAL, WAL→DELETE). Record p50/p95/p99/max for the complete action and `sqlite_phase_latency_ms.sqlite_begin_total_ms`, number of actions over 1 second, CPU/RAM and wall clock. Do not accept WAL as superior based on a single sample; stop if any functional invariant, integrity, pending-action replay or restore regression occurs.

## Decision after comparisons

If WAL consistently lowers high-percentile latency without breaking correctness, it may be a useful **synthetic/staging** configuration. It is **not** a long-term architectural substitute for an independently reviewed transactional, row-level locking/queueing design, potentially PostgreSQL, for a human RCT. That requires a new privacy/security architecture, consent/recruitment separation, independently verified trial allocation and review of real peak concurrency.

If it does not reliably improve tail latency, reject this optional experiment and preserve the locally validated 1,382-test baseline rather than propagating another unmeasured change.

## External NO-GO

No real participant records, institutional controller, PI/statistician power signoff, ethics/DPO decisions, approved 95 items/32 resources/M-VAS, approved consent materials, independent WCAG/security/device/HTTPS load, offsite encrypted recovery or final written institutional GO. All remain mandatory and unverified.
