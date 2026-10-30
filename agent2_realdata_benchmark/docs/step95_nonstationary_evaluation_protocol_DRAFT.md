# Step 95 — Paired Nonstationary Stress Benchmark (PROVISIONAL)

**Status:** DEVELOPMENT STRESS-TEST ONLY. NOT FROZEN. NOT A HUMAN EXPERIMENT.

## Question

When the data-generating synthetic learner can forget, and the policies assume
stationarity, do guarded POMCP actions outperform original POMCP and fixed,
greedy, or heuristic-remediation policies under matched resource opportunities?

No superiority is assumed. Negative outcomes must be reported. This benchmark
is *not* itself a novel algorithm or evidence that the assumptions fit humans.

## Fixed synthetic models

The source file `scripts/step95_nonstationary_heldout.py` is authoritative.
The exogenous `Scenario` tuples (forgetting probability per concept per
action, observation slip, relative learning-rate scaling) are:

- `stationary_nominal`: 0.00, 0.10, 1.0
- `slow_forgetting`: 0.02, 0.10, 1.0
- `rapid_forgetting`: 0.08, 0.10, 1.0
- `noisy_slow_forgetting`: 0.02, 0.25, 1.0
- `weak_learning`: 0.02, 0.10, 0.5

All are hypothetical assumptions, not estimated from educational data.
The actual observation model's guess probability is fixed at 0.25.
Each concept starts mastered independently with probability 0.25.

## Comparison policies

- `fixed`: fixed round-robin concept sequence, practice only
- `greedy`: highest model-expected immediate practice gain, no recovery resources
- `heuristic_recovery`: lowest belief concept, WORKED_EXAMPLE if belief <0.35
  and budget remains, otherwise practice; **illustrative** heuristic and not
  a verified reproduction of the supervisor's historical rule-based algorithm
- `v3`: original eight-concept POMCP search
- `v5`: opt-in positive-belief-support guarded V3 planner

Policy decisions use eight beliefs and remaining resources only. The latent
state, true future forgetting draws, and answer key are not provided to the
policy. All policies use the same nominal `GenerativeAssumptions`, and hence
are misspecified when the synthetic environment forgets or changes its slip
or learning rate.

## Fairness and information restrictions

- Each policy gets **20 + 20 + 15** decision opportunities across three
  sessions and up to two optional resources per session.
- Resource usage is recorded; policies differ in whether they elect to use
  those resources, and that is an experimental treatment difference.
- Costs are subtracted from the nominal terminal-mastery fraction; these costs
  are arbitrary model constants, not empirically calibrated time or money.
- Deterministic exogenous uniforms are keyed by synthetic participant seed,
  step, concept and event type; random draws can be shared for identical
  potential events across policies.
- **Observational trajectories are policy-dependent**, so this is NOT a
  same-trajectory/off-policy evaluation.
- POMCP uses the same simulation count for V3 and V5; heuristic/greedy are
  cheaper algorithms, and runtime must be measured separately for any
  compute-cost comparison.

## Primary development metric

Nominal net terminal true mastery fraction:

`(# true mastered concepts / 8) - (sum of specified action costs)`

The exact synthetic true mastery is accessible to the **evaluator only**.
Its use is not an endorsement as a measured student outcome.

Additional descriptive metrics are final latent mastery, total recovery
resource actions, and latent forgetting events.

## Statistical report

Return all five policies for every prespecified scenario and V5-minus-each-
comparator paired differences across identical synthetic participant seeds.
Report a seeded, **descriptive** percentile paired bootstrap interval, with
its assumptions. Do not interpret the interval as a real-world treatment
confidence interval or the difference as educational effectiveness.

## Holdout and leakage prevention

- Development seeds begin at 100000.
- Reserved held-out seeds begin at 200000.
- The command refuses `--split heldout` without an explicit
  `--frozen-protocol-acknowledged` flag.
- **Do not run held-out evaluation now.** This flag is an operational
  reminder, not a security boundary, and cannot prevent deliberate peeking.
- Before any held-out run: commit the protocol, code and threshold decisions;
  record the Git SHA, source fingerprints, simulation budgets, scenario grid,
  primary metric, comparisons, interval procedure, decision thresholds, and
  how exclusions and failures are handled. Confirm independent reviewer signoff.
- Record the results regardless of direction. Do not change policies or tune
  parameters using held-out results and then claim the same seeds are held out.

## Significant limitations

1. A synthetic regime cannot validate forgetting or remediation in students.
2. This is a comparison of **existing candidate policies**, not a novel
   deterioration-aware controller.
3. A fixed mastery-binary model may systematically favor/disfavor different
   actions and is not psychometrically calibrated.
4. The outcome is accessible only in a simulator; it is not an independent
   exam or transfer measure.
5. The simulator does not use the reviewed educational item bank (still blank)
   and is not integrated with consent, privacy, recruitment or real assessments.
6. The paired bootstrap's seed sampling interpretation requires additional
   methodological review.
7. No generic POMCP drift theorem is established by these simulations.

## Development command

Run from `agent2_realdata_benchmark` with `.venv` active:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m scripts.step95_nonstationary_heldout \
    --split development --participants 5 --simulations 12 \
    --scenario slow_forgetting
```

Expected new focused tests: 17. Expected complete suite: 815, assuming the
previous 798 tests remain unchanged. Do NOT treat test count as scientific
progress percentage.
