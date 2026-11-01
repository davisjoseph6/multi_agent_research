# RESEARCH PROTOCOL v0.1 — DRAFT, NOT APPROVED, NOT REGISTERED
**Date:** 2026-11-01  
**Study:** Self-healing adaptive quizzes via belief-space modular decision architecture  
**Status:** Discussion document for principal investigator, supervisor, statistician, educational-measurement reviewer, institutional ethics/privacy teams. **NOT a participant-facing release document.**

## 1. Objective and design
Candidate: individually randomized, parallel-group, three-arm, educational-methods study.
- A: adaptive belief-space POMCP controller that can select questions and at most two recovery resources per practice session (summary, two-option remediation, worked example, static Socratic-style guided prompt).
- B: comparator greedy question selection under the currently frozen candidate configuration; verify the exact control setting and version rather than inferring from arm name.
- C: pre-specified fixed balanced question sequence, with no adaptive resources.
- All arms: same 16-item pretest and 16-item posttest architecture, 55 practice questions arranged 20/20/15; three assessment intervals.
- **Dose confounding warning:** A may receive up to six extra resources relative to B/C. A superiority finding alone does not isolate the effect of policy adaptation from exposure/dose. Pre-specify resource counts, duration, resource uptake, and an explicitly exploratory matched-dose ablation; equal-dose comparisons need their own validated treatment implementation.

## 2. Study classification (unresolved)
- Decide whether this is a **feasibility/pilot RCT** or a **confirmatory efficacy RCT**. A legacy target of 75 completers / 25 per arm is a recruitment planning assumption, NOT a justified sample size or power calculation.
- The supervisory design described three sessions separated by 3–5 days, roughly 45 minutes/session. **Current browser rehearsals are continuous and do not enforce those gaps; this discrepancy is a release blocker if spacing is retained.**
- Confirm recruitment site, sponsor and legal data controller, principal investigator, data protection officer, ethics-review route, inclusion/exclusion criteria (including prior behavioral economics education), participant age and any incentives. Do not recruit until all applicable approvals are obtained.
- Confirm which paper's scientific question is tested: comparative posttest learning vs a rigorously operationalized degradation/recovery effect. No claim of real mastery restoration can be supported from planner-belief trajectories alone.

## 3. Outcomes — proposed, not frozen
**Suggested primary efficacy endpoint if a confirmatory design is approved:** 16-item posttest score (0–16) after learning session 3, compared between A and B with adjustment for 16-item baseline pretest score. Higher = better. Confirm equivalent test difficulty, construct coverage, item discrimination, test-retest overlap and expert answer-key validity BEFORE outcome freeze.
**Suggested secondary endpoints:** A vs C posttest, B vs C, assessment completion and time burden, arm-specific resource counts and timing, repeated session errors, proportion of recoveries (strictly operationalized in advance), and Lee Fatigue Scale fatigue/energy scores. Distinguish measurement of *observed knowledge performance* from latent BKT estimates.
**If pilot is selected:** set feasibility/recruitment/retention/data completeness as primary; treat efficacy contrasts as exploratory with uncertainty intervals. Do not relabel exploratory estimates as confirmatory afterward.

## 4. Lee Fatigue Scale / VAS-F — FIRST CANDIDATE, NOT LICENSED OR INTEGRATED
- Original: Lee, Hicks and Nino-Murcia (1991), *Validity and reliability of a scale to assess fatigue*, Psychiatry Research 36:291–298, https://doi.org/10.1016/0165-1781(91)90027-M.
- Original instrument is 18 items (13 fatigue; 5 energy) with a 100 mm visual analogue format and current-state ("right now") rating. Later versions/studies use numeric scales; do not assume electronic 0–10 or 0–100 alternatives are psychometrically interchangeable.
- Copyright: publication of a reproduction states “Copyright © KA Lee 1992” and prohibits copying without written consent. **Obtain and archive documented permission that explicitly covers electronic web administration, requested language, scoring, any modification and planned population; do not copy items into repository or public preview until permission confirmed.**
- Obtain authorized instrument and scoring instructions; freeze fatigue/energy subscale scoring, direction, missing item rules, digital interface geometry/keyboard accessibility, language, device equivalence and timestamp of rating. Do not use unvalidated morning/evening clinical cutoffs for this student sample.
- **Assessment-frequency decision required:** (A) baseline before first practice + after each session (4 administrations × 18 = 72 ratings) for longitudinal end-state fatigue; (B) before and after each of 3 sessions (6 × 18 = 108 ratings) for within-session change, subject to tolerability review. Existing six-item five-point rehearsal questionnaires cannot be represented as LFS. Higher burden needs an initial cognitive usability/measurement pilot with separate approval as applicable.
- Fatigue as measured by LFS is a possible endpoint/covariate or moderator, **not** an automatically validated indicator of cognitive degradation or proof of self-healing. Any fatigue-derived policy switching would change the intervention and require new validation/versioning.

## 5. Randomization, concealment and conduct
- Audit code for randomized block sizes, ratios and enrollment timing; freeze algorithm and verify concealment of arm assignment from participant-facing UI. Record immutable allocation version/hash and baseline covariates (only approved ones).
- Document participant-facing information, withdrawal policy, adverse-event/discomfort reporting, unequal intervention dose, limits of blinding, support contacts, attendance scheduling, stopping rules, and the distinction between research and instruction.
- Predefine 3–5-day spacing windows if retained, missed-session policy, use across devices, dropouts, and whether participants can continue after a missed visit; current demo has no mandatory intersession time lock.

## 6. Methods, independent review, data protection
- Expert-check all 95 questions, 32 recovery resources and all outcome keys; fix “Explain...” single-choice mismatch, copied distractors, hint response claim and questionnaire validity.
- Independent security and WCAG accessibility review, institutional privacy/data retention/processor decisions, backups, real HTTPS and realistic concurrent-user stress tests. GitHub Pages scripted preview is not approved data collection.
- Restrict PII, invitations, raw responses, LFS text and permissions to controlled systems; de-identified sharing policy requires institutional approval.

## 7. Preregistration and sign-off
- Prepare the full protocol with the SPIRIT 2025 checklist (34 minimum items) and use CONSORT 2025 for reporting; intervention details should follow TIDieR.
- Choose appropriate registry (e.g., OSF preregistration for eligible nonclinical educational research, subject to institutional requirements), time-stamp versions before first participant recruitment/randomization, and record any subsequent amendments and rationale.
- **Approval checklist:** PI + statistician + educational measurement expert + licensed LFS user + institutional ethics/privacy authority + operational/security reviewers. These sign-offs are required when applicable and are not claimed here.

## Open decisions / NO-GO blockers
1. Pilot vs confirmatory? Primary scientific estimand and hypothesis?
2. Target participant population; actual enrollment and attrition assumptions; sample-size justification?
3. 3–5-day session spacing and scheduling enforcement?
4. Original LFS usage rights; web implementation; scoring and frequency?
5. Validated pre/posttest items and identical cross-arm instructional exposure assumptions?
6. Ethics/privacy/governance/host and independent review evidence?

### Sources
- SPIRIT 2025 https://doi.org/10.1136/bmj-2024-081477
- CONSORT 2025 https://pmc.ncbi.nlm.nih.gov/articles/PMC11995452/
- VAS-F original https://pubmed.ncbi.nlm.nih.gov/2062970/
- Fatigue instrument taxonomy https://pmc.ncbi.nlm.nih.gov/articles/PMC2909842/
- LFS 13 fatigue / 5 energy https://pmc.ncbi.nlm.nih.gov/articles/PMC4902715/
- Original reproduced scale copyright notice https://www.med.upenn.edu/cbti/assets/user-content/documents/Sleep-Instruments-book.pdf
