# Step 100 — Predeclared **development-only** paired policy comparison

**Date:** October 31, 2026. **Status:** experimental design frozen *before running this new Step 100 simulator*. This is NOT a confirmatory preregistration, not an estimate of real-student effects, and not evidence of algorithmic novelty. Prior V6 negative development results and V3 counterexamples are already known.

## Question

In a common, finite-inventory **hypothetical** learner environment, does a POMCP-style planner whose future rollouts consume question inventory (Step 99) produce better independent synthetic posttest performance than original V3's planner, which fixes root-legal concepts throughout search?

This comparison isolates a **planning-model implementation difference**, but not all possible effects of simulation noise, offered resource dose, or item-level policy choice.

## Policies and fairness

1. `step99`: immutable Step 99 inventory-aware planner with 240 root simulations, horizon 3.
2. `v3`: original `EightConceptPOMCP` unchanged, 240 root simulations, horizon 3. At **execution time**, it receives the same actually remaining concept set and two-resource-per-session budget as Step 99; only internal V3 rollouts omit inventory depletion.
3. `greedy_no_resource`: every question targets the lowest current BKT mastery estimate; zero resources (a teaching-dose control, *not* matched-dose).
4. `balanced_fixed_no_resource`: no adaptive decisions or resources; the same 55-question inventory in the interleaved original fixed-order schedule (a teaching-dose control, *not* matched-dose).

For `step99` and `v3`, force a first **practice** question each session using the same lowest-belief deterministic concept choice, before invoking either POMCP planner. This is a reduced-concept approximation to the operational V3 warmup, whose item-level difficulty and item ID tie-breakers are not simulated. Both have at most two recovery resources per session and exactly 55 practice questions, every practice question consumes an inventory slot, and both receive the same hypothetical transition rates and costs in their internal planners. Both use same simulation count and choice seed. Do **not** substitute Step 99 into the human RCT.

## External simulator: identical for all policies

- Exactly eight Boolean latent mastery concepts, initial mastery probability 0.20 per concept, *not calibrated to students*.
- Sixteen independent pretest responses (two/concept) initialize BKT posterior for each concept, but do not change latent mastery; pretest observations are drawn from the external environment and share the same learner/exogenous keys across policies.
- 20/20/15 practice-question schedule. Optional recovery resources do not consume one of the 55 questions. A `DROP_2` response is observed and updates BKT without consuming practice inventory; plain text resources offer no observed correctness. All resources are assumed completed; real skips and consent/withdrawals are not modeled.
- Each action targets one concept, response (if any) occurs *before* the learning transition. All policies use the same `BKT()` posterior-update convention in their observable policy state.
- **Common random numbers by seed, scenario, absolute action index, target concept, event type**, preserving exogenous coupling without exposing latent truth to the planners. Policy trajectories may diverge legitimately.
- Model-specified costs and opportunities are hypothetical. No participant-level real data, ASSISTments labels, or sealed held-out seeds are accessed.

## Fixed scenarios, chosen without viewing Step 100 outcomes

- `nominal`: learning rates equal planner assumptions, slip .10, guess .25, forgetting 0.
- `half_learning`: actual learning rates half planner assumptions, slip .10, guess .25, forgetting 0.
- `noisy_observations`: planner rates unchanged, actual slip .25, actual guess .35, forgetting 0.
- `forgetting_shift`: planner rates unchanged, actual slip .10, guess .25, and per-action per-mastered-concept forgetting .005.

These are stress tests, NOT estimates of actual forgetting, learning effects, or pedagogical relevance.

**Development seeds:** 150000..150029, 30 paired synthetic learners per scenario. A quick smoke run may use the first two and fewer planner simulations; it is NOT part of the scientific comparison. Any seed >=200000 is prohibited. Prior negative V6 development findings have informed this line of inquiry, so do not treat Step 100 or any rerun as untouched confirmation.

## Outcomes (fixed before reading results)

- **Primary descriptive contrast:** paired `step99 - v3` difference in independent synthetic posttest correctness (16 items, same externally keyed posttest draws per learner/policy).
- Report mean, seed-cluster descriptive bootstrap interval (two-sided 95%, deterministic bootstrap RNG) and wins/ties/losses; intervals are NOT nominal confirmatory coverage under iterative development.
- Secondary: final *simulated* true mastery fraction (oracle diagnostic only, NEVER given to policies); total offered/completed assistance resources; nominal total model cost; step count; POMCP decisions and runner duration.
- Additional exploratory contrasts with greedy/fixed: clearly mark unmatched treatment/resource dose. Report all four scenarios including negatives, never hide them.

## Before paper claims

Requires research-reviewer signoff; a truly new method relative to prior POMDP tutoring and risk-aware shielding; models calibrated to external data without contamination; fair dose-matched comparisons; independent test cohort(s) not tuned upon; realistic item difficulty/IDs and respondent behavior; mathematical claims about the actual executed policy. In particular, passing 1,200+ tests establishes software integrity only, **not evidence that Step 99 improves learning**.

If Step 99 fails to improve the predeclared primary contrast, preserve that failure; do not alter simulation weights and reframe it as confirmatory evidence.
