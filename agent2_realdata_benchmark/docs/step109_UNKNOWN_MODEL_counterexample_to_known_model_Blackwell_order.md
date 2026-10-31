# Step 109 — A model-uncertainty counterexample to the Step108 assessment-order guarantee

**Research date:** 2026-10-31. **Status:** exact, restricted **Bayesian model-uncertainty counterexample** derived using elementary decision theory. **NOT** a novel general theorem, minimax-robust ordering reversal, calibrated model, RCT evidence, or IJCAI-ready contribution. The codebase and previous experiments are unchanged.

## 1. Why this matters

Step108 showed that, **for each fixed known learner model θ**, asking a nonteaching diagnostic question B **before** a restorative question A Blackwell-dominates A→B for inference about original mastery H. Its proof uses a garbling kernel K_θ that depends on the learner model's restorative probability and the mastered-response distribution for B.

It is tempting but **incorrect** to infer that B→A is universally better when θ itself is not known to the decision maker. A known-model garbling can vary with θ, so it need not define a single usable policy under model uncertainty.

The following construction demonstrates an **exact reversal of Bayes-optimal historical-mastery classification error after marginalizing over an unknown θ**. It uses **no noisy simulations** and gives every relevant probability as a rational fraction. It establishes a mathematical limitation of applying Step108 too broadly, not a new contribution beyond standard comparison-of-experiments theory.

## 2. Two unknown models, each physically ordered correctly

Let H∈{M,U} be *original* mastery, with prior P(H=M)=1/4; let θ∈{0,1} be an unknown learner response model, with prior P(θ=0)=P(θ=1)=1/2, independent of H.

Both questions are single use. A emits its answer **before intervention**, then **certainly converts U into M**. B never changes the state. There is no forgetting and there are no additional outcomes or time costs. Both orders use exactly the same two questions, so their total assessment costs are equal and their final mastery is M with probability one. Observations are conditionally independent given H and θ and their relevant pre-question mastery.

The response channels depend on θ as follows. Entries are **probabilities of a correct answer**:

| Model | A when M | A when U | B when M | B when U |
|---|---:|---:|---:|---:|
| θ=0 | 9/10 | 1/10 | 1/5 | 1/10 |
| θ=1 | 7/10 | 1/2 | 9/10 | 1/2 |

**Crucial physical ordering:** In **each** θ, both questions are more likely to be answered correctly by a mastered learner than by an unmastered learner. No sensor-label inversion is used. This remains only a hypothetical model family; it is not a plausible calibration of any specific real student's answers without data.

For any *known* θ, the assumptions of Step108 hold with ρ=1, so the dominance of B→A over A→B by a **θ-dependent garbling** remains valid.

## 3. Exact marginal observation distributions

Write observations as (a,b), where a and b represent the binary correctness of questions **A and B**, respectively, regardless of presentation order. Marginalize θ using the same prior 1/2 under both H hypotheses.

With **A→B** the learner is mastered by the time B is asked. Therefore

    P_AB(a,b | H=h) =
       1/2 Σ_{θ∈{0,1}} O_A,θ(a | h) O_B,θ(b | M).

With **B→A**, both answers reflect the original H because B does not teach and A's answer is emitted before it teaches:

    P_BA(a,b | H=h) =
       1/2 Σ_{θ∈{0,1}} O_A,θ(a | h) O_B,θ(b | h).

The exact probability tables are:

| (a,b) | P_AB(·|M) | P_AB(·|U) | P_BA(·|M) | P_BA(·|U) |
|---|---:|---:|---:|---:|
| (0,0) | 11/200 | 77/200 | 11/200 | 106/200 |
| (0,1) | 29/200 | 63/200 | 29/200 | 34/200 |
| (1,0) | 79/200 | 13/200 | 79/200 | 34/200 |
| (1,1) | 81/200 | 47/200 | 81/200 | 26/200 |

Each column sums to one.

## 4. The Bayes-optimal classification error reverses the known-model ranking

For observations x=(a,b), 0–1 error and prior P(H=M)=1/4, the optimal classification risk is

    R(order) = Σ_x min{ (1/4)P_order(x|M), (3/4)P_order(x|U) }.

For A→B, expressing the four minimum terms in units of 1/800 gives

    R(A→B) = (11 + 29 + 39 + 81)/800
            = 160/800 = 1/5 = 0.20.

The optimal rule declares H=M **only when (a,b)=(1,0)**.

For B→A the minimum terms are

    R(B→A) = (11 + 29 + 79 + 78)/800
            = 197/800 = 0.24625.

The optimal rule declares H=M **only when (a,b)=(1,1)**.

Consequently,

    R(B→A) − R(A→B) = 37/800 = 0.04625 > 0.

**Under this specified prior on unknown θ and H, asking the restorative question A first is better for Bayes-optimal classification of *initial* mastery**, despite the fixed-known-θ Blackwell statement in Step108 and despite administering the same two questions at equal cost and achieving identical final mastery.

**Why?** A teaches mastery before B, so the second B answer indirectly **calibrates which unknown model θ generated A's answer**. When B is observed before A, B's response depends jointly on H and θ; with this parameterization it is less useful for deciding H after marginalization. This is parameter-learning through the intervention, *not* proof that teaching first is generally preferable.

### Why the Step108 theorem is NOT contradicted

There is a model-specific simulation kernel K_θ mapping each B→A observation experiment into the corresponding A→B experiment. In this example K_0 must generate a mastered B response with probability 1/5; K_1 must instead generate it with probability 9/10. The decision maker does not know θ.

A **single θ-independent garbling kernel** would imply B→A is at least as useful as A→B after mixing θ under the declared prior, contradicting the exact Bayes-risk calculation above. Hence **no such common garbling exists** for these two fixed experiment families.

This is fully consistent with Blackwell's existing theorem, which treats the relevant hidden parameter/state as part of the statistical experiment. A decision maker who knows θ faces a different information problem from one who must infer θ while deciding H.

## 5. Important limitation: NOT a minimax-risk reversal

This example demonstrates a **Bayesian, prior-weighted model-uncertainty reversal**, not a worst-case / minimax one.

Indeed with the prior P(H=M)=1/4 and *unrestricted uncertainty over θ∈{0,1}*, the worst-case optimal risk is **exactly 1/4 for both fixed orders**: always diagnosing H=U achieves 1/4, and under θ=1 the likelihood ratios of available response pairs do not exceed 3, so even a classifier informed that θ=1 would do no better than always diagnosing H=U. Thus no decision rule can reduce the supremum risk below 1/4 in that model family.

Therefore the present result **cannot justify saying A→B robustly dominates B→A**. Any later minimax, distributionally robust, or posterior-robust ordering claim requires a new explicit theorem with the correct uncertainty interpretation.

It also **cannot diagnose historical forgetting**: the latent variable here is *initial mastery H*, not the path event M_t=1,M_{t+1}=0. There is no forgetting anywhere in this constructed environment.

## 6. What a genuinely new research claim would require

Step107: a two-item exact optimal stopping example.  
Step108: a classical Blackwell fixed-known-model ordering dominance.  
Step109: an exact **failure of a naive uniform extension** when the observation model is uncertain.  

All three are elementary decision-theoretic analyses, not established main-track originality.

The stronger research opportunity, if any, is to characterize a **nontrivial ambiguity family with interpretable response assumptions** under which (a) common feasible garblings or order bounds *do* exist; or (b) efficient robust finite-item policies attain meaningful risk bounds; and to show that the result goes beyond existing robust experiment comparison, dual control, active learning and robust POMDP theory.

To test such a claim, require:
1. The exact action and item availability set and a **specified** target: current knowledge, historical forgetting event, or initial mastery (never silently interchange them).
2. A credible uncertainty model learned from approved data or clearly labeled hypothetical assumptions, and sensitivity to unknown θ.
3. A cost-sensitive objective that avoids trivial always-negative classification and abstention.
4. Matched exposure/time/recovery resources, oracle small-instance reference, strong robust-policy baselines and independent evaluation.
5. Explicit literature review of the *robust Blackwell comparison of experiments* literature, sequential active change detection and belief-state dual control. Merely exhibiting this toy reversal is **not** sufficient originality.

**Monday 2026-11-02 decision:** Do not authorize a main-track novelty claim from Steps103–109 alone. Demand supervisor-reviewed precise theorem statements, counterexamples, realistic assumptions and direct competitor identification. Keep all previously reported V6, Step100 and Step102 negative or mixed results.

## Prior references / related field

- Blackwell, *The Comparison of Experiments*, 1951; *Equivalent Comparisons of Experiments*, 1953. Standard garbling and decision-value ranking. Modern course exposition: https://python.quantecon.org/blackwell_kihlstrom.html
- *Coarse-Graining and the Blackwell Order*, Entropy 2017, https://www.mdpi.com/1099-4300/19/10/527
- *Robust Merging of Information* (robust information-order questions), https://gtcenter.org/wp-content/uploads/2022/04/RobustMerging.pdf
- Rafferty et al. (2016), POMDP teaching, https://doi.org/10.1111/cogs.12290
- Step106: closely related robust POMDP / measurement methods.
