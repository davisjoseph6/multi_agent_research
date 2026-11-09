# Synthetic-only SQLite status/scoring lock isolation — experimental hardening

**2026-11-09. DRAFT. NOT AUTHORIZED FOR STUDENTS OR VPS DEPLOYMENT.**

### Motivation

At the locally verified parent `13ed3b1`, first-visit 30-fictional-person runs at 41 and 240 POMCP simulations **both functionally passed** but showed multi-second p99/max outliers. Diagnostics showed action delays occurred primarily while acquiring `BEGIN IMMEDIATE` SQLite transactions. The subsequent optimistic off-lock planner experiment in PR #10 passed all functional tests, but user-reported p95/p99 got **worse**. **Do not merge PR #10 or claim that optimization succeeded.**

The original database store opened **global writer transactions for read-only operations**, including `snapshot()`, `scores()` and `audit_arms()`. A parallel synthetic load repeatedly calls these methods. In SQLite, `BEGIN IMMEDIATE` claims a RESERVED write lock; read-only status requests should not have to compete for that writer position.

### This isolated change

- Retain **all** mutating operations, action planners and exactly-once submission code *unchanged* from the locally validated sample-size branch `9f35d40`.
- Introduce a SQLite `mode=ro`/`query_only=ON` read transaction for synthetic-only reporting, under `BEGIN` consistent snapshot.
- Use it in base `SyntheticPilotStore.snapshot` and `scores`, and `SyntheticThreeArmPilotStore.audit_arms`.
- Consolidate the three-arm `snapshot` into **one consistent read-only transaction** that returns the same documented fields and cannot mix participant state with the policy from a later commit.
- This branch changes source fingerprints by design; **do not reuse the earlier synthetic browser acceptance database or the running fictional VPS**.
- Regression tests cover query-only write rejection, reader availability while an unrelated client holds `BEGIN IMMEDIATE`, unchanged synthetic scoring/status fields, and refusal to use `_transaction` during a pure read.

**Critical limitation:** SQLite readers still acquire SHARED locks in rollback-journal mode and may conflict with a writer's commit. WAL mode, journal configuration, filesystem latency, concurrent CPU and worker processes need separate analysis. This is a *candidate change*, not guaranteed p99 improvement.

### Required WSL evidence

From a **new detached worktree** of this branch, with the same frozen local ASSIST2009 and external reference files copied as usual:

```bash
PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q tests/test_pilot_readonly_sqlite_isolation.py tests/test_pilot_concurrency_rehearsal.py tests/test_pilot_three_arm_store_draft.py
"$PY" -m pytest -q
"$PY" -m scripts.pilot_concurrency_rehearsal --participants 30 --workers 5 --simulations 41 > "$HOME/ijcai_readonly_load41.json"
"$PY" -m scripts.pilot_concurrency_rehearsal --participants 30 --workers 5 --simulations 240 > "$HOME/ijcai_readonly_load240.json"
```

Expected full suite count from prior 1,370 + 5 = **1,375** (unverified until WSL). Compare all phases, per-arm latencies, >1-second count and max to parent **under comparable host load**, with multiple repeated runs, keeping results and source hashes private. If worse, revert/keep this PR draft; do not release.

### Release boundaries

The browser and DB remain **fictional-only**. The 14-gate release evidence index remains 0/14 approvals. No external human-data deployment, identity, institutional approval, ethics, consent or final sample-size decision is implemented here. All changes are independent of the older PR #10 optimistic-planning branch, which has a measured latency regression.
