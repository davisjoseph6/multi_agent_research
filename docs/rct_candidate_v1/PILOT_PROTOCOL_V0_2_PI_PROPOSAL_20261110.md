# IJCAI 2027 randomized feasibility pilot — PI-direction protocol v0.2 (PROPOSED)

**Prepared:** 2026-11-10. **Status: PI-DIRECTION PROPOSAL ONLY. NOT SIGNED OR AUTHORIZED. DO NOT RECRUIT.** This updates the intended scientific direction of `PILOT_PROTOCOL_DRAFT_20261108.md`, but does not silently overwrite that historical draft or its SAP. The supervisor's message is the source for the explicit decisions below; additional operational details are **draft engineering assumptions**, not assertions of PI approval.

## 1. Purpose and study type

The supervisor now proposes a **three-arm individually randomized feasibility pilot**, initially targeting **90 enrolled students**, **subject to independent statistical review**. The primary objective is to establish whether a larger future randomized controlled trial can be delivered and measured reliably, **not** to demonstrate confirmatory superiority of the adaptive algorithm.

The study's primary feasibility domains are:

1. **Recruitment:** students approached, screened, eligible, consented, randomized, rate/time to recruit; record enrollment window and refusals under approved privacy controls.
2. **Retention:** proportion of randomized students completing all three supervised visits and the final posttest, overall and by assigned arm; record withdrawal/missingness reasons.
3. **Three-session adherence:** visits attended, each valid 3–5-day interval, schedule deviations, intervention completion and rescheduled visits.
4. **Intervention fidelity:** delivery of assigned policy, bounded and recorded recovery actions only in A, fixed content version, duplicate-answer rejection, instructor interventions and contamination.
5. **Software reliability:** action and HTTP error rates, retry/idempotency, performance per route, wrong-arm exposure, downtime, recovery and security incidents.
6. **Data completeness:** posttest captured at final visit, proposed pre/post fatigue scores, time stamps, audit trail and reasons for missing observations.

See `../PILOT_HUMAN_STAGING_IMPLEMENTATION_PLAN_20261110.md` and `PILOT_SAP_DRAFT_20261108.md`. PI/statistician must freeze all endpoint denominators, confidence intervals, missingness handling, feasibility progression criteria, stopping rules and the primary analysis before recruitment.

## 2. Three-arm interventions — proposed package comparisons

Randomize eligible, consented students 1:1:1 under an **independently approved concealed allocation scheme**; do not expose arm selection to any participant or allow staff to forecast assignments.

| Arm | Proposal | Critical control |
|---|---|---|
| **A** | POMCP-based adaptive learning with bounded, predefined, auditable self-healing recovery | Approved resource catalog; documented per-session limit; evidence of **offer vs render vs completion**; recovery only for assigned A |
| **B** | Greedy adaptive learning | No A-only self-healing interventions; capture policy version/decision trace without revealing sensitive allocation |
| **C** | Fixed non-adaptive learning | Frozen and versioned balanced item order; no adaptive or A-only recovery |

All three arms draw from **the same approved concepts, assessment structure and core question bank**. The study compares these **intervention packages**. Because A has recovery resources and B/C do not, it **cannot attribute an observed A-versus-B/C difference solely to POMCP** or assume matched exposure/time.

The previous supervisor brief also described BKT/Q-matrix/Bloom/degradation threshold/fixed four-step recovery, live generation and a neural-predictor benchmark. The supervisor's new proposed package specifies POMCP/greedy/fixed but **does not formally resolve each lower-level mechanism**. Record exact model versions, thresholds, recovery budget, content sourcing, resource exposure and whether those legacy features remain scientifically required in a dated protocol amendment.

## 3. Proposed visits and outcome collection

Three supervised visits, provisionally **3–5 calendar days apart**, with server-recorded and enforced actual time. **This schedule comes from the existing protocol draft, not from a new assertion in the supervisor's reply**, and still requires PI/ethics confirmation.

| Visit | Proposed sequence |
|---|---|
| 1 | Eligibility and voluntary consent **before allocation**; independent 16-item pretest; one fatigue rating immediately **before learning**; 20 core practice questions plus possible bounded A recovery; one fatigue rating immediately **after learning** |
| 2 | One pre-learning fatigue rating; 20 core practice questions plus possible bounded A recovery; one post-learning fatigue rating |
| 3 | One pre-learning fatigue rating; 15 practice questions plus possible bounded A recovery; one post-learning fatigue rating; independent 16-item final posttest and debrief |

The supervisor now proposes **one single-item 0–100 mental-fatigue M-VAS immediately before and after learning in each visit**, six total ratings per student. Learning gains and fatigue are **exploratory**, to inform a future adequately powered confirmatory trial. No fatigue noninferiority or educational efficacy conclusion from this feasibility sample.

**Important:** The original supervisor brief's **six NASA-TLX-like items administered after each session** and the proposed single-item pre/post VAS are scientifically distinct. The *new supervisor reply favors the VAS as the pilot proposal*. Exact wording, anchors, attribution/rights, accessibility, French/English language versions, digital implementation, validity, missingness and scoring **remain under independent review**; the current deployed fictional six-item questionnaire is **not approved** and must not be relabeled.

## 4. Sample size and progression

Proposed target: **90 enrolled students, roughly 30 randomized per arm** if a balanced allocation is approved. An earlier target of **75 completers** (~83% overall retention) was a *planning expectation*; the supervisor's reply did **not** independently approve 75 as a required number, nor guarantee 25 completers in each arm. A statistician must document an appropriate precision/feasibility rationale and realistic recruitment/dropout scenarios. If the research aim becomes *confirmatory effectiveness*, the trial must be newly powered for primary endpoints, attrition, multiplicity and relevant educational effect size.

The current draft mentions candidate progression discussions (e.g., >=80% retention overall, >=95% posttest capture among final-visit attendees), but these are **NOT approved thresholds**. Statistical reviewer and PI must specify binary go/amend/stop criteria and what constitutes numerator/denominator before any genuine data collection.

## 5. Eligibility and consent

A provisional novice-student population 18+ with **no previous formal behavioral-economics coursework** is inherited from the November 8 draft, not newly confirmed in the supervisor reply. Final eligibility, prior training screen, school population, session location, approved language, accessibility accommodations and independent recruitment arrangements require ethics/PI approval. Avoid academic grading/authority pressure; refusal or withdrawal must not affect academic treatment.

Use distinct decisions for voluntary research participation consent and GDPR lawful processing basis. The institution must name the actual controller and PI, designate the data access team and review the participant information, rights, withdrawal, retention, processors, cross-border transfers and DPIA determination before collecting real information.

## 6. Proposed governance

The supervisor wrote they **will formally serve as principal investigator**, that **Aivancity would authorize the study**, and that they **will initiate** ethics, DPO and independent item/content reviews. This message is evidence of **intent and proposed responsibility**, not formal signed institutional authorization, ethics disposition, DPO clearance, reviewer approval or student-recruitment permission.

Before real participants:
- record the PI's actual name, role and written acceptance privately;
- obtain Aivancity's authorized institutional sponsor/controller determination, study identifier, site authorization and named ethics route;
- obtain signed statistician-approved protocol, SAP and 90-person feasibility justification;
- independently review 95 provisional questions, 32 resources, content rights/language/accessibility and exact fatigue measure;
- approve consent, eligibility, allocation concealment, staffing, recruitment, three-visit timetable and missingness;
- accept independent security, accessibility, external HTTPS load, resilient storage, backup/restore, audit and release controls;
- bind signed evidence and final written institutional GO to the **exact candidate commit and content hashes** in a **private** evidence directory; do not commit personal records or signed approvals to GitHub.

## 7. Release state

The current repository exercises **fictional-only** actions. Human enrollment, permissioned personnel, real study calendar enforcement and true allocated accounts have **not** been implemented and independently accepted for human use. **No real enrollment may occur**, even if the CI suite or synthetic full-journey rehearsal passes. Public 14-gate evidence template remains 0/14; no false approval flags will be set.

Related sources:
- `PI_FEASIBILITY_DIRECTION_PROPOSED_20261110.json`
- `PILOT_SAP_DRAFT_20261108.md`
- `PILOT_SAMPLE_SIZE_DECISION_20261109.md`
- `MVAS_PROPOSAL_20261108.md`
- `SUPERVISOR_BRIEF_PROTOCOL_CROSSWALK_20261110.md`
- `../pilot_release_evidence/MANIFEST_TEMPLATE.json`
