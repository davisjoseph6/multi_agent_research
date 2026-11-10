# Aivancity three-arm randomized feasibility pilot — review and authorization request pack

**Prepared 2026-11-10. WORKING REQUESTS ONLY. NOT APPROVED. No real student enrollment.**

The supervisor proposed to act as **principal investigator**, named **Aivancity as proposed authorizing institution**, and offered to initiate independent ethics, privacy and content reviews. This packet makes the requests concrete; it is **not** evidence that Aivancity has accepted the responsibility, granted authorization, or provided a sponsor/study number.

## 1. Decisions requested from the PI and statistician

| Decision / required document | Proposed option to review | Current status / evidence gap |
|---|---|---|
| **Study classification** | Three-arm individually randomized **feasibility** pilot; educational effect and fatigue exploratory, future definitive RCT separate | PI proposal received; dated protocol/SAP signoff missing |
| **Recruitment size** | 90 initially enrolled, expected 1:1:1 groups, not a guarantee of 75 completing | Independent feasibility precision/attrition review missing; progression thresholds must be agreed |
| **Population/site** | Adult enrolled novice students, without formal behavioral-economics coursework, 3 supervised sessions | Verify eligibility, recruiting institution, accessibility, staff capacity, avoiding grade/teacher coercion |
| **Allocation** | Concealed secure server-side scheme, candidate balanced randomization, no participant-selected arm | PI/statistician must approve generation, implementation, concealment, deviations and audit |
| **Arms** | A POMCP + bounded audited recovery, B greedy adaptive, C fixed; shared approved core questions and concepts | Review actual policy version, recovery **per-session count**, fidelity and unmatched A resource exposure |
| **Fatigue measure** | One 0–100 **mental-fatigue VAS** before/after each visit, six total; exploratory | Exact validated question/anchors, rights, versions, language, accessible digital parity, response/missingness policy unresolved |
| **Primary feasibility endpoints** | Recruitment, retention, visit adherence, fidelity, software reliability and data completeness | Freeze numerator/denominator, Wilson interval plan, target thresholds and no-go/stop criteria in SAP |
| **Exploratory learning outcome** | Independent 16-item final posttest and 16-item baseline pretest | Independent test-form and scoring review, no pilot efficacy hypothesis claims |

Existing documents to review:
`PILOT_PROTOCOL_V0_2_PI_PROPOSAL_20261110.md`,
`PILOT_SAP_DRAFT_20261108.md`,
`PILOT_SAMPLE_SIZE_DECISION_20261109.md`,
`MVAS_PROPOSAL_20261108.md`,
`SUPERVISOR_BRIEF_PROTOCOL_CROSSWALK_20261110.md` and the **14 still-unresolved** rows in `SUPERVISOR_ALIGNMENT_DECISIONS_TEMPLATE.json`. This original decision template remains unresolved pending a signed final protocol; the newer PI message is added separately and does not impersonate the PI's signed approval.

## 2. Required institutional/ethics/DPO responses

**Aivancity authorized institution representative** (identity and authority to be verified privately):
- Confirm whether Aivancity will formally act as **research controller/sponsor**, host and authorize the study, and identify separate operational and ethics responsibilities.
- Provide official protocol/study identifier, researcher/PI appointment acceptance, supervisory delegation and staff permission for student recruitment, classrooms, devices, hosting and follow-up.
- Identify the competent educational research ethics review body/office and return its classification and approval/determination in writing; do not infer an ethics exemption.
- Approve the English and/or French participant information, independent consent/withdrawal, safeguarding, student grading separation, accessibility and recruitment procedure.

**Data protection officer / controller**:
- Record personal data inventory and minimization: screened eligibility, a separate identity/contact lookup, pseudonymous research records, fatigue, performance, timing/technical logs and withdrawal.
- Decide GDPR lawful bases, sensitive-data classification, DPIA need, rights/retention/deletion, encryption and hosting region, processors, transfer restrictions and breach contacts. Do not equate research participation consent with the GDPR lawful processing basis.
- Approve or reject Google Forms, Sheets, Calendar, WhatsApp or other third-party enrollment/communications. **Do not start using any for real data before a written decision.**

**Independent teaching, measurement and language reviewers**:
- Individually approve the **95 provisional quiz items** and **32 resources**, answer keys/distractors, source/legal rights, difficulty and accessibility; sign off the exact bank/content hash.
- Approve the precise M-VAS single-item source, word choice, anchors, numerical 0–100 digital adaptation, language validity and within-session delta calculation (post − pre).
- Evaluate any inter-arm learning exposure/time imbalance, and the exact interpretation of A vs B/C package effects.

Keep completed correspondence/approval documents in a **private institution-approved system**, never in this public GitHub repository.

## 3. Engineering deliverables that can be prepared without participants

- Separate preproduction environment and synthetic-only dataset, isolated from `demo.selfhealing-edu.fr` and from any future human production environment.
- Authenticated staff/participant service and concealed arm allocation **on the server**; eligibility and consent must precede assignment, no unauthenticated enrollment endpoint, no trusted client boolean flags.
- True server-clock 3–5-day session limits, staff-supervised visit check-in, missed-visit/deviation handling and approved pre/post VAS steps.
- Versioned data model, response idempotency, independent auditor access, recovery/withdrawal and export policy, content hashes, signed migration + rollback plan.
- Real multi-process concurrency review: per-process FIFO queues do not coordinate across independent processes; choose a reviewed SQL/queue architecture and independently test full three-visit persistence.
- External HTTPS/device/accessibility/security/backup tests with written site-approved p95/p99/error-rate/availability thresholds and capacity estimates; production TLS does not imply security acceptance.
- Pre-approved operational RPO/RTO, encrypted offsite backup plus independent restore to a separate environment, incident/deviation procedures and responsible contacts.

## 4. Private release signoff process

The public `../pilot_release_evidence/MANIFEST_TEMPLATE.json` lists **14 pending independent signoff categories**. It can be copied into a *private* evidence directory for the responsible institution. An engineer's checklist or user-entered JSON cannot authenticate a signature or turn on human enrollment. Associate each private document to the exact reviewed release and its SHA256 digest; use independent reviewers to verify authority. Final written institutional/PI **GO** is mandatory **after** the relevant reviews and witnessed release rehearsal, not before.

### Proposed review-meeting output (record privately)

- Actual PI identity/acceptance and institutional representative:
- Official study ID / approved site / decision:
- Statistician name and full sample-size/analysis signoff:
- Ethics authority and determination/approval evidence:
- DPO lawful basis/DPIA/hosting and retention determination:
- Independent item/content and instrument reviewers:
- Final instrument version and exact anchor wording:
- Final per-session recovery budget and 3–5-day schedule:
- Recruitment eligibility, languages, staffing, consent and withdrawal plan:
- Independent engineering/security/accessibility/load/restore reviewers:
- Date/version of approved protocol/SAP/content/release candidate:
- Final GO signatories and approved recruitment window:

**No empty line above is evidence of an approval. Do not fill from assumption or publish private identifiers.**
