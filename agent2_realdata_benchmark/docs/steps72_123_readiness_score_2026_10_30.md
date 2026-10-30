# Steps 72–123: evidence-weighted readiness review

**Date:** 2026-10-30. **Study release:** NO-GO.

## Transparent working-score convention

This is a **provisional task-equivalent progress score**, not scientific validity, effectiveness, chance of publication, or time remaining. All steps are equally weighted (a limitation).

- `SYNTHETIC-IMPLEMENTED`: 1.0 credit — tested synthetic software function only, not necessarily full scientific closure.
- `PARTIAL`: 0.5 credit — useful work but acceptance criterion unsatisfied.
- `EXTERNAL-REQUIRED`: 0 credit — no sufficient external evidence.
- `NOT-PROVEN`: 0 credit.

Based on the source V3 step-level audit, with Step 93 moved from NOT-PROVEN to PARTIAL because of the exact audit/counterexample work (not because any guarantee is proven for the controller). The later V5 development advances **Step 95** but does not close it, so no other statuses are upgraded.

| Status | Steps | Credit per step | Points |
|---|---:|---:|---:|
| SYNTHETIC-IMPLEMENTED | 19 | 1.0 | 19 |
| PARTIAL | 20 | 0.5 | 10.0 |
| EXTERNAL-REQUIRED | 13 | 0 | 0 |

**Task-equivalent score: 55.8% = 29 / 52.**

Caution: This is an **optimistic engineering-inclusive score**. Counting synthetic-implemented steps as complete does not mean that 55.8% of the RCT's human-study validity, approvals, statistical power or recruitment is done. No such scientifically meaningful single percentage can currently be assigned.

## Evidence updates as of 2026-10-30

- User verified 770/770 local tests and 12/12 focused V5 tests.
- 52 paired V3/V5 *decision cases*: 33 V3 zero-gain, 29 guard interventions, 4 V5 zero-gain (all-believed-mastered cases).
- Three-participant V5 synthetic mock: 58 planner decisions, **zero** guard interventions.
- The latter means the guard's intervention relevance in the actual study configuration remains uncertain.
- A verified V3 statewise drift counterexample blocks a universal drift guarantee.
- No external subject-matter item-review signoffs, pilot reliability dataset, model calibration, formal sponsor/ethics decisions or final content freeze have been presented.

## The shortest critical path to genuine completion

1. Supervisor/research sponsor decides which policy A actually is (rule-based, V3 POMCP or V5 guarded hybrid), confirms A vs B primary hypothesis, ITT endpoint, expected dose and planned analyses.
2. Human author(s) create 95 real **non-synthetic** item drafts in `step96_106_authorship_slots.csv` (16 pre, 16 post, 55 practice, 8 DROP_2) and 32 substantive recovery resources in `step104_recovery_resource_slots.csv`.
3. Qualified subject-matter experts independently review and document amendments and signed item-level decisions. Separate pilot participants and measurement specialists assess score validity and reliability.
4. Calibrate/sensitivity-test the eight-concept response/transition model; predeclare planner/fallback and budget; audit true-state vs belief-state assumptions and matched dosages.
5. Production security/consent/privacy/workflows; institutional research approval determination; then final independent mock run using frozen real materials. Human enrollment only after appropriate authorization.

**External dependencies cannot be closed by marking a CSV cell as reviewed.** For French personal-data research, engage the institutional DPO and owner of the study; exact legal/ethics pathway depends on population, data and sponsor.

The detailed, step-specific acceptance criterion and owner appear in `steps72_123_closure_register.csv`.
