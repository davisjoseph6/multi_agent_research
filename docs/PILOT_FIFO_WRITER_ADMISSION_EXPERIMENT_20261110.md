# Concurrent synthetic SQLite admission: FIFO scheduling versus native contention

**2026-11-10. Experimental, disposable synthetic workload only. No human enrollment or public server changes.**

## Verified baseline and diagnosis

The operator locally verified head `0013106`, **1,383/1,383 WSL tests passed**, clean worktree. Thirty fictional participants each completed three virtual visits with 240 POMCP simulations, using either one or five worker threads; both runs reported **PASS, no functional failures**.

| Measurement | 1 worker | 5 workers |
|---|---:|---:|
| Complete action p50 | 11.669 ms | 11.741 ms |
| Complete action p95 | 24.162 ms | **240.406 ms** |
| Complete action p99 | 33.438 ms | **1,107.288 ms** |
| SQLite transaction-entry p99 | **0.682 ms** | **1,096.584 ms** |
| Transaction body p99 | 10.195 ms | 9.709 ms |
| Transaction finalize p99 | 24.855 ms | 16.187 ms |
| Actions above 1 second | 0 | 33 |
| Elapsed wall time | 44.894 s | 39.506 s |

**Interpretation:** Writer-admission delays, rather than in-transaction body or commit/close execution, grow dramatically with five workers. This is strong observational evidence of serialized SQLite writer contention and scheduling/fairness issues. Instrumentation for entry includes connection creation, PRAGMAs and `BEGIN IMMEDIATE`, not pure lock wait. Only one run per worker count was performed; no production SLO exists.

Prior experiments rejected:
- Optimistic POMCP outside SQLite write lock **PR #10**: passed functionality, but regressed p95/p99 under the user's first-visit workload.
- WAL journal **PR #16**: closed unmerged after three paired 30-person/240-simulation runs; median WAL p95 **372.878ms** vs DELETE **195.304ms**, p99 **1572.800ms** vs **1199.052ms**, actions above 1s **61** vs **40**. WAL does not allow concurrent writers.

## New process-local FIFO queue: purely experimental

Adds `--writer-admission fifo|native` to the **disposable full three-visit fictional rehearsal only**, default `native`.

For FIFO mode, a `threading.Condition` manages monotonically increasing *tickets* around the existing ordinary SQLite `BEGIN IMMEDIATE` transaction and through SQLite commit/close. Exactly one **thread within that Python store instance** may try to acquire the writer connection at a time; waiting workers sleep in Python condition wait instead of independently competing for SQLite's writer lock. Tickets advance in a `finally` block on success or rollback. This does not change any policy, treatment, action IDs, scoring, POMCP, content, audit trail, SQL persistence, journal setting or study state. The original `_transaction` implementation is untouched.

The timer now records `writer_queue_wait_*_ms` separately. In native mode, the synthetic queue wait is always zero by definition; its **actual contention remains inside** `sqlite_begin_*`. In FIFO mode, queue wait is counted in the action's total latency. Therefore **compare total end-to-end action latency, tail counts and elapsed time first**; a lower SQLite entry time in FIFO mode is not sufficient to conclude an improvement if total wait merely moves to the Python queue.

**Important limitations:** FIFO applies only to transactions on a *single* Python instance in a *single* process. It does NOT coordinate multiple Gunicorn/WSGI worker processes, machines, independent SQLite connections outside the wrapper, filesystem locking, database interruptions or human student requests. Under a real deployment, a reviewed multi-process database/worker architecture is still needed. The apparent fairness improvement may reduce throughput or worsen p99; no result is assumed.

## Automatic alternating-order comparison

From the new isolated worktree, under `agent2_realdata_benchmark`:

```bash
PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q \
  tests/test_pilot_full_journey_rehearsal.py \
  tests/test_pilot_writer_admission_pair_comparison.py
# Copy frozen ASSIST2009 fixture files from the original worktree.
"$PY" -m pytest -q

"$PY" -m scripts.pilot_writer_admission_pair_comparison \
  --participants 30 --workers 5 --simulations 240 --repetitions 3 \
  > "$HOME/ijcai_fifo_pair_30_240.json"
```

This performs **six independent full three-visit rehearsals**, alternating native→FIFO, FIFO→native, native→FIFO. Each creates its own SQLite file and deletes it afterwards. Compare the medians across run-specific p50/p95/p99/max, the per-arm latency tails, actions over 1 second, and wall time. Also inspect `fifo_wait_latency_ms` versus `sqlite_entry_latency_ms`. Do not infer exact causal effects without repeated comparable WSL system conditions and intervention random seeds.

Expected full WSL tests: baseline **1,383 + five new tests = 1,388**, *unverified until user runs locally*. GitHub CI does not carry the six external-fixture tests.

**Acceptance criteria for advancing this experiment:** all six complete A/B/C journeys must still pass with 16 pretest + 55 practice + 16 posttest, six proposed fatigue responses, A recovery budget ≤2/visit and zero B/C recovery resources, exact-once replays, and zero errors. The paired empirical p95/p99 and wall-time outcomes will determine whether FIFO merits additional staging research. If no stable improvement, abandon this experiment and retain native DELETE.

## Human study release is separate and remains blocked

The cohort count 90/75, eligibility, validated digital M-VAS, approved 95 questions/32 resources, protocol/SAP, full informed consent, concealed randomization, institution/PI/ethics/DPO approvals, independent web security/WCAG/device/network load, separate privacy-safe hosting and offsite recovery require their own signed GO decisions. A successful synthetic FIFO benchmark does **not** authorize human recruitment. Existing IONOS VPS remains completely unchanged.
