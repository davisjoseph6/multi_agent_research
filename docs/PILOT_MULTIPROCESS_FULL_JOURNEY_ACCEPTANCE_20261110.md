# Cross-process full three-visit A/B/C fictional acceptance test

**Prepared 2026-11-10. NEW experimental test only. No real human participants, no public VPS, no recruitment.**

## Why this exists

The operator verified PR #19 head `2800537` with **13/13 new focused tests passing** and **1,396 existing tests passing, 5 fixture-missing setup errors**. The five errors were limited to missing `data/processed/assist2009/interactions.parquet` after creating an isolated Git worktree without copying the two frozen research fixture directories. A full **1,401** passing test result **has not been obtained yet**; restore the frozen ASSIST2009 directories and rerun.

PR #19's new small multi-process DB counter probe passed for both native SQLite and per-process FIFO: **12/12 updates**, `PRAGMA integrity_check=ok`, no errors. FIFO yielded p99 132.025ms vs native 185.877ms in **one small 12-operation sample**. That tests SQLite integrity, **not the complete student workflow**. In both modes the FIFO queues are independent in each process.

## What this independent experiment adds

`src/prototype/pilot_multiprocess_full_journey_rehearsal.py` and CLI `scripts/pilot_multiprocess_full_journey_rehearsal.py` create one disposable SQLite file, populate independent fictional A/B/C participants in the parent, and launch 2–4 real spawned Python processes. Each process constructs its own store instance and invokes the unchanged verified complete-three-visit rehearsal across up to four local threads.

For each fictional student, require:
- three complete virtually spaced supervised visits;
- 16 pretest, 55 unique practice and 16 posttest answers;
- exactly six **proposed, unvalidated** pre/post M-VAS readings;
- bounded A resources, zero B/C recovery, and fixed immutable original arm;
- exactly-once submissions under replay of the identical request ID and payload.

After all subprocesses exit, the parent checks **SQLite integrity**, enrolled-arm counts, persisted unique submission records, aggregate action counts, and no per-arm imbalance; no participant identifiers appear in output.

This still cannot validate **human** consent, eligibility, concealment, staff roles, 3–5-day real-time enforcement, network/HTTP/HTTPS/browser, encryption, production capacity or distributed lock fairness. Independent processes have their own `threading.Condition` FIFO queue, so cross-process FIFO coordination explicitly remains **FALSE**.

## Safe local verification

From an entirely separate worktree of `research/ijcai2027-multiprocess-fulljourney-rehearsal-20261110` and directory `agent2_realdata_benchmark`:

```bash
PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"

"$PY" -m pytest -q tests/test_pilot_multiprocess_full_journey_rehearsal.py

# Restore only the frozen research files from the original checkout,
# as in prior verified worktrees, before the complete regression.
"$PY" -m pytest -q

"$PY" -m scripts.pilot_multiprocess_full_journey_rehearsal \
  --participants 6 --processes 2 --threads 2 --simulations 41 --mode native \
  > "$HOME/ijcai_multiprocess_journey_native.json"

"$PY" -m scripts.pilot_multiprocess_full_journey_rehearsal \
  --participants 6 --processes 2 --threads 2 --simulations 41 --mode fifo \
  > "$HOME/ijcai_multiprocess_journey_fifo.json"
```

**New tests: 3**. Prior PR #19 had **1,401 expected full WSL tests** (pending after restoring the five frozen-split tests). This branch expects **1,404** only if its tests and all fixture-dependent tests actually pass. GitHub Actions excludes the six external-fixture tests by design.

If both six-person runs pass, optionally test 30 fictional people / 240 simulations / 2 processes / 2 threads after reviewing machine load. This still is not an HTTPS load certification.

## Scientific and institutional blockers unaffected

Original supervisor's NASA-TLX-like six post-session items vs current M-VAS pre/post require PI/measurement signoff, along with BKT/recovery/POMCP taxonomy, 90/75 feasibility sample-size, 95-item/32-resource reviewer content, treatment contrasts and concealed assignment. A new human-eligible system has not yet been approved. Responsible institution/PI, ethics, DPO, consent and all 14 evidence gates remain unapproved. The IONOS operator-only fictional demo is unchanged.
