# IJCAI 2027 — Synthetic Model Misspecification v1

Status: exploratory synthetic simulation. Not validated or authorized for student research.

## Question

How do complete-episode recovery-policy outcomes change when the learner
transition, uptake and observation mechanisms differ from those assumed by
the planner?

## Trust boundaries

- **Planner model**: provides belief updates and action planning.
- **Environment model**: generates simulated uptake, latent learning,
  independent synthetic probe outcomes and realized action costs.
- The planner never receives true mastery, realized uptake, hidden random
  shocks, or environment parameters.
- **Environment-informed exact** is an explicitly information-advantaged
  idealized diagnostic that knows environment **parameters**, not the
  learner's latent mastery. Do not treat it as a deployable comparison policy.

## Seven prespecified synthetic variants

- `baseline_matched`: planner and environment are baseline model.
- `baseline_effect_overestimated`: planner assumes baseline gains; real
  synthetic intervention increments are zero.
- `high_cost_matched`: planner and environment agree on high costs.
- `high_cost_effect_overestimated`: planner assumes high-cost gains;
  environment intervention increments are zero.
- `high_cost_low_uptake`: environmental uptake probabilities are 0.2 and 0.1.
- `high_cost_guess_shift`: environment guessing probability is 0.25,
  while the planner assumes 0.20.
- `high_cost_combined_adverse`: environment has weaker effects, lower
  uptake, and 0.25 guessing probability simultaneously.

All numerical parameters are hypotheses for simulation, not estimates.
These variants are stress cases, not a representative real-world distribution.
The environment cost is the same as the planner cost in this version.

## Matched episode design

The same `(initial_belief, horizon, seed)` determines identical external
uniform shocks for every policy and for each scenario variant. Planner
randomness is independently seeded. Variants with a shared planner model
use a shared planner RNG label; no environment model information is leaked.

Every decision is followed by an independent synthetic probe. This is NOT
the browser's current schedule with one final independent probe.

For all policies except the environment-informed reference, posterior
updating uses the **planner** likelihood and transition parameters,
even when these are misspecified. Rewards are determined only by the
environment's realized probe correctness and offer costs.

## Policies and outcomes

Existing fixed no-offer, fixed hint, fixed scaffold, myopic greedy, POMCP-style
and planner-model exact policies are supplemented by an idealized
`environment_informed_exact` reference.

Primary measurement is complete-episode discounted synthetic utility:
correctness minus offer cost, using the same 0.95 discount and policy actions.
We additionally report correctness, offers, simulated uptake, costs, timing,
paired differences against greedy, no-offer and the idealized reference,
and seed-cluster bootstrap intervals conditional on the chosen synthetic grid.

The idealized reference is optimal in expected value under its model;
finite-sample realized returns may nevertheless be worse than those of
another policy on particular matched shocks.

## Run

From `agent2_realdata_benchmark`:

```bash
python -m pytest -q tests/test_ijcai2027_model_misspecification_v1.py
python -m scripts.ijcai2027_model_misspecification_v1 --quick \
  --output "$HOME/ijcai2027_outputs/misspec_smoke_v1"
python -m scripts.ijcai2027_model_misspecification_v1 \
  --output "$HOME/ijcai2027_outputs/misspec_full_v1"
```

Default full grid: 7 scenarios × 4 initial beliefs × 3 horizons ×
60 seed clusters × 7 policies = **35,280 episodes**. The quick run uses
3 seeds = **1,764 episodes**. Outputs remain outside the repository;
existing output directories are never overwritten.

## Scientific limitations

This experiment tests a synthetic belief-space planning algorithm against
predeclared assumed failure mechanisms. It does not measure effects on
students, certify pedagogical recovery, or establish causal gains.

The planner has optional hint/scaffold actions; the browser provides a
concept summary. The observation noise and assessment schedule are not
calibrated to the browser. There is no validated human learner model.

Do not modify frozen Phase 6 research artifacts, open held-out test data,
recruit participants or turn on POMCP-driven student-facing assistance.
