# Step 101 — Step 100 full development results and scientific decision

**Recorded:** 2026-10-31. **Base source commit:** `d62c04b5daccb5b0cbb9f89babe2fb2bb03d181e`. **Status:** DEVELOPMENT-ONLY synthetic comparison, not human evidence, not novelty certification, not a confirmatory experiment.

The researcher ran the fixed 30-seed × four-scenario × four-policy benchmark after all **1,221 project tests passed**, and reported a clean working tree. The full output remains on the researcher's workstation at `/tmp/ijcai_step100_full_01.json`; this memo records values from the supplied terminal output. Full raw output has **not** been independently inspected here. Before relying on its summary, run the separate read-only Step 101 verification.

## Primary comparison: Step 99 minus V3

Metric: independent synthetic posttest accuracy across 16 response draws per fictional learner. Paired differences by learner seed; intervals are *descriptive bootstrap summaries* and should not be interpreted as confirmatory uncertainty under iterative model development.

| Prespecified environment | Paired mean | Descriptive bootstrap interval |
| --- | ---: | ---: |
| `nominal` | +0.006250 | [−0.033333, +0.045833] |
| `half_learning` | −0.018750 | [−0.056250, +0.018750] |
| `noisy_observations` | −0.004167 | [−0.029167, +0.016667] |
| `forgetting_shift` | +0.037500 | [−0.014583, +0.089583] |

**Decision:** NO-GO for a claim that Step 99 is broadly superior to V3. Means are positive in two of four stress scenarios; all four intervals include zero. Do not select the favorable forgetting case alone, rerun seeds repeatedly to discover a positive result, or disguise the full study as independent confirmation.

## What was established

- A Python implementation of finite-inventory-aware search and session warmup constraints exists and has passed the supplied regression suite.
- The comparison uses the same source-defined external simulator and finite question schedule for Step 99 and V3, rather than comparing outputs from incompatible benchmark programs.
- Thirty seed clusters in each of four synthetic scenarios produced **mixed and uncertain** outcomes; this does not prove equivalence or no effect.
- Stronger claims need an independent novelty analysis and materially different evidence. Step 99 is an implementation correction, not an established AI research innovation.

## Known experimental limitations

- Synthetic intervention effects and forgetting are assumptions, not empirically calibrated mechanisms.
- Root-action legality is matched but V3's internal rollouts ignore item depletion; Step 99's rollouts track it.
- Both experimental policies get up to six extra resources, whereas greedy and fixed receive none; those comparisons confound selection policy with instructional dose.
- First-question warmup uses a concept-only lowest-belief approximation, not exact difficulty/item-ID selection in deployed V3.
- Correctness draws use common exogenous keys indexed by absolute action step. Different numbers of resource actions can shift practice actions' exogenous keys; the pairing remains reproducible but is not an ideal matched-practice-opportunity design.
- Step 99 cannot certify drift of the executed RCT controller or measure actual learning; independent posttest outcomes are generated from hypothetical mastery.
- Existing Step 95 development evidence and the original negative V6 result have already been seen; Step 100 was not a pristine test.

## Most valuable pre-November 2 next steps

1. Verify every saved Step 100 JSON observation, scenario, seed, policy, posttest accuracy, cost, dose and published primary contrast using the read-only Step 101 audit.
2. Obtain a supervisor decision selecting one **falsifiable novel AI contribution** rather than a sequence of engineering improvements. Suggested direction to discuss, not claim: uncertainty-set constrained planning with policy-feasible actions and explicit bounds under model shift; explain precisely why existing POMDP tutoring and POMCP shielding do not already solve the question.
3. Design a **resource-dose-matched** baseline and a practice-opportunity-aligned exogenous coupling, with a documented new development protocol. Do not retroactively change Step 100.
4. Establish parameter and outcome calibration using allowed training/development data with strict cohort provenance; do not use the sealed Phase 6 test cohort for tuning.
5. Request independent mathematical proof review, educational content/assessment review, and the institution's ethics/privacy/statistical determinations. There is no authorization to run human studies.

## Closest established prior art to inspect before asserting novelty

- Rafferty, Brunskill, Griffiths and Shafto, *Faster Teaching via POMDP Planning*, Cognitive Science 40(6), 2016, DOI: `10.1111/cogs.12290` (POMDP tutoring with simulations and human experiments).
- Mazzi, Castellini and Farinelli, *Risk-aware shielding of Partially Observable Monte Carlo Planning policies*, Artificial Intelligence 324, 2023, DOI: `10.1016/j.artint.2023.103987` (risk-aware analysis/shielding for POMCP).

These two references are a **non-exhaustive** novelty screen; the planned contribution needs a broader systematic review before writing a strong originality claim.
