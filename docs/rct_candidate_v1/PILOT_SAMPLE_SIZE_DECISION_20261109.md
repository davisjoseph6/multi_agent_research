# IJCAI 2027 — prospective student sample-size decision memo

**Prepared:** 2026-11-09 · **Status:** DESIGN CALCULATION ONLY — PI + statistician approval missing. **No human enrollment authorized.**

**Immediate decision: do not yet assert that 90 students is the final required n.** Decide which of two scientifically different studies we intend to run:

1. **Randomized feasibility pilot (current draft):** Can we recruit, randomize, deliver three supervised visits, collect six proposed fatigue responses and 16-item posttest scores, retain participants, and operate the platform safely? Size is justified primarily by feasibility objectives, precision and practical delivery. Efficacy hypothesis testing is not the pilot's primary purpose; do not claim that absence of significance means equal learning or fatigue.
2. **Definitive/confirmatory efficacy RCT:** Is Arm A's *POMCP + optional recovery* package superior to B greedy and/or C balanced fixed schedule? Size must be powered for the precise primary effect, adjusted analysis/variance, planned two contrasts and missingness. The present 90/75 target does **not** demonstrate conventional 80% power for moderate effects. A separate fatigue noninferiority claim would require its own justified margin and powered analysis.

CONSORT 2016 pilot/feasibility guidance calls for a rationale tied to feasibility objectives, and generally advises against formal efficacy hypothesis tests in feasibility pilots. The 2025 BMJ pilot sample-size tutorial describes precision-based planning for proportions and progression thresholds. Sources:
- https://www.bmj.com/content/355/bmj.i5239
- https://www.bmj.com/content/390/bmj-2024-083405

## Proposed 90 enrolled / 75 completers

**Design assumptions (not observed outcomes):** Individual 1:1:1 allocation, exactly 30 assigned in each arm; every participant independently completes with common probability `p = 5/6 = 83.333...%`; target at least 25 complete **in each arm**. No within-classroom/site correlation, arm differences or attendance scheduling correlations are represented in this simple binomial model.

| Hypothetical measure | At 90 enrolled |
|---|---:|
| Assigned per arm | 30 |
| Expected completers per arm | 25 |
| Expected total completers | 75 |
| Chance at least 25 complete in **one particular arm** | **61.6%** |
| Chance at least 25 complete in **all three arms** | **23.4%** |
| Chance at least 75 complete in total (even if arms unequal) | **56.8%** |

The **23.4%** finding matters: `75 expected overall` does not justify promising `25 completing in each group`. Actual retention may be lower, correlated or different between arms; these modeled probabilities are illustrative, not guarantees.

If exactly 75/90 completed in an actual study, the hypothetical **overall** Wilson 95% interval for the completion rate would be **74.31%–89.63%**. If exactly 25/30 completed in one arm, its interval would be **66.44%–92.66%**. Thus precision is much weaker for arm-by-arm retention, and the study size should be assessed against the *feasibility* questions we need to answer. The intervals in this memo are **prospective examples, not actual pilot results**.

### Illustrative enrollment assurance (not the adopted sample size)

If the equal independent 83.3%-completion model is correct, an illustrative quota to attain **at least 25 completers in each of A/B/C** with:

| Desired model probability for all three arms | Minimum assigned per arm | Total assigned |
|---|---:|---:|
| 80% | 34 | 102 |
| 90% | 35 | 105 |
| 95% | 36 | 108 |

These are **assurance scenarios**, not recommended final n, and depend strongly on assumed completion probability. They do not address whether the study's feasibility precision, operational capacity, scientific questions or ethical risk justify the number. Recruitment quota must be justified and preapproved independently.

## Preliminary efficacy sensitivity already implemented

The existing `scripts/pilot_power_analysis.py` uses exact noncentral-t power for an **unadjusted** equal-variance two-sample model. Planned A vs B and A vs C comparisons use a conservative Bonferroni two-sided `alpha=0.025` each (two-contrast family alpha 0.05). With 25 completers per arm:

| Standardized mean difference d | Approx. power | Completers per arm for 80% | Recruits total at 83.3% completion |
|---|---:|---:|---:|
| 0.3 | 11.4% | 213 | 768 |
| 0.4 | 19.4% | 121 | 438 |
| 0.5 | **30.2%** | **78** | **282** |
| 0.6 | 43.0% | 55 | 198 |
| 0.8 | 69.6% | 31 | 114 |
| 0.9 | 80.4% | 25 | 90 |

Detectable standardized effect at 80% power with 25 per arm: **d ≈ 0.896**. These figures are sensitivity scenarios, **not final ANCOVA/posttest/fatigue power**. In particular:
- The intended final outcome is 0–16 correct on an independent posttest, potentially adjusted for baseline pretest. We need evidence-backed within-arm SD, pre-post correlation, ceiling/floor effects and minimum meaningful difference measured in **number of correct questions**, rather than choosing an arbitrary Cohen d.
- Assumptions of independence may fail if recruitment or outcomes correlate within classroom/instructor/site; repeated six fatigue measurements are not six independent participants. Students, not question or session observations, are randomized.
- Multiple comparisons, missing-data strategy, attrition, noninferiority (if claimed), and Arm A's extra recovery-resource exposure must be incorporated in the approved estimand and its power calculation.
- If we retain a feasibility pilot, the 90/75 assumption can be documented as a proposed **recruitment and feasibility precision** target rather than pretending a confirmatory efficacy threshold has been met.

## Required PI/statistician decisions before recruitment

- [ ] Choose feasibility pilot vs definitive efficacy RCT and record precise primary objective in the protocol and SAP.
- [ ] Approve candidate three-arm intervention contrast; Arm A is a **package** (POMCP + resources), not just isolated POMCP, and may differ in time-on-task.
- [ ] For feasibility: approve primary parameter(s), precision targets, the thresholds for progress/amend/stop, denominator, expected recruitment per week, attendance capacity and attrition estimates; decide how much per-arm retention precision is needed.
- [ ] For definitive efficacy: choose meaningful difference in 0–16 posttest score **from external evidence**, estimate SD and baseline correlation from compatible sources or blinded feasibility data, confirm outcome/model, two-contrast multiplicity, dropout and design effects. Simulate frozen analysis/score distribution, if necessary, instead of blindly transplanting noncentral-t power.
- [ ] Decide whether additional sample size is justified to ensure at least 25 in **all** arms, not merely 75 on average. Document feasibility and ethical/resource budget.
- [ ] Approve exact eligibility (including novices without prior formal behavioral-economics coursework), three supervised sessions 3–5 calendar days apart, language(s), site, staff and schedule.
- [ ] Independently approve the proposed M-VAS wording/anchors and scoring; power a **separate** fatigue noninferiority margin if that claim is made.
- [ ] Freeze source and analysis revision, the signed statistical memo, protocol/SAP, registration/amendment decisions and sponsor authorization *before any real outcome inspection/enrollment*.

## Reproducible, non-invasive calculations

From `agent2_realdata_benchmark` on the isolated **sample-size** review branch:

```bash
PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m scripts.pilot_power_analysis
"$PY" -m scripts.pilot_sample_size_justification \
  > "$HOME/ijcai_pilot_sample_size_prospective.json"
"$PY" -m json.tool "$HOME/ijcai_pilot_sample_size_prospective.json"
"$PY" -m pytest -q tests/test_pilot_power_analysis.py tests/test_pilot_sample_size_justification.py
```

These scripts read no candidate database, no human data and no VPS secrets. Every output includes `human_enrollment_authorized=false` and `sample_size_approved=false`. The independent research release remains blocked at 0/14 evidence gates until genuine institutional review, PI and statistician signoff.

**Relationship to performance work:** This standalone statistical branch starts at previously locally verified `13ed3b1`; it intentionally does **not** include the later optimistic SQLite-lock experiment (draft PR #10), which passed functionality but regressed p95/p99 timing in the operator's single local comparison. No server/VPS changes are made.
