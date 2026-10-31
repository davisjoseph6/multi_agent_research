# Step 97 — exact statewise drift scope and a conditional coverage remedy

Status: **mathematical model exploration**, not a novel IJCAI theorem, an implemented trial intervention, or a guarantee about V3/V5/V6.

## Structural impossibility for deterministic single-target actions

Let the latent state be (s\in\{0,1\}^n) where (s_j=1) denotes mastered, and let (D(s)=n^{-1}\sum_j(1-s_j)). A policy chooses one action targeting one concept from an observation-dependent belief. In the no-forgetting model, a targeted unmastered concept learns with probability (p_a>0); untargeted concepts cannot be learned.

If the policy deterministically targets concept (j) while a different concept (k\neq j) is unmastered and (j) is mastered, then \\(\mathbb E[D_{t+1}-D_t\mid s,a]=0\\) despite \\(D(s)>0\\). Hence no deterministic single-target policy that makes such a selection can have a strictly negative uniform drift bound over **all** compatible latent states. This does not preclude conditional guarantees over smaller state supports, average-case progress, or beneficial instruction.

## Conditional randomized-coverage result

At one decision, let \\(q_{a,j}\\) be the probability of executing action type (a) on concept (j). Define the effective probability of learning concept (j), when unmastered, as \\(r_j=\sum_a q_{a,j}p_a\\). Let \\(f_j\\) be the independent probability of forgetting a mastered concept, with no other learning. Then for any fully specified latent state,

\\[
\mathbb E[D(S_{t+1})-D(S_t)\mid S_t=s,\text{observable history}]
=\frac{\sum_{j:s_j=1}f_j-\sum_{j:s_j=0}r_j}{n}.
\\]

The largest drift over all nonmastered states is exactly

\\[
\max_{D(s)>0}\mathbb E[\Delta D\mid s]
=\frac{\sum_j f_j-\min_k(f_k+r_k)}{n}.
\\]

A strict uniform negative drift margin exists if and only if every concept satisfies

\\[
r_k>\sum_{j\neq k} f_j.
\\]

Proof: for any unmastered set (U\neq\varnothing), the numerator equals \\(\sum_j f_j-\sum_{k\in U}(f_k+r_k)\\). Nonnegative terms make it maximal at a singleton (U=\{k\}\) minimizing (f_k+r_k).

**Important:** these equations require the distribution of the chosen action to be the same across possible latent states **conditional on the observable history**. They are valid at each such history if the distribution and model assumptions hold; the statewise worst case does not assume the controller sees the true state.

For no forgetting, any distribution putting strictly positive learning-weighted probability on all eight concepts yields strict statewise negative drift. A hypothetical epsilon-mixture with a chosen primary action and uniform practice has \\(r_k\geq\epsilon p_{practice}/8\\), so \\(\delta\geq\epsilon p_{practice}/64\\). With (p_{practice}=0.05\) and \\(\epsilon=1\\), this is \\(1/1280\\) per decision.

For \\(f_j=0.001\\), the uniform-practice mixture fails: a state with seven mastered concepts has positive expected deficit drift \\(3/32000\\). If \\(f_j=0.0001\\), the conditional certificate becomes \\(111/160000\\).

## Why this is NOT yet a practical solution

The repository's 55-item finite quiz does not ensure at least one unused question remains for every concept at every decision. Recovery budgets and resource feasibility may change action availability. The proposed hypothetical randomized mixture is **not** the V3, V5, V6 or enrolled-study Group A policy and is not an accepted change to that design.

The same action may produce different effects across learners, the true forgetting and learning probabilities are unknown, and human learning cannot be inferred from these simulator parameters. If the uniform drift holds throughout an actual stopped process until a target or horizon K, the standard additive-drift bound can be used, but it is often vacuous at the planned horizon of 55 decisions. In particular, an initial deficit of 1/2 and margin 1/1280 yield the trivial upper bound 1 on non-recovery at step 55.

## Scientific next steps

1. Verify the sharp formula and exact enumeration in `src/prototype/step97_policy_drift_certificate.py`; report any failed arithmetic checks.
2. Define a policy with feasible question inventories and a formally specified uncertainty set of transition/forgetting parameters. Derive its *actual* reachable-state guarantees, if any.
3. Compare fair, matched-budget and matched-time policies in an environment faithful to the actual quiz. Do not select a policy based on the already viewed held-out or development results and relabel the result confirmatory.
4. Compare novelty against prior POMDP teaching, stochastic coverage, drift analysis and risk-aware shielding. These elementary results alone are **not IJCAI-level novelty**.
5. Retain negative outcomes and independent reviewer decisions; do not modify the current RCT candidate or the original 52-step progress rubric merely because this mathematical exercise passes.
