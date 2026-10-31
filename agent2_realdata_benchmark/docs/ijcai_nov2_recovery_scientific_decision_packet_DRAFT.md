# IJCAI 2027 — October 31 / November 2 scientific decision packet

**Current checkpoint:** checkout `feature/ijcai2027_prototype`, local commit `1597fd6`, user-reported 1,114/1,114 passing full regression tests. Original 52-step subjective credit: **29/52 = 55.8%**. No human participant authorization, expert educational review, calibrated intervention effects, or paper novelty established.

## Already verified — preserve without upgrading claims

- Real ASSISTments data: corrected, UTF-8-reencoded source CSV SHA-256 `1309321c8673591da65cc8e456cd0561d275e82b09d6b0667c84e30518a0d522`; source encoding conversion was handled without deleting records.
- Frozen Phase 6 partitions: 2,951 TRAIN students, 633 VAL, 633 TEST. Original 633 TEST outcomes **not evaluated** in the latest reanalysis. The earlier independent 60/20/20 Step 95 split exposed 387 original TEST students for training and 116 for development, hence it cannot be considered independent of prior Phase 6 research.
- Reanalysis Phase 6 VAL 45,488 responses: constant Brier `.22438970550048787`, no-forgetting train-selected Brier `.21800739845912237`, forgetting train-selected Brier `.21190363562287934`; paired forgetting-minus-no-forgetting difference `-.006103762836243032`, descriptive student bootstrap interval `[-.007603368629813052,-.004571821752687569]`.
- Matched observation/learn parameters with forgetting `.08` versus `0`: Brier difference `-.00644821311637081`, descriptive interval `[-.00834174565642764,-.004542933287334338]`.
- These results are **exploratory on previously used Phase6 validation**, and demonstrate only that observed response predictions improve in this specification. They do not identify real latent forgetting or causal recovery effects.
- The prior 1,142 mechanical content issues were reduced to 381 independent-review failures: 127 draft items/resources × 3; 95 draft questions, 32 draft resources, and 8 constructed-response CREATION tasks exist, but the 8 MCQ CREATE warnings remain because the actual runtime has not been replaced. No educational review is approved.

## P0: V6 ablation — single most informative next execution

Run `scripts.step95_nov2_recovery_decision` on all **five original hypothetical scenarios**, default 30 development seeds per scenario. This calls the EXISTING `scripts.step95_v6_mechanism_audit.audit`, independently checks V6 replay parity, and compares against **no-recovery with the same controller**, as well as `fixed`, `greedy`, `no_risk_credit`, and `no_coverage_weight`. The action and observation semantics are those already implemented in the project. No new controller is silently introduced.

The conservative screening rule is declared as follows:

> For every one of the five existing scenarios, V6 minus no-recovery must have positive mean *nominal net mastery*, **and** the descriptive paired-bootstrap interval lower bound must exceed zero.

This is a **development-stage screening convention**, not a valid frequentist familywise hypothesis test: the policy and settings have been developed on these same scenarios, and the bootstrap intervals do not correct for model/parameter selection. Failing the screen means **do not assert a general beneficial V6 recovery mechanism**, not that the model is fundamentally impossible or that no future design could work. Passing likewise does not validate the real-human policy or establish novelty.

The script emits every negative and positive scenario, raw scenario aggregates, complete ablation contrasts, posthoc simulator-truth trigger diagnostics, and SHA-256 of execution-source modules. It will not access held-out synthetic seeds (start 200000); it does not open real student-level records. Preserve JSON before moving to another candidate.

## Research hypothesis / math choices — must resolve with supervisor

A viable paper contribution needs a narrow, falsifiable object, e.g.:

- **Option A:** an *identifiability-aware conservative* treatment decision when action uptake and educational benefit are unknown; a novel theorem or performance advantage beyond existing robust/Bayes-adaptive constrained POMDPs is required. A familiar threshold rule or reimplementation of POMCP does not constitute novelty.
- **Option B:** a rigorously characterized *failure mode* of observation-only deterioration detection, a provable validity boundary, and demonstrably effective correction. A counterexample alone is generally not enough for IJCAI; quantitative external verification is needed.
- **Option C:** a domain-specific experimental method if there are truly new technical components and replicable performance that do not depend on fabricated latent rewards. The current student-response data do not contain randomized resource-effect labels.

All three possibilities are hypotheses for research scoping, **not claims that a novel contribution has already been achieved**.

### Mathematical anchor: one-step robust improvement cannot be assumed

Suppose current mastery belief is `b`, practice learning probability is `p`, recovery learning probability is `r`, and treatment costs are `c_P,c_R`. Under the explicitly hypothetical one-step binary-mastery model, the *modeled* net advantage of recovery is

`D = (1 - b)(r - p) - (c_R - c_P)`.

If `r∈[r_min,r_max]` is only bounded, then recovery robustly dominates practice only when

`(1-b)(r_min-p) > c_R-c_P`;

practice robustly dominates recovery when

`(1-b)(r_max-p) < c_R-c_P`.

Otherwise the evidence is insufficient for robust dominance. The proof is the affine monotonicity of `D` in `r` when `0≤b≤1`. This is **elementary**, not a new IJCAI theorem or a guarantee for long-horizon POMCP. When resource uptake `u` is unobserved and learning-on-uptake probability is `theta`, many simplified observation models identify only `u*theta`: distinct `(u,theta)` pairs can have identical observable distributions. Specific identification requires extra measurements or assumptions. The current ASSISTments next-response benchmark does not identify intervention effect `r`.

## Saturation/quality gates before changing anything else

1. All decisions must use observation histories and beliefs **available at decision time**; simulated `mastered` and `forgotten_since_learning` can appear only in post-hoc diagnostics.
2. Compare raw mastery, nominal mastery-minus-cost, resource actions and exposure/fatigue separately; a single invented cost weight is not a validated welfare objective.
3. Ensure the same number of sessions and opportunities, compatible resource budget, and content difficulty under fixed, greedy and no-recovery arms. Confirm that mechanism-only ablation actually changes only one policy capability.
4. Re-run exact drift/counterexample suites and filter-path arithmetic oracle; the stronger mathematical theorem must hold for the EXECUTED policy if claimed.
5. Negative outcomes, zero-effect ablations, false triggers and unreliable observation-model assumptions are **paper results**, not errors to hide.
6. Do not use original Phase6 TEST or synthetic heldout seeds to tune V6 or choose the primary endpoint.

## Concrete weekend schedule (complete as soon as evidence permits)

**Saturday 31 Oct, P0:** Run V6 policy ablation; preserve aggregate JSON/markdown and source SHA; decide candidacy. Audit policy A/B/C identity and identical budgets. Send supervisor and independent methodological reviewer requests **today**, not on Monday. Prepare the exact 1-page manuscript claim and distinct forecast-versus-control claims. Run full pytest suite.

**Sunday 1 Nov, P1:** Address measurable engineering gaps only: Step 72 common action and outcome contract; Step 73 code-matched pseudocode; Step 78 dose/time matched evaluation; Step 83 slip/guess sensitivity; Step 86 pretest low-mastery false detection; Step 93/94 theorem/counterexample scope; Step 103 leakage tests; Step 119 restart/concurrency. Verify all results, retain counterexamples. Substantive content review by external subject/psychometrics specialists starts when collaborators are available; no fake signoff.

**Monday 2 Nov, P2:** Final independently reconcilable evidence snapshot of 52 original exit criteria (no rubric changes), code/test Git commit, source/dataset/report hashes, negative results, reviewer request log and a GO/NO-GO decision. Draft double-blind paper skeleton only after you have a defensible contribution; otherwise make an explicit research pivot. No unauthorized human study.

## External requests to initiate immediately

- **Project supervisor:** approve identity of Group A (historical rule, V3, V5, V6 or a newly frozen candidate), primary hypothesis and eligibility of a three-arm trial; review the new prediction-versus-intervention distinction. The previous convention cannot be inferred to authorize study.
- **Methods/statistician:** exact A-versus-B estimand, randomization, intention-to-treat, missing data, multiplicity, pre/post comparability, session attrition, selection biases and any prospective sample size.
- **Behavioral Economics domain expert:** 95 authored question records, 32 recovery resources, source/citation accuracy and corrections; sign individual items only after an actual review.
- **Educational psychometrician:** Bloom CREATE tasks, parallel forms, reliability and fatigue instrument; review instrument validity before any pilot.
- **Institutional data-protection / ethics authority:** consent, data access, storage/retention, withdrawal, identities, host, ethics and any institutional authorization.
- **Independent code/architecture reviewer:** design conformance, time/cost fairness, policy output leakage, POMCP history update and external reproducibility.

## Scientific GO/NO-GO by Monday (not an enrollment authorization)

- **GO to a frozen confirmatory *synthetic* protocol:** only if one specific candidate/controller and endpoints are selected, reviewer has inspected the policy and simulation assumptions, baseline comparisons reproducibly pass a predeclared screening test, provenance immutable, and prior work assessed. It does **not** automatically license heldout use; obtain actual protocol freeze/signoff before any sealed access.
- **NO-GO for general V6 improvement claim:** any violation of the all-five-scenario positive screen. Retain the negative data; consider a mathematically honest negative/limitations paper or different candidate. Do not rescue the outcome by choosing only favorable scenarios.
- **NO-GO for real participant collection:** until all applicable oversight, content, consent and privacy approvals are verifiably received. All original 13 EXTERNAL-REQUIRED and numerous partial criteria remain blocked.

## Prior art — required serious comparison before choosing novelty

- Ross et al., *Online Planning Algorithms for POMDPs* (JAIR 2008), https://pmc.ncbi.nlm.nih.gov/articles/PMC2748358/ . General online belief-space action planning predates this project.
- Ross et al., *A Bayesian Approach for Learning and Planning in Partially Observable Markov Decision Processes* (JMLR 2011), https://jmlr.csail.mit.edu/papers/v12/ross11a.html . Bayesian model uncertainty and decision making are established.
- Original POMCP (Silver & Veness, *Monte-Carlo Planning in Large POMDPs*, NeurIPS 2010): identify precisely what your controller changes beyond root sampling, UCT, a recovery budget and an observation trigger.
- Existing BKT and forgetting-aware KT: list source codes, parameter assumptions and exact architectural distinctions. A two-state HMM with forgetting is a baseline, not novel.

**Do not equate the 55.8% accounting proxy with acceptance probability.** Some nominal SYNTHETIC-IMPLEMENTED rows lack their final independent signoff and may not be genuinely closed. Expert/ethics approvals cannot be automated by a weekend package.
