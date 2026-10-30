# IJCAI 2027 / Step 75: Novelty and intervention-selection gate

**Status:** Evidence-based preliminary research review, **not** supervisor approval, not a preregistration, and not a finding of IJCAI novelty.
**Date:** 2026-10-30. **Protocol:** research-software testbed only; no authorized human experimentation.
**Verified baseline supplied by researcher:** 781 passing project tests, 55.8% provisional weighted Steps 72–123 progress. Neither is a research-validity score.

## A. What the current research actually supports

- The V3 POMCP-like planner is executable in an eight-concept synthetic model, but an exact latent-state counterexample shows a nonzero deficit with zero one-step expected decrease under a specified decision.
- V5 runs the V3 planner then applies a deterministic safeguard **only** if the original selected action has *zero* belief-expected mastery gain and another legal action has *positive* gain.
- A paired 52-case *decision* audit reported 29 safeguard interventions; a separate routine three-participant synthetic protocol reported zero guard interventions across 58 planner decisions. These are not learning efficacy experiments.
- The educational item templates are unreviewed and fail the release content audit. Researcher reported 1,142 missing/invalid content findings. No trial approval or human learning evidence is established.

## B. Exact structural result for V5: interior-belief inactivity

Let `b_j` be belief of mastery of an eligible concept, `p_a` the synthetic learning probability for an eligible action, and `m=8` concepts. The currently implemented safeguard calculates

    g(b,j,a) = (1 - b_j) * p_a / m.

If every eligible `b_j < 1` and every legal `p_a > 0`, then `g(b,j,a) > 0` for **every legal action**. V5 intervenes only when the raw action has `g <= 0` and an alternative has `g > 0`. Therefore, under these conditions, **V5 cannot intervene, irrespective of the raw POMCP decision quality**.

The default synthetic learning rates in `GenerativeAssumptions` are positive. Default BKT parameter values are `learn=.10, slip=.10, guess=.25`. In exact arithmetic, strictly interior prior beliefs remain strictly interior after finitely many admissible BKT observations with these interior parameters. Finite-precision floating-point saturation near 1 may be an exception; no numerical universal guarantee is asserted. An additional four-test regression suite verifies the stated conditions, default BKT examples, and example guarded decisions.

**Implication:** V5 as currently configured should not be marketed as a generally active self-healing intervention. Fixing a zero-gain boundary example is not equivalent to an improvement in ordinary teaching, and is not novel by itself.

## C. Prior-art risk assessment (non-exhaustive)

| Work | Established prior result | Novelty claim threatened |
|---|---|---|
| Silver & Veness (NeurIPS 2010), *Monte-Carlo Planning in Large POMDPs* | Introduces POMCP | Claiming POMCP as new |
| Rafferty et al. (Cognitive Science 2016), *Faster Teaching via POMDP Planning* | POMDPs to select pedagogical actions and compares modeled policies in simulations and human teaching | Claiming belief-space teaching alone is new |
| Tong et al., *Adaptive algorithms for shaping behavior* (published full article 2025; preprint 2023) | POMCP-style adaptive teaching/shaping with alternative heuristics | Claiming POMCP-based adaptive curricula alone is new |
| Mazzi et al. (Artificial Intelligence 2023), *Risk-aware shielding of POMCP policies* | Restricts undesirable POMCP actions using a shield | Claiming action filtering/shielding in POMCP is new |

Primary source links:
- https://papers.nips.cc/paper_files/paper/2010/hash/edfbe1afcf9246bb0d40eb4d8027d90f-Abstract.html
- https://doi.org/10.1111/cogs.12290
- https://pmc.ncbi.nlm.nih.gov/articles/PMC12448964/
- https://doi.org/10.1016/j.artint.2023.103987

This list is a novelty **screen**, not a systematic review. Additional closely related work may exist.

## D. Research contribution decision (unfrozen)

Do **not** freeze either "POMCP for adaptive quizzes" or "a zero-gain guard" as the main-track novelty claim on present evidence.

Potentially defensible *research question* (not yet a result):

> Can a budget-constrained, uncertainty-aware recovery policy under partial observability identify **actual deterioration** rather than low initial mastery, and improve a pre-registered cost-adjusted recovery objective over strong POMDP teaching and shielding baselines under **model misspecification**, without relying on an invalid global drift guarantee?

This needs a precise new algorithm, not just a rename or threshold change, and a convincing gap relative to the literature above.

## E. Minimum controlled computational evaluation before selecting the paper's claim

1. Lock **algorithm implementations** and configuration hashes, using original V3, V5, greedy, fixed, historical rule-based recovery, and any proposed new candidate. Clearly identify the three-arm human trial separately from the computational ablation comparison.
2. Define an explicit deterioration event requiring a temporal change, an outcome threshold, a fixed intervention budget, equal practice opportunities, and cost/timing accounting; distinguish all these from the static baseline deficit `D`.
3. Split **development** scenarios from **held-out evaluation** scenarios. Include at least nominal, shifted transition rates, misestimated mastery beliefs, changed observation noise, no-learning, fatigue/cost stress, and finite-budget exhaustion.
4. Use many independent learner/environment seeds; log seed assignment, environment and policy versions, resource consumption and elapsed decision time. Do not interpret shared integer seeds as proof of mathematically perfect counterfactual pairing.
5. Report mean and distribution of held-out independent post-assessment score, *actually observed* recovery success and time, intervention frequency, resource cost, planning latency, and failures. Include uncertainty intervals and the method used to compute them.
6. Include ablations of planner, uncertainty handling, trigger, resource budget, fallback, and new mechanism. Publish null/negative scenarios and distinguish simulated effects from real educational evidence.
7. Recheck novelty against the closest available implementations and peer-reviewed articles before authoring a definitive contribution statement.

**Go/no-go gate:** The primary research claim is **not frozen** until an identified novel mechanism is implemented, distinct from prior art, independently reproduced on held-out computational conditions, and reviewed by the research team. A completed educational item bank, psychometric calibration, sponsor approvals, and independent security/privacy audit remain separate blockers to genuinely completing Steps 72–123 as a study-ready program.

## F. Evidence boundaries

- Four new focused tests check a mechanistic property of V5; they do not prove superiority, educational effectiveness, or publication novelty.
- Any future claims of finite-horizon drift must satisfy assumptions of the **actually executed policy**. V3 currently has a documented counterexample.
- **No fabricated expert reviews, consent, psychometrics, or RCT data.** Do not raise the official 52-step closure percentage merely because a draft novelty screen or test file was added.
