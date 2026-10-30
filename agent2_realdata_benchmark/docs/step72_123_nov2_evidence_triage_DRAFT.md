# IJCAI 2027: October 30–November 2 evidence triage (DRAFT)

**Source:** Researcher's read-only audits and Git/test logs provided October 30, 2026. **This memo does not certify a completion percentage.**

## What has actually been shown

- `feature/ijcai2027_prototype` commit `4b6626ccebffc82810358895787745354e982182` passed 1,029 project tests in WSL.
- The two-state Bayesian forgetting filter passed 102 additional local parity tests and compared with an exact hidden-path oracle; displayed maximum discrepancy 2.220446049250313e-15 on diagnostic examples.
- `step72_123_progress.py` reported 19 synthetic-implemented, 20 partial, 13 external-required, totaling 29.0/52 = **55.8% provisional rubric credit**.
- The educational content checker **correctly failed closed**, with exit code 1, 1,142 issues, `expert_review_verified=false`, `psychometric_validation_verified=false`, and `authorized_for_human_study=false`.
- Example issues include blank learning objectives, question prompts, rationales and citations; missing answer options/keys and invalid difficulty; and absent independent review records and dates.
- The printed 33 incomplete steps all showed `independent_signoff=NOT RECEIVED`. This does not establish the status of rows not printed.
- Untracked local archives and draft files must not accidentally enter a paper artifact or Git commit; use explicit `git add` paths.

## Work that is internally actionable before Monday

| Priority | Steps | Deliverable that can honestly be produced | Closure distinction |
|---|---|---|---|
| P0 | 72, 73, 78, 88 | Contract matrix for all A/B/C variants; action, time, observation, intervention and tie-breaking trace tests; formal pseudocode | Requires independent review of exact shipped implementations; a draft is not signoff |
| P0 | 79, 83, 86, 93–95 | Posterior calibration and misspecification report; explicit deterioration target; counterexamples; matched-dose and no-recovery ablations; runtime/cost | Do not claim posterior = true forgetting; published HMM/BKT mathematics alone is not novelty |
| P0 | 80, 103 | Freeze proposal, source hashes, data sources, assessment leakage and separation checks | Do not freeze an incomplete/unapproved content bank as though approved |
| P1 | 96–97, 99–100, 104 | Genuine drafts of 95 content-item slots and 32 recovery-resource slots, complete sources and reviewer instructions | Keep `DRAFT` review status; authentic expert evaluation remains absent |
| P1 | 106, 117, 119–120, 122 | Dry-run user interface, reboot/resume, multi-client concurrency, audit log integrity, privacy and security issue ledger | Independent accessibility/security review and host validation remain open |
| External | 75–77, 81, 85, 98, 101–102, 105, 118, 121 | Requests, drafted protocol, reviewer decisions and evidence to be delivered to responsible people | Approval, real pilot data, psychometrics, ethics/data protection cannot be fabricated |

## Scientific stop/go rules

- V5 and V3 produced identical executed decisions in 825 decision opportunities in the three development scenarios described; preserve this negative result.
- In the subsequent V6 100-seed development ablations, the incremental advantage of V6's recovery over the same practice-selection controller with recovery disabled was approximately zero and sometimes negative. Do not claim the recovery mechanism has been shown effective.
- An observation-only `CCWW` alert can be produced without latent forgetting, and the exact Bayesian filter's probabilities are conditioned on assumed learning, forgetting, slip and guess parameters.
- Do **not** unlock held-out seeds starting at 200000 merely because the weekend has ended. A candidate contribution, all primary metrics and analysis plan must be justified and frozen first.
- Do not write a global recovery guarantee from a mathematical claim already refuted by a counterexample.
- Paper claims must be checked against relevant prior work on BKT/forgetting, POMDP teaching, POMCP and budgeted interventions. A novelty argument must be technical and specific.

## The next precise inventory commands

From inside `agent2_realdata_benchmark`:

```bash
# Find actual CSV input schema and hardcoded defaults (read-only).
grep -nE '(default=|csv\.|DictReader|fieldnames|items|resources|review)' scripts/step96_106_content_audit.py | head -n 100

# Locate educational CSVs in your current checkout.
find . -type f \( -iname '*item*.csv' -o -iname '*resource*.csv' -o -iname '*blueprint*.csv' \) -print | sort

# Read-only snapshot. The content checker is expected to exit nonzero while drafts are incomplete.
PYTHONDONTWRITEBYTECODE=1 python3 -m scripts.step72_123_weekend_triage \
  --output /tmp/ijcai_weekend_evidence.md \
  --json-output /tmp/ijcai_weekend_evidence.json

sed -n '1,120p' /tmp/ijcai_weekend_evidence.md
```

Once paths and schemas are known, create a content *authoring* plan with distinct responsibilities; do not insert invented approvals into required columns. Keep draft authoring files separate from the original review-frozen bank.

## Monday November 2 deliverables

1. A full 52-step evidence register with checksums, exact criteria, no retroactive status inflation, and an explicit owner for every unresolved requirement.
2. An authentic, structurally inspected educational draft bundle and a reviewer request package, clearly marked **not released**.
3. Rigorous and reproducible synthetic model/counterexample/fairness analysis with favorable **and unfavorable** results; independently reviewed claims where available.
4. A human-study gate and privacy/ethics issue register that forbids recruitment or live use without authorization.
5. A main-track paper contribution decision and the next scientifically appropriate experiment; or an explicit **NO GO** if novelty/causal benefit cannot be defended.

**Progress rule:** Existing 55.8% may be changed *only* after a step's exact exit criterion is evidenced; completion of a script or a draft document alone is not sufficient.
