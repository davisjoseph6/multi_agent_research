# IJCAI 2027 — Intensive evidence-first completion playbook (30 Oct–2 Nov 2026)

**Current verified checkout:** `feature/ijcai2027_prototype`, `4b6626c`, 1,029 tests passed in WSL, exact Bayesian short-path oracle parity with maximum observed discrepancy 2.22e-15. **Provisional Steps 72–123 score: 55.8%**, 29/52 equivalents. **Human/ethics clearance: NO. Lead novel algorithm: NOT ESTABLISHED.**

## Nonnegotiable meaning of 100%

The exact 52 original exit criteria, not a count of passing tests or tasks completed in this playbook, define completion. The register counts 19 synthetic-implemented, 20 partial, 13 external-required. With all 20 partials upgraded but all 13 external requirements unchanged, the original rubric gives at most 39/52 = **75% provisional**. This upper bound assumes every partial can be completely resolved without external signoff, which is unlikely. A real 100% requires genuine independent signoffs, authentic validated educational content and assessments, authorized human research wherever required, and scientific evidence for the core claim. No automatic changes to percentages are permitted.

## Priority 0 (tonight): preserve claims and create drafts

- Confirm `git status --short`, `git rev-parse HEAD`, `git diff --check`; keep archives/untracked source unrelated to the sprint unstaged.
- Run `python3 scripts/step72_123_progress.py`, `python3 -m scripts.step72_123_weekend_triage --output /tmp/ijcai_weekend_evidence.md --json-output /tmp/ijcai_weekend_evidence.json` if already installed, and preserve outputs.
- Run the new `scripts.step96_106_authoring_drafts`, making new reviewed-pending draft CSVs and review ledger; **do not overwrite the canonical 95 or 32 slot CSVs**.
- Run the original content checker with `--items` and `--resources` pointing to the new drafts. Verify all *nonreview* structural problems are addressed, and preserve legitimate independent-review failures. 381 review-related messages is expected only for the representative blueprint, not necessarily the exact live result.
- Editorially inspect at least the first 16 assessment questions and all 8 recovery probes; then systematically review the rest with subject-matter collaborators. Check answer keys, conceptual mistakes, alternate-form leakage, `create` level, source alignment, and whether definitions actually match the 8 target competencies. Record any needed corrections in a new revision, not fake approvals.
- Email a relevant behavioral economist and educational measurement specialist promptly to ask for real, dated independent reviews. Institutional research/ethics staff and supervisor must determine whether a human study is permitted and which protocol is authorized. Do not send unapproved materials to study participants.

## Priority 0 (Saturday): core research validity, not controller proliferation

- Verify the executed Group A policy identity and contract; complete fair comparison of A/B/C learning opportunities, costs, response access and intervention dose (72–74, 78, 88).
- Continue direct mathematical scrutiny of the original drift guarantee: the monotonic synthetic V3 mastery dynamics cannot establish recovery from forgetting; preserve counterexamples and conditional statements (79, 86, 93–94).
- Audit explicit Bayesian learning/forgetting likelihood calibration on out-of-model synthetic cases, including **proper scores**, false positive rate per time and per learner, missed detection, detection delay and identifiability. The 1,029 tests show short-path code parity only, not empirical parameters (83, 85, 86, 95).
- Freeze a written `CONTRIBUTION_DECISION.md` with the exact difference between the proposed method and established BKT with forgetting, POMCP tutoring and constrained decision-making. If the difference is not novel, say so.

## Priority 0 (Sunday): mechanism ablation and unbiased comparison

- New candidate requires an **identical policy minus its proposed recovery mechanism** comparator, plus fixed, greedy, historical heuristic, V3/V5/V6 and matched-dose baselines. Source/metric/action-time/seed handling should be independently reproducible.
- No tuning on heldout seed range beginning at 200000. A confirmatory split may only be accessed after a frozen method, protocol, endpoint definition, analysis plan and independent signoff.
- Report raw mastery alongside nominal net mastery, interventions, response opportunities, compute cost, confidence intervals appropriate to the design, and negative scenarios. No cherry-picking or interpreting n=5 bootstrap intervals as confirmation.
- Check Step 103 content leakage and Step 117–122 browser/storage/security tests: pre/post keys withheld, consent and session tokens segregated, replay/refusal idempotence, timestamp provenance, retention/deletion strategy, negative authorization tests, accessibility and concurrency. Mark limitations clearly where independent reviews are unavailable.

## Priority 0 (Monday 2 November): actual closure audit and IJCAI package

- Review 52 original `docs/steps72_123_closure_register.csv` lines against output artifact ID, source SHA, negative tests, time-stamped independent reviewer record, and the *exact* exit criterion. Change a row only if its full original criterion is genuinely satisfied and independently evidenced where required.
- Run the full suite (`pytest -q -p no:cacheprovider`), progress checker, original content checker, Git provenance, content manifest, security test report and compare negative/positive development results. Report any regressions, not just the passing subset.
- Draft a double-blind original research manuscript storyboard. Claims supported by the Bayesian two-state filter belong under **established baseline**, not new theory; V6 recovery-specific benefit was near zero in the development ablation, and this result must be reported truthfully.
- Secure named external next actions with real reviewers/owners for each blocked Step 75–77, 85, 98–102, 104–105, 118, 121. Approval is not granted by an email request; accepted signoff must be verifiable and scoped.
- Final deliverable: what is **done**, what is **drafted/pending**, what is **not proven**, and what is **not authorized**; score must be independently reconcilable to the same 52-row register.

## Exact step closure map (current historical statuses, NOT newly certified)

| Steps | Evidence work we can do immediately | Closure block |
|---|---|---|
| 72–74 | Shared policy contract, decision pseudocode and rule/POMCP identity | Independent conformance and supervisor policy decision |
| 75–77 | Hypothesis, predeclared contrast, ITT analysis and missing-data plan drafts | Research team/clinical/ethics/statistician decision |
| 78–81 | Dose fairness, config hashes, source provenance, challenge matrix | External protocol review and signoff |
| 82–84 | Latent model, response assumptions, exact Bayesian filtering | Calibrated observations where criterion requires them |
| 85–86 | Decline/transition oracle and false-alarm model; parameter-fitting plan | Real observations, reviewer validation |
| 87–92 | Recovery/action semantics, heuristics and POMCP reproducibility | Fair resource protocol; model remains synthetic |
| 93–95 | Formal theorem audit, counterexamples, mechanism ablation and strong baselines | Original novelty, independent scientific evidence |
| 96–97 | Authored concept/Bloom bank, separate pre/post forms | Expert content review, parallel form validation |
| 98–102 | Transfer/retention instrument outline, reviewed 55 practice, 16+16 assessment, 8 probe questions | Expert review and authorized empirical psychometrics |
| 103–106 | Leakage audit, 32 resources, fatigue drafts, signed content hashes | Independent educational/measurement review and approved content freeze |
| 107–116 | Functional three-arm synthetic engines, pre/post, budgets and fatigue events | Already synthetic-implemented, not human evidence |
| 117–120 | Browser/security/persistence/access/timestamp audits, privacy packet | User/independent security review and institution authority |
| 121–123 | Pseudonymized export and 3-arm mock replay | Institution-approved real-data analysis, actual trial where required |

## External reviewers: ready-to-send request outline

**Subject:** Request for independent methodological/content review — adaptive Behavioral Economics tutoring research

Hello,

We are preparing a research study on adaptive, resource-constrained pedagogical interventions across eight Behavioral Economics concepts. We have a reproducible synthetic prototype and draft educational materials, but we are **not yet authorized to recruit participants** and have not validated the assessment bank.

Would you be willing to review the attached material **within your expertise**, documenting substantive errors, content adequacy, learner-level suitability, answer/rationale correctness, and any limitations? We would appreciate a dated review record, clear revision requests and an explicit decision scope; please do not approve anything outside your expertise. A separate institution-led research/ethics review will be required before a human study.

Thank you for considering the request.

## Hard STOP conditions

- No overwriting of source CSVs, existing test records, code hashes, or prior negative outcomes.
- No fake review decisions, names or dates; no changing the rubric to make 100%, and no claiming Bloom creation or psychometrics from MCQs.
- No heldout access before candidate+protocol+analysis freeze and signoff.
- No participant recruitment or data capture without institutional legal/ethical permission.
- If a structural audit detects issues besides pending review, **fix the content**, not the checker.
