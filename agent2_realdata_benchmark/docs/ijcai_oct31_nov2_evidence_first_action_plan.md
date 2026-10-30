# IJCAI 2027 — October 31 to November 2 evidence-first research sprint

**Release status:** DRAFT technical plan, no human-study authorization, no supervisor review implied.

**Authoritative starting point:** original Steps 72–123 closure register, remote branch `feature/ijcai2027_prototype` at `929e19e`, user's 1,097 green tests, original Phase 6 student split (2,951 train / 633 validation / 633 test), exploratory 60/20/20 Step 95 split and follow-up overlap diagnostic.

## Critical discovery: two incompatible partitions of the same ASSISTments dataset

The original Phase 6 test cohort has **633 students**. The newer Step 95 60/20/20 hash allocates:

| Phase 6 source | Step 95 train | Step 95 development | Step 95 sealed | Total |
|---|---:|---:|---:|---:|
| Phase 6 train | 1,784 | 598 | 569 | 2,951 |
| Phase 6 validation | 378 | 139 | 116 | 633 |
| **Phase 6 test** | **387** | **116** | **130** | **633** |

Thus the *already completed* Step 95 exploratory run used responses from **387 former Phase 6 test students to select parameters**, and responses from **116 former Phase 6 test students in development scoring**. One cannot retroactively claim that run respected the original Phase 6 test barrier. A new Phase 6 TRAIN/VAL-only **re-analysis** can establish which development claims survive the correction, but does not unexpose prior decisions. The original Phase 6 validation cohort was itself previously accessed for other model selection; it is therefore **development data** and not a fresh independent test.

Never change membership lists, overwrite Phase 6 test files, access Phase 6 test labels for this reanalysis, or report the older Step 95 60/20/20 test cohort as a pristine independent test of all Phase 6-related work. Preserve the earlier result and overlap table verbatim as exploratory history.

## P0 — Do immediately on Saturday Oct 31 (preferably today)

1. **Preserve original state**: `git status --short`, `git rev-parse HEAD`, `git diff --check` and `python3 scripts/step72_123_progress.py`; record the printed results. Original 1,097 tests passed at commit `929e19e`. Store output snapshots in `/tmp` and version any explicitly approved, sanitized evidence separately. No raw student datasets in Git.
2. **Install add-only package** (this bundle). Run focused tests, then `python3 -m scripts.step95_phase6_safe_reanalysis --input ... --splits data/splits/assist2009 --output /tmp/...json`. The script strictly validates all Phase 6 student membership lists, skips Phase 6 TEST rows before label parsing, fits a constrained grid on Phase 6 TRAIN only, and scores on Phase 6 validation only.
3. **Read both the tuned and the fixed-matched results**. Preserve both positive and negative contrasts, with log loss, Brier and descriptive student-cluster intervals. Note that the matched-fixed experiment is a post-hoc sensitivity analysis, not confirmatory evidence.
4. **Run the original 52-step backlog reporter** to print exact unresolved acceptance criteria, not invented substitutes. Pay attention to surprising historical credits on rows marked `SYNTHETIC-IMPLEMENTED` whose actual `exit_criterion` requires supervisor/sponsor signoff (notably Step 74 and Step 123). The published 55.8% is a *subjective, possibly optimistic* proxy, not completion of those exit conditions.
5. **Freeze a short candidate-claim memo**: one specific claim for response prediction; a separate claim for novel decision making (if any); explicit ablations and assumptions; external review needed. No implication that BKT + forgetting, POMCP, or uncertainty-triggered resources are inherently original.

## P0 — Saturday Oct 31: decide algorithmic contribution

- **Identify the primary research object**, not an unbounded patchwork of V3, V5 and V6. The synthetic V3 planner has no unconditional healing theorem; V5's zero-gain safeguard was inactive in typical synthetic trajectories; V6's recovery-specific ablation previously showed near-zero or negative incremental effect. Preserve these negative results.
- Write a single methods table with input state and observations, resources, time/budget cost, comparator, exact intervention effect assumptions, and the policy's observable information set. No access to simulated latent state during decisions.
- Propose and scrutinize a *specific* novel advance: e.g. identifiability-aware conservative control under uncertain response/uptake, **only if it has a nontrivial theorem or measured advantage** over POMCP, greedy, and identical-controller/no-recovery baselines. Merely adding a filter and a threshold is not a defensible main-track novelty argument.
- Independently examine prior work: Bayesian knowledge tracing, forgetting-aware KT, Bayes-adaptive/budget-constrained POMDPs, POMCP, active teaching, uncertainty-triggered interventions. Cite concrete technical distinctions (not keyword-level novelty).
- Keep any synthetic confirmatory seeds starting at `200000` sealed until candidate algorithm, endpoints, sensitivity ranges, comparators and analysis plan have been frozen and reviewed. Similarly do not use original Phase 6 TEST labels to iterate the current benchmark.

## P1 — Sunday Nov 1: close internally verifiable requirements

- **Steps 72–73, 78, 88:** exact common action/observation contract and pseudocode for A/B/C; matched instructional dose, opportunity costs and all actions' state transitions. Treat an independently reviewed signoff as still outstanding until obtained.
- **Steps 79, 83, 85–86, 93–95:** observed deterioration ≠ latent forgetting; quantify calibration, misses/false alarms, and cost under misspecification; preserve exact counterexamples and report no unsupported global drift guarantee. Original `Step 95` exit criterion additionally requires paired multi-seed outcomes/time/cost ablations with confidence intervals and independent reproduction. Predictive ASSISTments results alone **do not close Step 95**.
- **Steps 80–81, 103, 106:** immutable source/parameter/seed/split provenance, assessment/practice leakage checks and defensible content freeze *proposal*. Do not call content approved while 127 independent reviews are pending.
- **Steps 117, 119–120, 122:** local synthetic crash/restart and concurrency tests, timestamps and integrity, export/deletion threat model, accessibility/security issues. These cannot substitute for external penetration tests, institutional privacy review or approved hosting.
- **Steps 96–106:** 95 content drafts, 32 recovery drafts and eight constructed-response creation prompts exist, but the pre/post forms and all 127 content records still require genuine expert review, pilot reliability and construct checks. Review all eight `create` prompts and response rubrics for the intended use. A valid authored draft is not a validated instrument.

## P2 — Monday Nov 2: honest release and go/no-go

1. Re-run full `pytest -q -p no:cacheprovider`, progress register, content audits, semantic audit, current real-data aggregate report and synthetic decision ablations. Capture exact commits, hashes, datasets, parameter grids, and reproducible outputs; keep all negative results.
2. Request **real external decisions**, using the review packet already prepared: supervisor policy identity and primary hypothesis; statistical estimand/multiplicity; behavioral-economics specialist for all items/resources; measurement specialist for pre/post equivalence and fatigue; privacy/DPO and ethics; independent architecture/security reviewer. An email request is **not a signoff**.
3. Audit every one of the **52 original exit criteria**. Upgrade none solely because an additional script or drafted artifact exists. The score's current labels were 19 synthetic-implemented, 20 partial, 13 external-required; even converting all 20 partials to full credit yields at most **75.0%**, not 100%, without the 13 external requirements. Several supposedly credited items still lack required final approval, so even 75% is not guaranteed.
4. Deliver four appropriately scoped artifacts: (i) full researcher-facing technical report with limitations; (ii) reproducible synthetic software and immutable evidence; (iii) **draft** content and reviewer request package; (iv) novelty decision and explicit next experiment. **NO-GO** for human participant deployment without approvals and **NO-GO** for broad "self-healing recovery efficacy" claims until supported.
5. If the claim cannot meet IJCAI main-track standards, make a scientifically sensible pivot rather than fabricating a positive result. The eventual submission may instead be on rigorous **limits of detection and safe control** if a genuinely original theorem and robust experiments exist. No claim of novelty without a careful prior-art comparison.

## Minimal handoff request to independent reviewers (ready to customize)

**Subject:** Independent review request — adaptive Behavioral Economics tutoring research

We have a synthetic experimental prototype and an author-produced draft bank of 95 questions, 32 recovery resources and eight constructed-response tasks. We are seeking separate independent reviews of (a) Behavioral Economics accuracy, items and explanations, (b) assessment construct and pre/post comparability, (c) the proposed controller and its mathematical assumptions, and (d) study privacy/ethics and institutional authorization. Please record specific corrections and a dated, attributable decision only for the scope you actually review. We will not recruit real participants or mark your review as approved until the appropriate authorization is documented.

## Privacy and claims stop conditions

- Never paste student-level logs or membership IDs into chat or commit them to a public repository.
- Never copy the original Phase 6 TEST response labels into Step 95 TRAIN/VAL reanalysis.
- Never change the definition of the primary endpoint after inspecting held-out data; document all exploratory decisions.
- No fabricated review records, names, dates, psychometric reliability estimates, consent or ethics approvals.
- Real ASSISTments next-response prediction **cannot identify recovery's causal impact** and does not validate Behavioral Economics transfer.
- Source hashes and reported score metrics are *evidence provenance*, not proof of original mathematical novelty.
