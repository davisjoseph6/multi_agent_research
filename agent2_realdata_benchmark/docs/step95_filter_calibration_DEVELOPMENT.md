# IJCAI 2027 — Step 95 / Bayesian-filter calibration development audit

**Date:** 2026-10-30. **Status:** DEVELOPMENT-ONLY independent analytical reference, **not** a frozen confirmatory result, validated human model, completed Step 95, or supervisor sign-off.

## 1. Why this audit exists

The repository's `step95_bayesian_forgetting_filter.py` is documented as an exact two-state learning-and-forgetting Bayesian filter. Its 22 existing tests and its `CCWW` probe establish important implementation properties, but correctness of a Bayesian update **given assumed rates** does not imply that the resulting probabilities will be calibrated in the educational population or under misspecification.

This additive audit creates an **independent mathematical reference implementation** and tests probability forecasts on synthetic sequences with known latent states. It does **not import or replace** `TwoStateFilter`; a direct source-level parity comparison with that existing implementation is a separate outstanding requirement. The reference's tests independently enumerate latent trajectories for all 1–4 response sequences under several parameter choices.

## 2. Precisely specified observation and transition model

Latent mastery `S_t ∈ {0,1}` exists **before** observation `Y_t`.

- `P(Y_t=correct | S_t=1)=1-slip`
- `P(Y_t=correct | S_t=0)=guess`
- `P(S_(t+1)=0 | S_t=1)=forget`
- `P(S_(t+1)=1 | S_t=0)=learn`

These are mutually exclusive transitions, as in the existing filter documentation. No learning or forgetting is applied **before** the current response; the first forgetting-event posterior is undefined because no prior interval exists.

For predictive prior `p_t` and an observed response with likelihoods `L_1`, `L_0`, posterior mastery is

`q_t = p_t L_1 / [p_t L_1 + (1-p_t)L_0]`.

The current **last-transition** forgetting posterior is

`q_(t-1) * forget * L_0 / [p_t L_1 + (1-p_t)L_0]`.

Prediction after the observation is

`p_(t+1) = q_t (1-forget) + (1-q_t) learn`.

An observation impossible under the assumed model fails closed.

## 3. Exact evidence and limitations

- 33 focused pytest cases passed in an isolated current-session reference environment.
- Tests enumerate latent paths for every response string up to length 4 and cross-check posterior mastery and most-recent forgetting-event probability. They test missing observations, impossible observations, stationary worlds, uninformative emissions, deterministic events and seed exclusion.
- The development experiment uses 300 **synthetic learner seeds**, each with 30 responses. These 300 seeds (not the 9,000 repeated observations) are the independent bootstrap units.
- The script is restricted to synthetic development seeds 120000–122999; the prior reserved held-out range from 200000 upward is inaccessible.
- An oracle parameter model is included **only as a simulation reference**. It assumes access to true generating rates, which would not be known for actual learners.
- Model evaluation reports prequential next-response Brier score and log score, post-response latent-state Brier, most-recent forgetting-event Brier, predicted vs actual forgetting-event prevalence, and binned calibration. Latent-state and event scores use simulator truth available only to the evaluator.
- Paired percentile bootstrap intervals measure uncertainty across synthetic seeds under this fixed simulator. They do not produce clinical/educational confidence intervals, correct for development-set tuning, or establish causal recovery efficacy.

## 4. Reproduced development results (300 seeds, 30 observations each)

Lower response Brier is better. Figures are rounded from the bundled JSON reference, which contains all manifest settings and calibration bins.

| World | Correct-parameter oracle Brier | Nominal forgetting Brier | No-forgetting Brier | High-forgetting Brier | Wrong-slip Brier |
|---|---:|---:|---:|---:|---:|
| Stationary, no forgetting | 0.121906 | 0.125173 | 0.121906 | 0.144251 | 0.144791 |
| Slow forgetting | 0.157596 | 0.157596 | 0.173618 | 0.166409 | 0.170997 |
| Rapid forgetting | 0.197381 | 0.202615 | 0.236632 | 0.197811 | 0.207903 |
| Noisy forgetting | 0.219514 | 0.233396 | 0.246382 | 0.235458 | 0.233396 |

The oracle comparison is a **model-misspecification sanity check**: it does not show the estimator could identify correct rates from sparse learner responses. The stationary world gives an oracle/zero-forgetting tie by construction, not a newly discovered result. In rare-event conditions, a trivial zero-event predictor can have deceptively good event Brier despite entirely missing forgetting events; event detection requires event recall, false-alarm accounting and temporal performance metrics beyond aggregate Brier.

## 5. Explicit scientific decision gate

The completed audit is **not** a validated forgetting detector. Before claiming Step 95 closure or a new IJCAI contribution, the team must:

1. **Cross-verify the existing source implementation** `TwoStateFilter.step` against this independent reference, using the exact `Model`, `Step` and output field types in the user's checked-out revision `0cb60f2`. This reference package intentionally does not guess those field names.
2. Test calibration and predictive scores under posterior parameter uncertainty, heterogeneous learners, item effects, adaptive question selection, response dependence, changed learning rates, delayed observations, and variable session gaps. Do not extrapolate constant-rate synthetic results.
3. Establish an identifiable deterioration estimand, event prevalence, eligible decision windows, precision/recall, false-alarm cost and detection delay. Distinguish immediate latent event posteriors from model posterior `P(H1|data)`.
4. Construct a *decision rule* with explicit resource opportunity costs, and compare it with its own no-recovery ablation and strong prior methods using equal opportunities. Do not count estimator calibration as an intervention benefit.
5. Obtain independent mathematical and educational measurement review, a genuinely frozen experimental design, ethical/administrative authorization where needed, and independently evaluated data before asserting human-study results.
6. Preserve the five-seed V3/V5/V6 negative findings and the 100-seed V6 no-recovery ablation. Do not modify or conceal negative comparisons.

## 6. Run instructions

Run from `agent2_realdata_benchmark` on the existing `.venv`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_step95_filter_calibration_development.py
PYTHONDONTWRITEBYTECODE=1 python3 -m scripts.step95_filter_calibration_development --world all --participants 300 --horizon 30 > /tmp/step95_calibration_dev300.json
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```

Expected additional focused tests: **33**. Anticipated full suite from the verified previous baseline of 894: **927**, assuming no unrelated changes. The current-session environment verified 33 focused tests; only the user's WSL run can establish the 927 complete-suite count.

Do not substitute this audit for genuine completion of the 52-step register: **55.8% remains a provisional evidence-weighted estimate** until exit criteria are met.
