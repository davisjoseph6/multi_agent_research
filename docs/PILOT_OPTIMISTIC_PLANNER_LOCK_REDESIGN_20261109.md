# Synthetic POMCP planner moved outside the SQLite global write lock

**2026-11-09 • Experimental review branch • no human enrollment • not deployed**

## Prior observed evidence

The user verified commit `13ed3b1`: 1,364/1,364 WSL tests passed. Two first-visit parallel workloads, each 30 fictional participants, five workers, no failures:

| POMCP simulations | p50 | p95 | p99 | max | >1s actions |
|---|---:|---:|---:|---:|---:|
| 41 | 10.994 ms | 17.073 ms | 889.947 ms | 4,157.015 ms | 11 |
| 240 | 9.607 ms | 17.634 ms | 720.475 ms | 4,449.785 ms | 10 |

The worst 240-simulation action spent 4,432.98 ms entering SQLite's `BEGIN IMMEDIATE` transaction. Most slow actions across all arms showed the same pattern. This implicates **global SQLite writer contention**, not just the planner's CPU time. `sqlite_begin_*` also includes connection creation and PRAGMA setup, so the numbers are not pure lock-wait measurements.

## Minimal isolated refactor

Changes exclusively to `src/prototype/pilot_three_arm_store_draft.py`:

1. Read the participant state, three-arm policy and existing pending action in a short SQLite **read transaction**, using `mode=ro`, consistent snapshot, and `query_only=ON`.
2. Close that read transaction before computing the deterministic selector (including 240-simulation Arm A POMCP), so it holds **neither the RESERVED writer lock nor a shared read transaction during planning**.
3. Prepare a full candidate action from a **deep-copied policy**. A losing proposal cannot accidentally spend Arm A's recovery budget.
4. Acquire `BEGIN IMMEDIATE` for a brief publish transaction; reread live state/policy and pending action **under that write lock**.
5. If an action was published by another writer, return it. If the state/policy changed, discard the proposal and retry with fresh state. Only when the snapshot matches may the proposal atomically insert into `pilot_actions`/`pilot_three_arm_selected`, update policy and record an audit event.
6. Limit retries to 32; fail closed on unending contention instead of silently overriding state or publishing duplicate actions.

Other `submit`, render, BKT, content, policy version constants, staff simulation, real study code, and public VPS paths remain unchanged. **Database policy fingerprints intentionally change on this branch**. Do not point new code at any old populated fictional SQLite file, including the previously audited three-person browser database. Use only disposable newly initialized local test DBs.

## Race regressions

Two added tests:

- Block Arm A's selector deliberately, and prove a simultaneous Arm C action completes while the Arm A planner remains blocked. This catches accidental planner-in-writer-lock regressions.
- Force two Arm A proposals for the **same participant** to race, and check they publish one identical pending action and never spend more than one recovery resource unit.

Existing tests cover duplicate submissions, stale and foreign action refusal, three full visits, independent bank consistency, recovery budget, 55-item inventory, and SQLite backup/replay. The full WSL regression baseline was 1,364; branch adds two new tests, so **1,366 is expected but unverified** until run locally.

## Verification (local WSL only; no HTTP requests)

Run in an isolated worktree of this PR:

```bash
PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q tests/test_pilot_three_arm_store_draft.py tests/test_pilot_concurrency_rehearsal.py
# Copy existing ASSIST2009 frozen artifacts into the isolated worktree.
"$PY" -m pytest -q
"$PY" -m scripts.pilot_concurrency_rehearsal --participants 30 --workers 5 --simulations 41 > "$HOME/ijcai_optimistic_load41.json"
"$PY" -m scripts.pilot_concurrency_rehearsal --participants 30 --workers 5 --simulations 240 > "$HOME/ijcai_optimistic_load240.json"
```

Compare p50/p95/p99/max, action latencies split by arm, `sqlite_begin_total_ms`, and the slowest ten actions to the previous baseline, ideally over multiple runs on an idle WSL machine.

If tail latency remains high, profile process scheduling, filesystem/WSL I/O, SQLite lock wait and concurrent planner CPU; do not claim an optimization worked without comparative evidence.

## Human-study release boundary

This refactor is **only for the isolated synthetic three-arm rehearsal**. The new protocol, content, M-VAS, consent, ITT allocation, authentication, real server timestamps, privacy and independent security/accessibility/production hosting remain separately blocked. No live recruitment, no public server changes, no deployment to `demo.selfhealing-edu.fr`. The full 14-item GO/NO-GO evidence checklist remains pending.
