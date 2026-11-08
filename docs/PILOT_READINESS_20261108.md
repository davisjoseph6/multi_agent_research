# IJCAI 2027 — pilot readiness control register

**Prepared:** 2026-11-08. **Status:** DRAFT / NO HUMAN ENROLLMENT AUTHORIZED.
**Scope:** Three-arm behavioral-economics adaptive-learning RCT, existing restricted fictional operator demonstration.
**Existing deployed version (reported by operator):** VPS running the `feature/rct-https-staging-20261101` checkout (previously identified as `3d8e189`). Do not modify or deploy the pilot draft branch to the live demonstration without a change review and repeat tests.

## Rule: different kinds of "ready"

1. **Software rehearsal:** synthetic records, internal and HTTPS checks; does not support enrollment.
2. **Pilot with real students:** separate formal sponsor/institution authorization, ethics determination/approval, DPO/privacy review, expert content sign-off, tested operational controls, approved versioned protocol/SAP and student-facing instruments.
3. **Definitive RCT:** all of (2), plus justified statistical power and endpoint/analysis freeze.

A working public web address and HTTPS certificate do NOT imply stage 2 or 3.

## Evidence register (as of 2026-11-08)

| Workstream | Known evidence | Outstanding release artifact / acceptance criterion | Status |
|---|---|---|---|
| DNS, TLS, server | Operator-reported DNS resolves `demo.selfhealing-edu.fr` to IONOS VPS; Caddy ACME certificate; HTTPS authenticated GET 200; unauthenticated GET 401. | Certificate/renewal check; configuration export, firewalls, renewal alert, system patch/monitor plan. | STAGING PARTIAL |
| SSH and process isolation | Non-root administrator, SSH keys, password/root login disabled; service account and Gunicorn loopback 127.0.0.1:8077; systemd active. | Independent hardening review, restricted SSH source IP, audit/recovery, separate staging vs human-data environments. | STAGING PARTIAL |
| Enrollment safety | `operator_demo` only, fictional A/B/C 3 each; public `/api/rct/enroll` 403; no live release evidence. | Reverify after any build, forbid demo API from handling human data. | REHEARSAL PASS ONLY |
| Automated code tests | 41 targeted pytest tests passed on VPS; local automated browser and synthetic concurrency rehearsals reported. | Full deployed-commit suite + CI report, migration/rollback checks, defect register. | PARTIAL |
| Real-browser journeys | Two Arm A fictional participant starts, save/reload/resume passed; Arm B/C question-only behavior observed. | Complete A/B/C three-session journeys, Firefox/Chromium/phones, poor network, expiry, retry/idempotency, simultaneous use. | PARTIAL |
| Load | Local 30-participant synthetic Flask test-client benchmark previously passed. | External HTTPS workload modeling 30+ concurrent study sessions, p50/p95/p99 latency, peak RAM/CPU, SQLite lock/timeout rates and recovery; record thresholds before testing. | NOT VERIFIED |
| Accessibility | No independent WCAG audit reported. | WCAG 2.2 AA keyboard, labels/focus, screen reader, zoom, contrast, forms/error messages, fatigue slider alternate keyboard input. | BLOCKED |
| Security/privacy | Basic Auth + bearer invitations; private fictional SQLite; some test bearer tokens disclosed in chat and rotated. | Independent application pentest, vulnerability/secret scanning, DPO DPIA necessity assessment, account/data location, role/retention policies, breaches, backups, certificate renewal. | BLOCKED |
| Disaster recovery | Local fictional SQLite backup/restore rehearsed in development. | Encrypted off-server scheduled backup, restore drill on VPS, RPO/RTO agreed, checksums, minimum-privilege and alerting, test during controlled outage. | BLOCKED |
| Content | Behavioral economics accepted as domain; 95 items + 32 resources currently unreviewed. | Two independent content/psychometric reviewers; item-by-item sign-off, answer-key and distractor review, sources, licensed text, scoring, language proof, freeze content hashes. | BLOCKED |
| Fatigue | Fictional six-item unvalidated rehearsal instrument. | Approved authentic M-VAS administration/scoring, pre/post at each of 3 sessions (6 ratings), display equivalence/rights, instrument version and missingness test; do not rename rehearsal fixture. | BLOCKED |
| Protocol/SAP | Drafts prepared on this branch. | Supervisor/institution/statistician approve both; outcomes, intervention contrast, missing data, randomization, error control, amendments registered BEFORE seeing human outcomes. | BLOCKED |
| Recruitment | Working hypothesis: 90 invited/enrolled, 75 complete (25/arm). | Feasibility rationale if pilot; proper power if confirmatory. Recruitment frame and absence of behavioral economics training verified without coercion. | BLOCKED |
| Supervised visits | Proposed 3 sessions, 3–5 days between consecutive sessions. | Approved schedule, physical rooms/staff, identity verification, reminders, rescheduling, no cross-arm contamination, enforce spacing in software and audit. | BLOCKED |
| Participant materials | Fictional rehearsal text only. | Approved language(s), information sheets, separate participation vs GDPR permissions, opt-out/withdrawal, compensation, complaints, accessible alternative, contact, data retention. | BLOCKED |
| Governance | Host account belongs to supervisor; research sponsor/controller and institution not yet documented. | Responsible institution, PI, DPO, competent ethics board/classification, institution-authorized hosting/data handling, agreement on paid hosting and administrative access. | BLOCKED |

## Required freeze / evidence before enrolling ONE student

- Signed institutional authorization, ethics pathway determination/approval, DPO/privacy disposition and named institutional sponsor/controller. French non-health educational research is not automatically a French RIPH study; competent ethics and data governance must decide.
- Frozen protocol, SAP, versioned questionnaires, consent forms, 95 item reviews and 32 resource reviews, language and copyright confirmation, documented allocation method and blinding/contamination controls.
- Pilot code change to replace the 3 fictional post-session 6-item fatigue forms with **6 pre/post M-VAS measurements** and to enforce 3–5 day sessions; complete tested migration/revision on a NEW human-trial database/schema, not the fictional DB.
- Independently tested external HTTPS full journeys, user/device/accessibility/security/concurrency tests, verified backup/restore and on-call response.
- Written GO decision countersigned by PI / responsible institution. Keep `operator_demo` and `live` separate; never bypass code gates or recruit through the demo URL.

## Ordered execution

**P0 now:** Maintain separate demo as is, keep tokens private; ask PI for named institution/ethics/DPO/statistician; review protocol/SAP drafts, select instrument, freeze primary comparisons, define eligibility. Implement release checklists in independent review branch.

**P1:** Reviewer worksheet for all 95 questions/32 resources, versioned M-VAS, accessibility and English/French language review; data protection and consent; scheduling and identity model; power/feasibility rationale.

**P2:** Versioned software changes on a new pilot-candidate branch; new encrypted human-trial DB distinct from `fictional.sqlite3`; unit/integration browser tests; external HTTPS load, device and security tests; off-server backup and restore.

**P3:** Institutional authorization, independent QA signoff, date/location staffing and signed GO. Only then pilot recruitment.

## Critical design limitations

- Arm A has POMCP plus up to two additional recovery resources per session. Arm B greedy and Arm C fixed do **not** receive resource interventions. This estimates a **bundled self-healing package** effect, not the isolated effect of POMCP given equal resource access or equal time-on-task. State this in hypothesis, consent and discussion; matched control is a protocol amendment.
- `operator_demo` seeded "consent" pertains only to invented synthetic records. It is not research consent.
- Existing test data and disclosed (rotated) invitations are never human study data.
- A 90-student pilot may characterize feasibility and estimate variance/attrition. At 25 completers per arm, pairwise 80% power at two-sided alpha .025 needs roughly standardized `d=0.896` under an *unadjusted normal homoscedastic two-sample t model*. Moderate effects are not reliably detectable; see `docs/rct_candidate_v1/PILOT_POWER_20261108.md`.

## References

- Eldridge et al. (2016), CONSORT extension for randomized pilot and feasibility trials: https://www.bmj.com/content/355/bmj.i5239
- CONSORT 2025 trial reporting: https://www.bmj.com/content/389/bmj-2024-081123
- CNIL non-health scientific research legal bases: https://www.cnil.fr/fr/recherche-scientifique-hors-sante-quelle-base-legale-pour-un-traitement-de-recherche
- Mental fatigue randomized crossover (see detailed candidate instrument note): https://pmc.ncbi.nlm.nih.gov/articles/PMC12746782/
