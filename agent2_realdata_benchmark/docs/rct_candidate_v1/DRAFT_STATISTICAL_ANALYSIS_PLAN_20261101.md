# STATISTICAL ANALYSIS PLAN (SAP) v0.1 — DRAFT / NO-GO
**Date:** 2026-11-01
**Related protocol:** `DRAFT_RESEARCH_PROTOCOL_20261101.md`
**Status:** Proposals only. No human data, LFS rights, approved instrument, power justification, protocol/ethics approval, or preregistration asserted.

## 0. Confirm pilot or confirmatory design *before* preregistration
- **Confirmatory path (proposed only):** individually randomized 3-arm superiority trial; primary A vs B posttest contrast; A vs C a pre-specified key secondary contrast; B vs C descriptive/exploratory. If two comparisons are intended as *co-primary*, multiplicity control and corresponding power planning are essential.
- **Pilot path:** primary outcome operational feasibility (prespecified proportion finishing all three scheduled sessions and usable posttest; recruitment, retention and instrument-completeness endpoints). Learning contrasts exploratory only, with effect estimates and intervals, not efficacy claims.
- Legacy goal `n=75` (25/arm) is **not** a power calculation. For two independent equal-size groups and an unadjusted two-sided alpha .05 test, 25/arm roughly supports 80% power only for a large standardized mean difference (~0.8); the actual detectable effect depends on baseline adjustment, correlations, missingness and the multiplicity plan. Calculate n prospectively using defensible assumptions and a statistician.

## 1. Study population, allocation and traceability
- Freeze inclusion/exclusion and unit of randomization; planned analysis population is all **randomized eligible consented** individuals analyzed by assigned arm, regardless of adherence (treatment-policy/ITT estimand), subject to prespecified handling of unavailable outcomes.
- Treat withdrawal and legal deletion requests according to institutionally reviewed information/legal basis, not as a statistical convenience.
- Preserve immutable time stamps, source/content hash, assignment and analysis version; fictional rehearsal records are EXCLUDED from all human analyses.
- Validate arm B policy setting and scheduling actual treatment before freezing.

## 2. Proposed primary estimand (confirmatory pathway)
- Population: eligible randomized study participants.
- Treatment: assignment to Arm A versus Arm B, including actual variable resource dose (policy-package effect; NOT isolated effect of POMCP).
- Variable: total score out of 16 on a psychometrically reviewed posttest, administered at prespecified time after session 3.
- Intercurrent events: missing sessions and skipping recovery are retained in assigned arm; noncompletion of posttest handled in a prespecified missing-data strategy; withdrawal/consent handling must comply with approved policy.
- Summary: adjusted mean posttest difference A minus B, with two-sided 95% CI and prespecified test; interpretation restricted to measured learning performance.
- Main estimator *candidate*: ANCOVA / ordinary least-squares model on posttest score: `posttest = intercept + beta_A I(A) + beta_C I(C) + beta_pre * pretest + prespecified baseline covariates + error`. With B as reference, beta_A is A–B; derive A–C by linear contrast. Prespecify HC3 heteroskedasticity-robust SE and the exact number of covariates before seeing outcomes, with a count/binomial or ordinal sensitivity model appropriate to score distribution if warranted.
- **Do not claim a recovered latent mastery state from this score alone.** Predefine a separate objective rule for observed decline and recovery, and handle regression-to-the-mean and selection bias in threshold-triggered subgroups.

## 3. Secondary and exploratory analysis
1. A vs C and B vs C posttest contrasts, with explicit distinction between inferentially protected and exploratory comparisons. Suggested strict gatekeeping: test A–B first at 0.05; only if rejected, test A–C at 0.05. This needs independent statistical review before freeze.
2. Change score (post–pre) is a supporting analysis, not an additional uncontrolled primary endpoint.
3. Prespecified session-specific correct/incorrect response trajectories using repeated-response methods that address within-participant dependence; avoid treating 55 question responses as 55 independent people.
4. Objective exposure metrics: time on task, practice question count, recovery action type/dose/time, skipped resource frequency, dropout; separately report all arm A resources and failures.
5. **LFS if licensed and approved:** fatigue (13 items) and energy (5 items) separately; use validated scoring, anchor direction and missing-item rules from authorized documentation. Present mean and variability by arm/time; repeated measurements may use a predeclared mixed model including baseline and session, or descriptive pilot summaries. Avoid post-treatment mediator adjustment in the *primary* outcome model.
6. Subgroup/moderator analyses (e.g. baseline score, fatigue) exploratory unless separately powered and preregistered, including interaction tests.

## 4. Multiple comparisons and uncertainty
- Primary confirmatory type I error: two-sided alpha 0.05 for A–B only (unless the team chooses a different hierarchy).
- Predefine how A–C, repeated LFS timepoints, other 2-way arm contrasts and individual eight-concept outcomes are handled; report confidence intervals and exact hypotheses.
- Never use uncorrected search over response subsets or POMCP seed trials as confirmatory human evidence.

## 5. Missing data
- Tabulate recruitment, consent, randomization, attended visits, posttest available, withdrawal and reasons by arm.
- Explicitly separate inability to reach, stopped participation and consent-dependent deletions.
- Do not use complete-case-only results as the sole primary inference when missing outcomes could depend on arm/fatigue.
- Recommended candidate: primary multiple-imputation under MAR using pretest, assigned arm, visit history and prespecified auxiliary variables, with imputation model compatible with bounded 0–16 posttest scores, plus complete-case and pattern-mixture/delta-shift MNAR sensitivity analyses. Exact method and plausibility checks require statistician sign-off; if a feasibility trial, describe missingness instead of overclaiming imputation precision.
- Handle missing LFS subscale items using permissioned scoring guide, not an invented complete-case cutoff.

## 6. Data checks and code before unblinding
- One unique pseudonym per consented individual; one allocation record; audited pre/post keys; cross-arm question availability, leakage, event time sanity and idempotent submissions.
- Generate a locked, code-reviewed extraction and versioned analysis script from synthetic blinded records. No manual changing of answer keys or treatment metadata after exposure.
- Blind analyst to arm labels where practicable; document unavoidable limitations.
- Freeze tables, figures, primary model, robustness analyses and multiplicity before primary human outcome inspection.

## 7. Operational boundaries
- Session scheduling: if planned 3–5 days apart, do not equate the local uninterrupted demo with a spaced longitudinal trial.
- Fatigue and learning outcomes are distinct constructs; post-session LFS scores are not a direct sensor of forgetting or mastery loss.
- Arm A may receive six extra resources; treatment dose and total learning time can confound mechanism attribution.
- All consent, licensing, ethics/privacy, content expert review, infrastructure/security and accessibility conditions are outside the statistical analysis and remain independent release blockers.

## 8. Decisions required for v1.0 sign-off
- Pilot vs confirmatory; primary hypothesis; 75 participants target vs justified power.
- Effect-size assumptions, target power, alpha/multiplicity, attrition and design.
- Exact posttest form/scoring/administration; learning items independently validated.
- Authorized LFS version, administration frequency, electronic equivalence, subscale scoring and permissions.
- Sessions spacing, deviations and participant follow-up.
- Statistical software/version, data dictionary, analysis scripts and prespecified missing-data algorithms.
- Sponsor/PI/statistician approvals, ethics and data-governance review, frozen protocol versions and public preregistration.

### References
- SPIRIT 2025 https://doi.org/10.1136/bmj-2024-081477
- CONSORT 2025 https://pmc.ncbi.nlm.nih.gov/articles/PMC11995452/
- OSF preregistration https://help.osf.io/article/330-welcome-to-registrations
- LFS primary validation https://pubmed.ncbi.nlm.nih.gov/2062970/
