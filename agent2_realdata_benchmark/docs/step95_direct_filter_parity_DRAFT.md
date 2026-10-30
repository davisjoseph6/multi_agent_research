# Step 95 — Direct exact-path parity for TwoStateFilter

**Status:** implementation correctness gate, not a cognitive-model validation, approval to experiment with people, or an IJCAI novelty result.

**Purpose:** Compare the existing `src/prototype/step95_bayesian_forgetting_filter.py` implementation directly against an independent enumeration of **all latent mastery histories**, rather than another implementation of the same two-state filter recursion. Do not alter the original filter.

## Mathematical oracle

For hidden state `S_t ∈ {0,1}`, independent response emission `P(Y_t|S_t)`, and action learning `ell_t`, the oracle maintains a separate weighted trajectory for each possible sequence `(S_0, ..., S_t)`.

1. Initialize paths `(S_0=0)` with weight `1 - p_0` and `(S_0=1)` with `p_0`.
2. At response `t`, multiply *each entire path's* weight by its emission likelihood at `S_t` (or one for a missing response).
3. Normalize against the total weight to calculate posterior mastery `P(S_t=1 | Y_0:t)`.
4. Normalize path weights ending in `(S_(t-1),S_t)=(1,0)` to calculate the posterior of **the immediately preceding forgetting event**.
5. Extend **every path** into both possible states at `t+1`, with `P(S_(t+1)=1|S_t=1)=1-f` and `P(S_(t+1)=1|S_t=0)=ell_t`.
6. Calculate predictive next mastery, per-response likelihood, and the cumulative log evidence from the complete path weights.

All path weights are `fractions.Fraction` rational numbers constructed from decimal input parameters. Only the final reported outputs are converted to floats. The oracle is exponentially expensive and deliberately restricted to at most nine response steps.

## Test coverage

The direct parity test suite checks:
- All 81 length-four sequences over `{correct, incorrect, missing}`.
- Six parameter boundary/misspecification regimes including high forgetting and non-informative observations.
- Sixty-four reproducibly generated short trajectories with varying learning rates and missing answers; genuinely impossible observations must fail in both implementations.
- Direct agreement with the previously committed, independent `ReferenceFilter` on constant-learning cases.
- Exact-path marginal likelihoods, log Bayes factors, and posterior model probabilities for different response strings and one nonuniform model prior.
- Impossible-observation handling without mutation of a filter's internal state.
- Missing responses must not change evidence but must still permit action transitions.
- The recent-transition posterior differs from the posterior of the hypothesis that `forget > 0`.

## Assumptions and limitations

- Fixed and known parameters (`slip`, `guess`, `forget`, and each `learn`) and conditionally independent responses given latent mastery.
- Missing response has emission likelihood one, but **does not imply a skipped action transition**.
- No support for estimating unknown parameters, nonstationary transition rates, concept dependence, item-specific observations, numerical filtering over thousands of steps, or post-selection inference.
- No evidence that the assumed latent mastery state or rates describe actual human students.
- No evidence that Bayesian-filter-based recovery improves learning compared with greedy, fixed or no-recovery policies.
- Passing tests is not equivalent to novel AI research or meeting IJCAI acceptance criteria.

## Operational sequence

From `~/multi_agent_research/agent2_realdata_benchmark`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_step95_filter_direct_parity.py
PYTHONDONTWRITEBYTECODE=1 python3 -m scripts.step95_filter_direct_parity_probe
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```

The script prints the SHA-256 of the actual source being tested so future results can be linked to a precise revision. `git rev-parse HEAD` is additionally required for a full provenance record.

**Expected focused tests:** 102. **Expected project suite:** 1,029 if the previously verified 927 tests are unchanged.

**Go/no-go:** Any mismatch, impossible-observation inconsistency, or source drift requires correction and reproduction before the estimator is used for policy evaluation. Passing this gate authorizes *further synthetic study only*; all data calibration, publication novelty, educational and external approvals remain separate.
