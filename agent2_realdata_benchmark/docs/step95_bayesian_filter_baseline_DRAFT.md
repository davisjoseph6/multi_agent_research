# Step 95 — Exact two-state Bayesian learning/forgetting FILTER BASELINE

**Status:** Research-development baseline; NOT an original contribution, calibrated cognitive model, validated deterioration detector, or approved human-study protocol.

## Why this baseline exists

The V6 answer-pattern trigger (`CCWW`) is not a reliable identification of a latent forgetting transition: it can fire under a state that never changes. This new baseline represents the competing explanations explicitly and makes three different quantities reportable: `P(mastered now | observations)`, `P(forgetting at previous transition | observations)`, and `P(model H1 with forgetting | observations)`. None is direct observation of true latent forgetting.

## Exact model, assumptions and time convention

For each concept, let `S_t in {0,1}` be latent mastery **before** response `Y_t`. For each response the emission assumptions are:

- `P(Y_t=correct | S_t=1) = 1 - slip`
- `P(Y_t=correct | S_t=0) = guess`
- A missing response has likelihood one, and is not counted as incorrect.

Given pre-response belief `p_t`, observe `Y_t`, then obtain `q_t=P(S_t=1 | Y_1..Y_t, actions to t-1)`:

`q_t = p_t L_1(Y_t) / (p_t L_1(Y_t) + (1-p_t)L_0(Y_t))`.

After the observation, apply the interval's action with an **assumed** learning probability `ell_t`, plus assumed forgetting probability `f`:

`P(S_(t+1)=1 | observations) = q_t(1-f) + (1-q_t)ell_t`.

These are mutually exclusive transitions: for a mastered concept, forgetting may occur; for an unmastered concept, learning may occur. The action's `ell_t` is supplied externally, not inferred from observed responses. With multiple actions or variable interval durations, the model requires an explicitly justified time convention and transition rates.

For t >= 1, the event `F_(t-1)={S_(t-1)=1,S_t=0}` has prior joint mass `q_(t-1)*f`. Upon observing `Y_t`, its conditional probability is:

`P(F_(t-1)|observed data through t) = q_(t-1)*f*L_0(Y_t) / P(Y_t | earlier data)`.

It is always bounded by the current nonmastery posterior, but may be much smaller. This is the probability of **the last** transition being mastered-to-unmastered, not a generic detection score or probability of ever forgetting.

The competing-model evidence compares fixed model `H0:f=0` with `H1:f=f_alt` using forward marginal likelihoods and a declared prior `P(H1)`. The resulting `P(H1|answers)` is a **model probability**, *not* `P(F_(t-1)|answers)`.

## Falsifiability tests

- Independently enumerate all latent-state paths for all 16 length-four binary-answer strings and compare likelihood, state filtering, prediction and last-transition event posterior with the recursion.
- Verify that an initial never-mastered state with no learning yields zero probability of forgetting, regardless of CCWW answer patterns.
- Verify that if `slip=0.75` and `guess=0.25`, responses have equal likelihood under mastery and nonmastery; thus they cannot update a mastery posterior even though the latent transition model may evolve.
- Reject logically impossible observed answers for degenerate emission probabilities rather than inventing a posterior.
- Permit missing observations for non-question resource actions.

## Scientific limitations and publication risk

This is standard finite-state hidden Markov / Bayesian knowledge-tracing mathematics, **not** new AI research. All rates in the probe are hypothetical and the independent-conditional-observation assumption may not hold. Mis-specified slip, guess, action efficacy, and forgetting can produce unjustified posterior certainty or false model preferences. A posterior under an incorrect assumed model is not a calibrated detection probability. These tests establish implementation correctness only.

Recent evidence: Schuetze, Yan and Carvalho, *Capturing Session-to-Session Dynamics of Learning and Forgetting: Testing the Limits of Knowledge Tracing Models*, International Journal of Artificial Intelligence in Education, 2025 (DOI 10.1007/s40593-025-00508-3). Retrospective performance can overstate temporal generalization. Use only as contextual precedent, not evidence validating this implementation.

## Proposed next scientific gate (NOT completed)

1. Independent baseline comparison with correctly specified and misspecified HMMs and V6 on common development seeds, including false positive rates, recall, time-to-detection, proper predictive log score, Brier score, and intervention cost.
2. Distinguish model-estimation utility from decision-policy utility: compare a new candidate WITH and WITHOUT recovery under equal instructional budgets and identical practice-selection rules.
3. Evaluate non-trivial forgetting (not only stationary or absorbing mastery), learning opportunities, different slip/guess parameters, resource availability, and time between sessions; report unfavorable scenarios.
4. Obtain independent novelty review against BKT+forgetting, adaptive POMDP tutoring and risk-constrained planning, followed by a protocol freeze **before** accessing held-out seeds.
5. Do not claim human efficacy, general drift guarantees, valid posterior calibration or IJCAI novelty from the tests or probe.

**The held-out split remains untouched.**
