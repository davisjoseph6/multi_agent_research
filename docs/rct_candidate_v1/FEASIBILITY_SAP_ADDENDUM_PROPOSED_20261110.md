# Proposed statistical reporting addendum — 3-arm randomized feasibility pilot

**Status:** 2026-11-10 **DRAFT, not statistician-approved**. Complements the existing `PILOT_SAP_DRAFT_20261108.md`; does not override its signed status (none exists). Implements the *direction proposed by the supervisor*, not any claim of confirmatory efficacy.

## 1. Analysis populations and exact future definitions

- **Approached, screened, eligible, consented, randomized:** count independently with an approved, minimally identifying screening funnel. Do not assign A/B/C before eligibility and freely given participation consent.
- **Randomized set:** all participants assigned an arm, regardless of subsequent completion. Original arm must be used for all arm-level rates, including withdrawals and deviations.
- **Visited (1,2,3):** independently verified staff-supervised attendance of the relevant visit, not an automatically simulated event. Actual elapsed time is required, not the fictional fixed 4-day clock.
- **Completed protocol:** all 3 study visits attended and an observed final posttest under the approved visit/deviation policy. The candidate reporting contract requires this numerator to be no larger than visit-3 attendance and available posttests.
- **On-window adjacent visit pairs:** count visit1→visit2 and visit2→visit3 that meet the **PI-approved** 3–5-day elapsed gap. Candidate rate denominator is all adjacent attended pairs (visit2+visit3), subject to confirmation of eligibility/rescheduled/missed-visit rules.
- **Expected M-VAS opportunities:** candidate synthetic metric is two observations per *attended* visit across the three sessions. Whether interruptions, missed assessments and partial visits remain in denominator **must** be frozen by PI/statistician before real collection. Never code missing as zero.
- **Available posttest:** independent final assessment actually recorded; percentage denominator chosen as visit-3 attendees in the draft report. An alternate completer denominator can inflate completeness if completing the protocol requires a posttest; the statistician must avoid circular definitions.
- **Application request failures:** candidate synthetic metric counts failures among received application requests, while retries and disconnected clients must be separately analyzed. Do not treat a 200 HTTP response as proof the application successfully persisted a unique answer.
- **Intervention fidelity deviations:** classify wrong-arm content, unapproved recovery, missing/broken resource, instructor help, version drift, corrupted allocation and other predeclared incidents; count and report by arm/session.
- **Critical incidents:** define severity, report window, ownership and what constitutes a study pause; software cannot self-assert absence of incidents it never monitored.

## 2. Statistical summaries

Pre-specify denominators and report **numerator/denominator, rate and Wilson 95% interval** for recruitment, eligibility, three-visit completion, visit timing, posttest availability, six-reading fatigue completeness and application failure. Reports will be **overall and by randomized arm**, with missing data and interruption reasons.

The local synthetic reporting code `src/prototype/pilot_feasibility_reporting_draft.py` is a *pure aggregate-only scaffold*: it validates monotonic visit attrition and arithmetic, computes descriptive Wilson intervals, and **does not** calculate treatment effects, label a cohort `GO`, accept actual participants or claim a signed SAP. The associated `EXAMPLE_FICTIONAL_FEASIBILITY_COUNTS.json` is entirely fabricated.

### Retention precision example, NOT approval

If 75 of 90 randomized students eventually completed all visits and final posttest, the **observed rate would be 83.3%**, with a two-sided Wilson 95% interval of approximately **74.3%–89.6%**. For 25 of 30 completing in one arm, the interval is about **66.4%–92.7%**. This illustrates feasibility-rate uncertainty. It does not mean 25 completers in each arm are guaranteed, or that 90 is a powered sample for educational effects.

## 3. Proposed progression and stopping decision

The earlier draft gave *candidate discussion values* (80% retention overall, 95% posttest capture among final-visit attendees, no unauthorized enrollment, zero unaddressed critical incidents). **These thresholds are unapproved**. PI + statistician must decide:
- desired precision for each feasibility proportion, arms and overall;
- which shortfalls lead to **GO / AMEND / STOP** for the **future definitive study**, not automatically for current student recruitment;
- whether any participant-harm or data incident mandates immediate interruption;
- handling of differential attrition, imbalanced arms, intervention dose and missingness;
- what sample-size adjustments are allowed, by whom, and without outcome-driven optional stopping.

The clinical/nonclinical trial category and whether formal study registration is required must be determined by the institution. Do not claim a trial registration or ethics exemption from this document.

## 4. Exploratory educational and fatigue analyses

The PI proposal treats pre/post learning and perceived fatigue as **exploratory**. For learning, preserve original randomized arm, outcome 0–16 independent visit-3 posttest, baseline 0–16 pretest, missingness and descriptive arm estimates. Any ANCOVA is exploratory; do not infer 80%-powered effectiveness from the feasibility sample.

For fatigue, independently verify the **single proposed 0–100 mental-fatigue VAS** before/after each learning visit, six total numeric observations. Candidate within-session change is `post - pre`, but exact item wording, anchors, timing, rights, digital mode, scoring, translations and accessibility require independent measurement approval. The old six-item after-session questionnaire is *not* equivalent to six pre/post single items. Do not claim "without additional fatigue" or noninferiority absent a meaningful prespecified margin and powered confirmatory design.

## 5. Dataset and reproducibility requirements for the future approved system

Collect minimum authorized fields only. Separate identity/contact files from pseudonymized student event logs; maintain original-arm assignment in an independently audited access-controlled area. Record consent/eligibility authorization, visit start/end actual UTC timestamps, role and approved deviation, action identity and immutable replay key, instrument version, item/content hashes, response-completeness/missingness code, student withdrawal state, exception/incident counters and staff interventions.

Any analysis/export procedure must be independently reviewed for GDPR, masking, disclosure and reproducibility. Freeze exact protocol/SAP and reporting code commit **before enrollment** and bind to private signed evidence. Do not publish participant-level records or authentication artifacts to GitHub. No such approved human record collection or export currently exists in this branch.
