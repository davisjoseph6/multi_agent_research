# Draft statistical analysis plan — IJCAI 2027 randomized feasibility pilot

**Version 0.1 — 2026-11-08; subject to PI/statistician approval. NO RECRUITMENT AUTHORIZED.**
**Companion:** `PILOT_PROTOCOL_DRAFT_20261108.md`, `PILOT_POWER_20261108.md`.
**Freeze rule:** Do not finalize or execute confirmatory inference after inspecting human outcome differences; record pre-registration version, amendments and analysis timestamp.

## Estimands and design question

This proposed study randomizes **individual students** 1:1:1 to:
- A = POMCP adaptive **package including optional recovery resources**;
- B = greedy adaptive question selection without resources;
- C = balanced fixed schedule without resources.

A vs B and A vs C are primary *candidate future definitive RCT contrasts*. The existing intervention is not matched for recovery availability, exposure or time; statements about the isolated POMCP algorithm or "equivalent time" are not causally justified. Primary pilot objective is feasibility, **not a null-hypothesis test of efficacy**. If future trial seeks algorithm-specific effect, protocol needs a matched recovery-resource comparator and revised SAP.

## Sets and denominators

- `screened`: approached potential participants with eligibility evaluation.
- `consented`: documented voluntary research consent and eligibility before allocation.
- `randomized` / intention-to-treat set: every assigned eligible student, analyzed by **original assigned arm** regardless of resource usage, adherence, or withdrawal (subject to legal limits on retained data).
- `completed`: all 3 visits attended and final posttest administered in window (state policy precisely).
- Safety/acceptability set: all participants who received any session intervention.
- Do not replace withdrawals with new "randomized" IDs without formal protocol amendment; if additional recruitment is allowed, report it and stop rules.

## Pilot feasibility endpoints and analysis (primary for pilot)

Describe screened/eligible/consented/randomized counts, time to enroll, 3-visit completion overall and by arm, ability to schedule consecutive sessions 3–5 days apart, instrument completeness across 6 fatigue observations, posttest completeness, exposures delivered, attrition reasons, browser/device errors, and suspected contamination.

Present numerators/denominators and **Wilson 95% confidence intervals** for binomial rates; predeclare precise per-arm and overall denominators. Summarize time-to-completion and outages. Proposed progression conversation: >=80% completed all 3 visits, >=95% posttest capture in completers, zero unauthorized enrollment and zero unresolved critical incidents; these are provisional and need PI approval. Compare to targets descriptively, not significance tests.

## Exploratory learning outcome

Outcome: independently scored 16-question posttest, total correct `Y` (0–16), at end of visit 3. Baseline `X`: 16-question pretest (0–16), collected before allocation/intervention as documented in protocol. Test-form equivalence/ceiling checks required.

For exploratory adjusted estimate, fit `Y_i = beta_0 + beta_B I(arm=B) + beta_C I(arm=C) + beta_X X_i + e_i` with `A` as reference and report:
- adjusted difference A-B = `-beta_B`;
- adjusted difference A-C = `-beta_C`;
- 95% confidence intervals, sample sizes and descriptive score distributions, without pilot efficacy claims.
- ANCOVA on bounded discrete totals is a *working model*. Check residual distribution, ceiling/floor, sensitivity using appropriate binomial/ordinal approaches and prespecified robustness methods in a later definitive SAP.

For a **future powered definitive RCT only**, prespecify the two A-vs-control directional hypotheses, two-sided family-wise error at .05 via Holm correction or conservative two-sided .025 per planned contrast (choose ONE before enrollment); avoid post hoc selecting the better comparator. Allocation and outcome analyst masking where practicable.

## Missingness, attrition and protocol deviations

Pilot report the *pattern and causes* of missing pretest, fatigue readings and posttest, by arm, session and timeline. Do not turn missing scores into zeros or assume completers are exchangeable with all randomized students.

For future confirmatory analysis with missing outcomes, prepare a statistician-approved estimator (e.g., multiple imputation under explicit MAR assumptions using baseline, arm, observed performance, session attendance; compare complete-case, pattern-mixture delta sensitivity and extreme-case bounds). Do not promise that imputation repairs MNAR attrition. Document consent withdrawal handling separately via institutional policy.

Per-protocol/adherent analysis is descriptive/sensitivity only, not primary. No unapproved exclusion after viewing scores.

## Fatigue: proposed six M-VAS assessments

For session s in {1,2,3} define `F_pre,is`, `F_post,is` in 0..100, immediate pre-learning and post-learning; `D_is = F_post,is - F_pre,is` (positive = greater self-reported fatigue). Record scale ID/version, precise anchors, mode (visual 10 cm vs digital input), timestamp, device, missing reason.

Descriptive secondary plan:
- mean/median, dispersion, % missing of pre, post and delta **within each arm and session**;
- overall average within-participant delta across available sessions, with count of sessions used and missingness sensitivity;
- explorative arm-by-session contrasts via mixed-effects or GEE accounting for repeated ratings (participant clustering); analyze baseline fatigue and measured task duration as prespecified descriptive covariates.
- If scientific claim is **"without greater fatigue"**, a *noninferiority margin* in M-VAS points, justified from external evidence, with powered noninferiority design and multiplicity correction is necessary. Absence of statistically significant difference is NOT evidence of noninferiority. The pilot must not claim it establishes no extra fatigue.

Measurement equivalence: Published 10-cm VAS is not automatically identical to a digital 0..100 slider. Explicitly assess mode validity, precision, accessibility, licensing/attribution and response dependence before freezing instrument.

## Additional analyses

Resource offer/render/finish/skip (different process states), duration, safety events and content fidelity are descriptive. Explore individual session-learning trajectories without presenting them as primary efficacy effects. A resource count is not a proxy for resource benefit. Reports must distinguish fictional practice logs from genuine pilot data.

Do not use session-level answers as if independently randomized observations: randomization unit is the **student**, n=90 at most. Device/site effects and differential instructor support must be recorded. Avoid unplanned moderator/subgroup inference in the small pilot.

## Data and reproducibility

Generate analysis from a read-only, de-identified export with audit trail; record signed protocol, analysis code revision, questionnaire/content hashes, time zone, preregistered contrasts, code review, dataset freeze and participant-flow exclusions. Never paste tokens/credentials into reports.

## Sample-size limitation

Target 90 recruited -> expected 75 completers (25/arm) presumes 16.7% attrition, no certainty of achieving 25 within each group. At n=25/arm, with two independent, unadjusted, equal-variance two-sample t comparisons and two-sided alpha=.025, ~80% power requires standardized group difference d≈0.896. For d=.50, power ≈30%. The *exact* ANCOVA power cannot be derived without credible pre-post correlation and residual variance from prior work/pilot. Review `PILOT_POWER_20261108.md`.

## Sources

- CONSORT randomized pilot feasibility extension: https://www.bmj.com/content/355/bmj.i5239
- CONSORT 2025 reporting statement: https://www.bmj.com/content/389/bmj-2024-081123
- ICH E9(R1) estimands overview: https://www.ema.europa.eu/en/ich-e9-statistical-principles-clinical-trials-scientific-guideline
