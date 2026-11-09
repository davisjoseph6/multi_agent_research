# Three-arm, three-visit synthetic parallel study rehearsal

**2026-11-09 — Software rehearsal only. NO REAL STUDENTS.**

This branch introduces a reproducible, disposable SQLite parallel test of **all three** proposed visits in **each** of the three arms, extending prior experiments that measured only the first visit.

## Exact fictional scenario

- Create `N` independent fictional participant IDs, balanced 1:1:1 across A POMCP+recovery, B greedy question-only and C fixed question-only.
- Each participant completes visits 1, 2 and 3 concurrently with other fictional participants, with virtual **4-day spacing between visit starts** (chosen to satisfy the draft 72–120h gap between prior visit finish and next start).
- In every completed three-visit journey: exactly **16 pretest MCQs**, **55 unique practice MCQs** delivered 20/20/15, **16 posttest MCQs**, **six proposed 0–100 pre/post fatigue responses**, optional A resources limited to two per visit, and **zero** B/C recovery resources.
- The local runner submits scripted synthetic answers, does periodic duplicate-request replays with the **same** immutable request ID/payload, verifies the replay is accepted without applying an answer twice, and checks participant-level stage and scoring invariants after every visit.
- All records exist in a system temporary directory and are removed at completion; no tokens, identities, consent, public listener, external host, VPS service, real enrollment or actual scheduling.
- Returns JSON with arm counts, completed visits, response totals, max/p50/p95/p99 action timings and failure classifications. Benchmarks do **not** establish a production SLO.

## Commands

In the new isolated review worktree:

```bash
PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q tests/test_pilot_full_journey_rehearsal.py
"$PY" -m scripts.pilot_full_journey_rehearsal --participants 9 --workers 3 --simulations 41 \
  > "$HOME/ijcai_three_visit_9_synthetic.json"
```

After the nine-person result is verified, on an idle WSL machine, separately try 30 fictional participants:

```bash
"$PY" -m scripts.pilot_full_journey_rehearsal --participants 30 --workers 5 --simulations 240 \
  > "$HOME/ijcai_three_visit_30_240_synthetic.json"
```

A proposed 90-person concurrency experiment is **optional and local only**; confirm suitable CPU/RAM/temperature and approve an explicit abort threshold before increasing to `--participants 90`. Ninety recruited students does not mean 90 simultaneously active. This local experiment is not equivalent to external TLS load, real device/browser performance or supervised participation.

## Acceptance evidence and exceptions

**The two new tests and synthetic CLI are not yet WSL-verified at authoring time.** The parent branch's full WSL tests also await verification. Preserve exact tested commit SHA, frozen local ASSIST2009 artifacts, results, code hashes, CPU/RAM metrics and run conditions for reproducibility. Do not merge experimental read-transaction optimizations without repeated performance comparisons and no regressions.

The current preview's questionnaire, behavioral-economics content, consent mechanism, staff identity, authorization, session scheduler and privacy controls are **not** approved or usable with real students. This is not a surrogate for the 14 required pilot release evidence gates, independent WCAG/security testing, legal institutional consent or statistical decisions.
