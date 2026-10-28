# IJCAI 2027 — Synthetic Planner First-Action Benchmark v1

Status: Local-only, uncalibrated, exploratory protocol implementation.

This experiment compares the first decision only. All candidate choices are
scored against the exact solver's `Q*(belief, first_action)`, which assumes
optimal continuation *after* that first choice. Results are **not** a direct
comparison of full sequential policies or real-world learning improvements.

## Policies

- `fixed_no_offer`: always chooses no assistance at the first decision.
- `fixed_hint`: always proposes a hint at the first decision.
- `fixed_scaffold`: always proposes a scaffold at the first decision.
- `greedy_one_step`: exact one-step expected utility under the same model.
- `pomcp_style`: existing history-indexed belief-sampling tree search.

All use the same synthetic model, action set, observations and action costs.
The `fixed_*` comparators represent fixed *first actions*, not fixed item order.

## Scenarios

- Baseline: existing illustrative synthetic parameter set.
- High cost: hint cost .35 and scaffold cost .40.
- No effect: intervention increments zero; positive costs remain.
- Zero effect/zero cost: deliberately tied actions to validate tie-aware metrics.

`no_offer` must be optimal in the no-effect scenario; all first actions must
have identical optimal Q in the zero-effect/zero-cost scenario.

## Run

From `agent2_realdata_benchmark`:

```bash
python -m scripts.ijcai2027_planner_comparison_v1 \
  --quick --output "$HOME/ijcai2027_outputs/planner_comparison_smoke_v1"
python -m scripts.ijcai2027_planner_comparison_v1 \
  --output "$HOME/ijcai2027_outputs/planner_comparison_v1"
```

The output directories must not already exist. They contain `decisions.csv`,
`summary.csv`, and `manifest.json`. Keep raw experiment outputs separate
from tracked source changes pending supervisor protocol review.

## Analysis

- Exact-action agreement reports identity with the solver's canonical tie-break.
- Optimal-equivalent rate permits actions within `1e-9` of the best exact value.
- First-action regret uses exact Q differences, not noisy tree-estimated values.
- A 1,000-draw seed bootstrap summarizes planner-RNG variability conditional
  on the fixed initial-belief × horizon grid, **not** uncertainty about students.
- Runtime measurements depend on hardware, Python interpreter and machine load.

## Caveats

The synthetic POMDP does not represent the real quiz's single final probe or
its `concept_summary` resource. Its guessing parameter differs from browser
BKT. Simulation effects and assistance uptake are assumptions. Matching
first decisions does not establish effective self-healing or educational gains.
The frozen Phase 6 artifacts and held-out evaluation gate remain untouched.
