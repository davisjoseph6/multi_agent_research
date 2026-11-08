# Draft pilot study protocol — self-healing adaptive learning in behavioral economics

**Version:** 0.1, 2026-11-08. **NOT APPROVED. DO NOT RECRUIT.**
**Principal investigator / responsible institution / ethics committee / DPO:** TO BE NAMED IN WRITING.
**Pilot classification:** proposed randomized **feasibility pilot** of a future effectiveness trial. If the team instead intends a *confirmatory* RCT, replace the feasibility aim, sample size and analysis design before enrollment.
**Site/hosting:** classroom supervision arrangements unspecified; EU IONOS VPS currently serves *fictional operator-only demo*, not human records.

## Study rationale and design

Behavioral economics instruction is the approved content area. Adult students without prior formal behavioral economics training are provisionally preferred. Three parallel individual-randomized groups (1:1:1); intended enrollment 90 (30/arm); target ~75 completing all visits (25/arm) assumes 16.7% overall attrition and must not be presented as guaranteed per-arm completion.

**A — POMCP self-healing package:** adaptive question selection and optional, planner-triggered recovery interventions (concept summaries, worked examples, Socratic hints, DROP-2). Maximum two recoveries per learning session, conditional on planner decisions.

**B — greedy adaptive baseline:** mastery-guided question selection but no recovery resources.

**C — versioned balanced fixed-order baseline:** non-adaptive question schedule without recovery.

**Interpretation caveat:** Arm A differs by both planner and availability/dose of resources. The design tests the complete self-healing package vs two baselines; it **does not separately identify a POMCP algorithm effect** or equalize time-on-task. Record actual practice/resource exposure duration and analyze descriptively. A matched access control would require approved redesign.

## Objectives and endpoints

**Primary pilot objective:** determine feasibility of recruiting, retaining, delivering and measuring three supervised sessions under the proposed controls, including remote platform reliability and acceptability.

**Candidate progression criteria (to be approved before first student):**
- Feasibility of recruiting up to 90 eligible participants within the agreed window and staff capacity.
- At least 80% completing all three visits *overall* as a discussion threshold; report arm-specific rates and 95% intervals, not just aggregate.
- At least 95% of intended posttest measurements captured among completers; report per-arm and per-session missingness, with reasons.
- 100% verifiable participation consent, correct allocation, no cross-arm leakage and no unauthorized enrollment.
- All critical security/accessibility incidents addressed and restored backups verified.
Thresholds are preliminary go/amend/stop discussion criteria, not formal approval.

**Future confirmatory learning endpoint (pilot exploratory):** independent 16-item posttest number correct (0–16) at end of visit 3. Baseline covariate: independent 16-item pretest score (0–16), measured before intervention; exact item forms and independence must be reviewed. No claim that repeated pre/post tests have equal difficulty until psychometric sign-off.

**Secondary exploratory endpoints:** mental fatigue M-VAS 0–100 before and after each learning session (six per student); change within each session = post minus pre. Also completion, withdrawal, adverse experiences, operator interventions, device/accessibility errors, teaching time, resources per session, and time-on-task. No diagnosis or clinical fatigue claim.

## Provisional eligibility

**Include:** 18+; currently enrolled in a participating educational institution; no previous formal coursework/training in behavioral economics (self-report screening); able to understand the approved information sheet and chosen instruction language; able to consent freely; able to attend 3 supervised sessions 3–5 days apart. Provide reasonable accessibility accommodations without automatically excluding disability.

**Exclude / screen carefully:** prior formal behavioral economics qualification/course or material expertise that defeats the novice estimand; cannot freely consent; prior participation in this study; conflicts preventing study visits; duplicate registration. Do not exclude medical conditions or protected characteristics without an independent ethical and scientific justification. If participants are the investigator's own students, implement independent recruitment and grading separation to minimize coercion.

**Record:** screening answers with minimum necessary information, exclusion reason, pseudonymous participant ID, prior familiarity, education context. Verify eligibility *before* allocation. Screening status must not reveal assigned arm.

## Visit schedule and instrument sequence

Three supervised sessions, each adjacent pair separated by 3–5 calendar days **if approved**. Record intended/actual timestamps, attendance, missed-visit reason, reschedule authority, supervisor, device, room and study-ID. No simulated spacing for genuine enrollment.

- **Visit 1:** eligibility/participant information; voluntary consent; allocation concealed until enrollment; independent 16-question pretest; immediate **pre-learning** M-VAS; 20 practice questions plus optional A recovery resources; immediate **post-learning** M-VAS.
- **Visit 2 (3–5 days after visit 1):** pre-learning M-VAS; 20 practice questions plus optional A recovery; post-learning M-VAS.
- **Visit 3 (3–5 days after visit 2):** pre-learning M-VAS; 15 practice questions plus optional A recovery; post-learning M-VAS; independent 16-question posttest; completion/debrief.

M-VAS placement deliberately excludes the extra fatigue of the final posttest; account for visit-1 pretest as potential baseline fatigue covariate. Record response times and changes of measure version. Require a documented handling policy for unanswered assessments and technical interruptions; no forced fabricated values.

**Spacing not implemented in current candidate**: operational schedules and server-side signed visit/identity authorization are **release blockers**. Disable progression to next visit until valid attendance/time criteria or an approved protocol deviation. No change to synthetic demo during design.

## Allocation, masking and fidelity

Computer-generated concealed permuted blocks balancing A/B/C; freeze allocation/version and audit mechanism; do not disclose future block membership/assignments to supervisors. The current fictional demo seeds and internally pre-enrolls, so it is NOT a human enrollment workflow. Human trial must consent before randomization and must prevent accidental re-enrollment/duplicate identities.

Participant and supervisor masking not feasible due to visible interventions. Keep outcome scoring automatic and immutable where possible; analysts blind arms (coded labels) until main analysis freeze. Use independent review for item correctness, resources, outcome scoring, translations, accessibility and analysis choices.

## Consent and ethics (DO NOT SUBSTITUTE DRAFT FOR APPROVAL)

Separate participant information/voluntary research participation consent from GDPR legal-basis determination. Legal basis for processing may be different from research participation consent; DPO must decide whether fatigue scores are special-category personal data and whether DPIA is required. Specify institution/controller/processor, purpose, measures, retention, security, cross-border processors, withdrawal and post-withdrawal handling, accessible contacts and complaints mechanism; recruitment text should clarify no effect on grades/teaching/support.

French education research is not automatically health research/RIPH simply because it asks about fatigue: competent institution must document scope/ethics. Provide approved language(s), independent recruiter for students exposed to academic power asymmetry, no collection before written clearance.

## Content and materials

Behavioral economics topics unchanged. **All 95 questions and 32 resources require signed independent review**, keyed by ID and content hash, including clarity, distractors, source permissions, answer correctness, concept coverage, difficulty, language and possible cultural bias. No silent editing after unblinding; version/hash and amendments.

Instrument proposal: single 0–100 M-VAS with approved question, anchors, visual/digital parity and timestamp semantics; source: `MVAS_PROPOSAL_20261108.md`. The existing **six-item rehearsal-only** questionnaire is unvalidated and must never be described as M-VAS.

## Harms / incident / deviations

Low-risk educational intervention presumed, but **risk and competent review status remain unclassified**. Define distress/fatigue response, break policy, technical incident reporting, safeguarding, withdrawal, compensation and adverse event escalation by institution. Record deviations from 3–5 day windows, system downtime, differential instructor help and data loss. A resource being *offered* is not proof it was read, understood or effective.

## Data and quality

Keep a separate controlled human-data environment from the IONOS fictional DB. Verify encryption in transit and at rest, backups, identity/access control, dual-role permissions, DPO review, participant ID mapping, retention and disposal, immutable audit trail, monitored service health, rollback plan, registered version of all forms and recruitment. Implement validated reporting and independent QA before pilot authorization.

## References and dependent files

- `PILOT_SAP_DRAFT_20261108.md`
- `PILOT_POWER_20261108.md`
- `MVAS_PROPOSAL_20261108.md`
- `../PILOT_READINESS_20261108.md`
- CONSORT randomized pilot extension: https://www.bmj.com/content/355/bmj.i5239
- CONSORT 2025: https://www.bmj.com/content/389/bmj-2024-081123
- CNIL non-health research basis: https://www.cnil.fr/fr/recherche-scientifique-hors-sante-quelle-base-legale-pour-un-traitement-de-recherche
