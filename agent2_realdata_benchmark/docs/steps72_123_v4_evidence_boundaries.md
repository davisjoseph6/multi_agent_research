# IJCAI 2027 — Steps 72–123: Evidence boundaries after V4

## What is actually established

The v3 synthetic runtime exercises eight concept states and a POMCP-style
candidate in Group A. Its full browser suite passed 720 tests in the user's
WSL on 29 October 2026. This does not establish a validated educational
model, a mathematical guarantee, or any human treatment effect.

V4 adds a **separate read-only SQLite integrity checker**, independent of the
study runtime implementation. It verifies participant-local ordered events,
normal practice and assessment counts, fatigue records, action/result pairs,
per-session resource caps, versioned item-bank hashes, committed response
counts, all three study arms, and completed states. It also runs adversarial
corruption tests. Its synthetic mock leaves an audit database on disk for
repeat verification; it refuses to overwrite an existing one.

The V3 schema retains a pending `COMPLETE` action after the final read of
`next_action`. That is a terminal display token, not an unsubmitted research
response. V4 explicitly recognizes this documented behavior, but rejects
pending nonterminal actions in otherwise completed sessions.

## What V4 does not establish

The audit does not detect a malicious rewrite that keeps all records mutually
consistent, and does not provide cryptographically attested provenance or
trustworthy timestamps. It cannot establish informed consent, real participant
identity, actual human actions, causal learning gains, missing-outcome
strategies, validated instrument scores, calibrated model transition rates,
or validity of a paper's theorem.

The 52-step V3 audit currently classifies 19 steps as SYNTHETIC-IMPLEMENTED,
19 as PARTIAL, 13 as EXTERNAL-REQUIRED and 1 as NOT-PROVEN. This V4 checker
improves independent synthetic verification of Steps 120–123; it does not
convert partial or external-required items into fully completed research work.

## Blocking deliverables before genuine completion

1. A supervisor/statistician-approved formal intervention and outcome protocol.
2. Subject-matter-reviewed Behavioral Economics bank and recovery resources,
   with independent assessment forms and item provenance.
3. Empirical calibration, test reliability, item quality and transfer/retention
   measurement using appropriately authorized real data.
4. Independent verification or revision of all mathematical recovery claims.
5. Actual study-grade secure, accessible and privacy-reviewed production system.
6. Any required institutional approval, DPO review and consent procedures.

Do not create records marked `expert_reviewed` without independent review;
do not infer effect sizes or psychometric properties from fictional participants.

## Commands

From `agent2_realdata_benchmark` with the project virtual environment active:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider tests/test_step123_v4_independent_audit.py
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 python -m scripts.step123_v4_audited_mock --database results/step123_v4_audit.sqlite3 --simulations 24
PYTHONDONTWRITEBYTECODE=1 python -m scripts.step123_v4_independent_audit results/step123_v4_audit.sqlite3
```

The expected full-suite total is **729** if the prior WSL baseline remains
720 and all nine V4 tests are discovered. This is a prediction, not a claimed
result for the user's machine. Use a different filename on repeat mock runs.
Keep synthetic data files out of Git. Nothing here authorizes recruitment.
