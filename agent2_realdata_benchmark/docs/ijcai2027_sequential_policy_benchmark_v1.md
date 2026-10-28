# IJCAI 2027 — Paired Sequential Synthetic Policy Benchmark v1

Status: Exploratory, synthetic, uncalibrated. Not a student study.

## What differs from Step 25

Step 25 estimated the quality of only the **first action**, assuming
optimal future continuation. This experiment executes complete sequential
policies, updating each policy's posterior using its own simulated probe
observations after each step, and replanning at each decision.

## Comparators

- `fixed_no_offer`: no assistance at any time.
- `fixed_hint`: always offer the hypothetical optional hint.
- `fixed_scaffold`: always offer the hypothetical optional scaffold.
- `greedy_one_step`: maximize expected immediate reward at every step.
- `pomcp_style`: replan using 300 MCTS simulations at every step.
- `exact_belief_oracle`: replan with exact belief-space dynamic programming.

The oracle knows the **assumed model parameters**, not a learner's true
latent mastery, future shocks, or private simulation outcomes.

These fixed-action baselines do not represent fixed **question order**.

## Coupling and validity

For each `(scenario, initial_belief, horizon, episode_seed)`, all policies
receive the same initial-mastery uniform and the same pre-generated uptake,
learning, and probe uniforms at each step. The policy sees only its current
belief, and never receives latent mastery or future random draws.

The planner uses independent, stable SHA256-derived RNG seeds. Different
actions can legitimately change the learner's latent state and responses.
The experiment maintains common random numbers even when action-dependent
RNG consumption would otherwise differ.

## Outcomes

- Full-episode **discounted return** = discounted correctness minus
  discounted assistance-offer costs.
- Independent synthetic probe correctness at each planning step.
- Assistance offer and simulated uptake counts.
- Un-discounted offer burden and planner runtime (separate outcomes).
- **Paired differences** in realized discounted return relative to the
  same-shock no-offer and exact-oracle policy episodes.
- Bootstrap intervals resample episode **seed clusters**, retaining the
  fixed belief grid. These express synthetic simulation uncertainty,
  not empirical student uncertainty or uncertainty in model parameters.

The oracle is optimal in **expected model value**, not guaranteed to win
on every finite set of stochastic rollout samples.

## Run

From the `agent2_realdata_benchmark` directory:

```bash
python -m pytest -q tests/test_ijcai2027_sequential_policies_v1.py
python -m scripts.ijcai2027_sequential_policies_v1 --quick \
  --output "$HOME/ijcai2027_outputs/sequential_smoke_v1"
python -m scripts.ijcai2027_sequential_policies_v1 \
  --output "$HOME/ijcai2027_outputs/sequential_full_v1"
```

The full default is 4 scenarios × 4 initial beliefs × 3 horizons ×
100 episode-seed clusters × 6 policies = **28,800 policy episodes**.
The quick run uses 5 seeds, yielding **1,440 policy episodes**.
The script refuses to overwrite existing result directories.
Outputs are `episodes.csv`, `summary.csv`, and `manifest.json`.

## Limitations and next steps

This is still the synthetic single-skill model with one independent
observation **after each** action, not the real four-question browser
schedule with one final independent probe. The POMDP has hypothetical
hint/scaffold actions, not the browser's concept summary, and its guessing
parameter differs from browser BKT. Intervention effects and uptake are
assumptions, not estimated from real learners.

The POMCP implementation is history-indexed MCTS; it does not maintain
persistent particles between real observations. The simulated oracle is
model-optimal, not an oracle of actual learning outcomes.

After inspecting paired full-episode results, conduct robustness tests
under misspecified transition/observation/uptake parameters and compare
policies on a simulator that matches the actual instructional sequence.

Do not recruit students or open held-out evaluation artifacts.
