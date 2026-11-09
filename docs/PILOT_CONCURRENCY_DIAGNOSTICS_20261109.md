# Synthetic concurrency tail diagnostic: release-blocking engineering investigation

**2026-11-09. FICTIONAL DATA / LOCAL SQLITE ONLY / NO HUMAN ENROLLMENT.**

## Observed first local run (user-reported at commit 3ed2cec)

- 30 fictional first-visit participants; A/B/C 10 each; five worker threads; **41** POMCP simulations.
- 1,160 synthetic completed action roundtrips, 13.45 seconds, no failures.
- p50 9.784 ms, p95 16.865 ms, **p99 1,340.227 ms**, maximum **7,177.206 ms**.
- Result was PASS for functional completion, **not** an approved latency service objective. This tail is worth investigating before a real pilot.

## Instrumentation in this branch

The disposable local concurrency harness now reports:
- Per-arm p50/p95/p99/max; how many actions exceeded observational 250 ms/1,000 ms thresholds (not an approved SLO).
- Phase p50/p95/p99/max across `next_action`, `mark_rendered`, `submit`.
- **Thread-local SQLite transaction-entry time** inside the unchanged `BEGIN IMMEDIATE` context, separately for next/render/submit, without changing production or synthetic study DB code.
- Ten slowest synthetic actions by arm, stage, action type and phase, **without participant IDs**.
- No HTTP/device/server/VPS access; default low-simulation preview is still not an actual 240-simulation capacity test.

**Interpretation:** SQLite acquisition timing includes opening a connection, PRAGMAs and possible `BEGIN IMMEDIATE` wait. It is **not a direct database busy-wait measurement**. `next_ms` also includes computational planning and database work. If `next_ms` is large but `sqlite_begin_next_ms` is small, planning and SQL work warrant investigation. If `sqlite_begin_next_ms` is large, serialized write-lock contention is implicated. Work remains to distinguish process scheduling/GIL from real contention, and measure independent worker processes and HTTP workload.

## Run without touching the real VPS

From this branch's isolated WSL worktree under `agent2_realdata_benchmark`:

```bash
PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q tests/test_pilot_concurrency_rehearsal.py
"$PY" -m scripts.pilot_concurrency_rehearsal \
  --participants 30 --workers 5 --simulations 41 \
  > "$HOME/ijcai_synthetic_load30_diagnostic.json"
"$PY" -m json.tool "$HOME/ijcai_synthetic_load30_diagnostic.json"
```

Once the 30-person run passes, run an explicit second **local** scenario with the intended 240 simulations:

```bash
"$PY" -m scripts.pilot_concurrency_rehearsal \
  --participants 30 --workers 5 --simulations 240 \
  > "$HOME/ijcai_synthetic_load30_240.json"
```

This may substantially increase the CPU and lock contention. **Do not** run against a real participant DB, on the public VPS or while resource-intensive production jobs share the same host. Review p99/max and phase attribution before approving more concurrent requests or a 90-person scenario.

## Future release acceptance after investigation

- PI/engineering team agree actual peak concurrency, network and response time SLOs before production tests.
- Test full 3-visit journeys, not only first visit; run for 30 and possibly 90 simultaneous fictional participants as a separate test schedule.
- Run on dedicated staging with 240 planner simulations, realistic devices and HTTPS, faults/restarts, CPU/RAM/DB-lock metrics, anti-replay isolation, and offsite encrypted backups.
- If performance is inadequate, review transaction design (planning currently occurs under SQLite `BEGIN IMMEDIATE`) **without sacrificing exactly-once semantics, action replays and randomized arm integrity**. Any optimization requires independent behavior-equivalence and race-condition tests.
- Maintain versioned code hashes, results and independent QA signoff; do not infer human-study authorization from any local test.

The 14-gate release-evidence public manifest remains pending and human enrollment remains prohibited.
