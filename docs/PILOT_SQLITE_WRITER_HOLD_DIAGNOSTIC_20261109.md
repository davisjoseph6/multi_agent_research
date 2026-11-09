# Synthetic SQLite writer-hold diagnostic and worker-count sensitivity

**2026-11-09. Draft, local fictional data only. Does not authorize human enrollment or VPS deployment.**

## Rejected experiment and retained base

- The WSL user fully verified the WAL journal experiment at `d0298f3`: **1,386/1,386 tests passed**, clean worktree.
- Six independent 30-participant, full-three-visit synthetic runs at 240 planner simulations and five workers all **PASS** with no functional failures. The benchmark alternated DELETE/WAL order across three pairs.
- The **median across the three run quantiles** was substantially worse with WAL:

| Metric | DELETE | WAL |
|---|---:|---:|
| Action p50 | 10.996 ms | 17.943 ms |
| Action p95 | 195.304 ms | 372.878 ms |
| Action p99 | 1,199.052 ms | 1,572.800 ms |
| SQLite entry p99 | 1,187.826 ms | 1,544.098 ms |
| Actions taking >1 second | 40 | 61 |
| Wall duration | 38.718 s | 51.604 s |

**Decision:** WAL experiment [PR #16](https://github.com/davisjoseph6/multi_agent_research/pull/16) is closed **unmerged** as a measured performance regression. SQLite DELETE remains the default. Neither WAL nor the earlier optimistic planner refactor in PR #10 is safe to adopt based on current performance data.

This branch intentionally begins from the **last full WSL-validated DELETE baseline `3980da5` (1,382 tests)**, rather than inheriting WAL. It changes **only measurement wrappers and the synthetic three-visit harness**, not application database transactions or action-selection algorithms.

## Why further timing matters

The 30-participant/240-simulation/three-visit report at `3980da5` recorded p95 **228.899 ms**, p99 **1,279.079 ms**, max **4,662.624 ms**, and **41 actions over 1 s**, with `sqlite_begin_total_ms` p99 **1,263.723 ms**. The slowest action took 4,662.624ms, including 4,647.090ms entering the `next_action` SQLite transaction. This implicates serialized write transaction entry, but *why the writer lock is unavailable so long* is unresolved.

### This new, narrow instrumentation

For each `next_action`, `mark_rendered` and `submit`, capture wall-clock:

1. **Entry:** connection creation, PRAGMAs and `BEGIN IMMEDIATE` acquisition (existing instrumentation; not isolated lock-wait time).
2. **Body:** time after transaction acquisition until returning from the operation's SQL/planning body, **while the SQLite writer lock is held**. In Arm A `next_action`, this includes POMCP selection.
3. **Finalize:** time to leave the parent transaction context (commit/rollback and close, plus scheduling).
4. Aggregate per action and compute p50/p95/p99/max for each phase, retaining previously reported arm/visit distributions and ten slowest actions without IDs.

This does **not** prove exactly how long the OS scheduler, filesystem or CPU planner operated. Timings include instrumentation and Python scheduling; comparison is observational.

## WSL verification

Create a new, isolated detached worktree of `research/ijcai2027-sqlite-writer-hold-diagnostics-20261109`, then in `agent2_realdata_benchmark`:

```bash
PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q tests/test_pilot_full_journey_rehearsal.py tests/test_pilot_synthetic_restart_recovery.py
# Copy frozen research fixtures from your original checkout, then:
"$PY" -m pytest -q
```

Expected full-suite test total: **1,383** (previously validated 1,382 + 1 new). Do not claim pass until verified.

For a controlled local worker-count comparison, run identical 30-person/240-simulation/DELETE workload with **one** and **five** worker threads:

```bash
"$PY" -m scripts.pilot_full_journey_rehearsal --participants 30 --workers 1 --simulations 240 \
  > "$HOME/ijcai_writer_hold_30_workers1.json"
"$PY" -m scripts.pilot_full_journey_rehearsal --participants 30 --workers 5 --simulations 240 \
  > "$HOME/ijcai_writer_hold_30_workers5.json"
```

Consider at least three independently repeated paired scenarios with alternating execution order, on a locally idle host, before deciding on queueing or transactional changes. Run 3 fictional participants first if hardware is constrained; do not overload an operational machine. For the one-worker run, expect low lock contention but a potentially longer overall elapsed time. Compare `sqlite_phase_latency_ms.sqlite_body_total_ms`, `sqlite_phase_latency_ms.sqlite_finalize_total_ms`, `sqlite_phase_latency_ms.sqlite_begin_total_ms`, and `latency_ms` p95/p99, plus `per_arm_latency` and failures.

**Interpretation:** If write-lock entry tail balloons with more threads while individual write-hold bodies are routinely fast, contention scheduling/SQLite writer queueing is the likely factor. If individual Arm A next-action body times are consistently long, selection under a RESERVED writer lock is structurally problematic. If finalize is long, inspect commit fsync and WSL filesystem. None alone proves a production remedy.

## Next architecture decision, requiring separate review

Before changing the live candidate, analyze: whether the true peak concurrency is 5 or less; the number of write transactions per question; grouping `next/render/submit` safely; whether a dedicated serialized writer queue would improve fairness; alternative DB design supporting participant-level row locks; and whether a new independently validated Postgres schema is appropriate. Never sacrifice audit evidence, arm-blinding, one-time scoring or immutable replay IDs for latency.

Actual **human** pilot remains **NO-GO**: pending approved protocol/SAP/power design and minimum meaningful learning effect, institutional sponsor/ethics/DPO, final 95 questions and 32 resources, valid fatigue instrument/anchors, consent materials and languages, concealed 1:1:1 allocation, staff authentication, server-enforced 3–5-day schedules, independent security/WCAG, real HTTPS/device load and encrypted offsite recovery with signoff. No IONOS server changes.
