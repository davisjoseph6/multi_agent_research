# IJCAI 2027 — Step 102: predeclared exactly matched practice-only ablation

**2026-10-31.** Exploratory DEVELOPMENT-only protocol. Written **before** any Step 102 result. This does not create a pristine cohort, preregistration, human-study authorization or established novelty. The prior V6 and Step 100 outcomes are already known. **Do not overwrite or change Step 100 source or reports.**

## Scientific question

Is the Step 99 inventory-consuming internal search measurably different from unchanged V3 internal search **when instructional exposure is exactly equalized** and both policies are prohibited from offering extra recovery resources?

This deliberately removes the effect of differential recovery-resource exposure so we can examine the specific *practice question-selection* difference. A null result would imply Step 99 has not shown an advantage in this simplified setting, not that inventory matters in every realistic learner model.

## Fixed policy comparison

- `step99_practice_only`: original Step 99 POMCP internal inventory-consuming search; at policy selection, explicitly represent zero remaining resource slots. **Do not modify original Step 99 source.**
- `v3_practice_only`: original V3 POMCP internal fixed-root-action search; pass the **same** currently available practice concepts, zero recovery slots and no resource actions. **Do not modify original V3 source.**
- Both use a common greedy-by-BKT-concept first QUESTION warmup per session, mirroring the approximation declared in Step 100.
- Both must execute **exactly 55 practice questions, zero resource actions**, divided 20/20/15. The external environment, BKT observation updates, assumed transition/reward parameters and independent 16-item posttest are the same as frozen Step 100. This yields equal question count, equal nominal action cost and equal number of chances for per-action forgetting. It does not equalize *which* concepts are targeted or their hidden effectiveness.
- At any decision, no policy gets latent learner states or posttest outcomes.

## Development evaluation

The same four prespecified Step 100 environments, and 30 *reused* learner seeds 150000–150029 per scenario; this is not independent evidence. Both use 240 MCTS simulations, horizon 3, and the exact same policy-choice seed. Quick smoke runs use 2 seeds and 48 simulations. The new script must pass a **parity check** that its external episode evaluator reproduces the frozen Step 100 original V3/Step99/greedy outputs exactly for a few development cases, prior to accepting comparisons.

## Endpoints and analysis

- Primary descriptive outcome: paired `step99_practice_only − v3_practice_only` **independent synthetic posttest accuracy** (16 independent correctness draws per learner).
- Secondary: final simulated latent mastery, number of different question selections in the same paired learner (if logged without revealing latent truth), nominal cost, number of practice questions, and POMCP invocation count.
- For each scenario report mean paired difference, wins/ties/losses, and a descriptive seed-bootstrap interval using the frozen Step 100 `paired_contrast` implementation.
- A claim of consistent benefit **cannot** be supported if any scenario has nonpositive mean or the corresponding descriptive interval includes zero. Passing all does not make it a confirmatory result; it only justifies new independent evaluation and prior-art review.
- All scenarios and unfavorable results must be preserved. No tuning over old or sealed seeds; seeds ≥200000 are prohibited.

## Explicit boundaries

This experiment is about **question-order policy differences without recovery**. Even a favorable result does not support the advertised self-healing claim, because there are no recovery actions. Properly evaluating recovery must eventually use a predeclared **dose/time-matched recovery comparator** with independently justified instructional effects, a realistic heldout design and institutional approval for human studies.

Closest prior work to screen before asserting novelty:

- Rafferty et al., *Faster Teaching via POMDP Planning*, Cognitive Science 2016, DOI 10.1111/cogs.12290.
- Mazzi et al., *Risk-aware shielding of Partially Observable Monte Carlo Planning policies*, Artificial Intelligence 2023, DOI 10.1016/j.artint.2023.103987.

**Expected disposition:** the original Step 100 effect is currently mixed, so report uncertainty without inventing an improvement.
