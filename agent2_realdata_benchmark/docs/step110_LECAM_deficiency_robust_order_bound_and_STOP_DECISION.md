# Step 110 — Uniform approximate ordering bound and originality stop rule

**Date:** 2026-10-31. **Status:** small-model mathematical note and **targeted** prior-art review. This is a direct **application of established Le Cam deficiency / randomization theory**, **not a new theorem**, a measured treatment effect, an RCT approval, or an IJCAI novelty finding. No software code, source data, experiments or previous negative results are changed.

## 1. What Step 109 established

For a **known** model θ and Step108's passive diagnostic B / restorative assessment A assumptions, B→A is Blackwell more informative than A→B about original mastery H. Step109 then gave two plausible monotonic (mastered response ≥ unmastered response) but conflicting unknown response models. Its **Bayesian** prior-weighted risk, after marginalizing θ, favored A→B: risk 1/5 versus 197/800 for B→A. This does **not** show that A→B is minimax-robustly superior, and there is no actual forgetting event.

Before designing a new "robust comparator", we must screen the classical **deficiency of statistical experiments**. This existing theory already measures whether an information experiment can approximately simulate another one under model uncertainty.

## 2. Standard deficiency formulation (NOT a novel mathematical concept)

Let s=(H,θ) vary over a finite joint hidden-state/model set S. For any order E define a channel P_E(x|s) over the **complete two-answer history** x. The two orders have the same observation alphabet after relabeling answers by question identity.

A *single* model-independent randomized transformation K(y|x) from B→A responses to simulated A→B responses is **approximately** valid if

    ε_K = sup_{s∈S} TV( sum_x P_BA(x|s)K(·|x), P_AB(·|s) )

is small. Define the one-way Le Cam deficiency

    δ(P_BA,P_AB) := inf_{K row-stochastic} ε_K.

This is a **standard** definition of experiment deficiency. Zero means one **common** garbling exactly reproduces A→B under every s, including each possible θ. Blackwell dominance for each separately known θ does not imply δ=0 for the joint unknown-state problem.

### Standard risk-transfer consequence

For any prior π on S, any terminal decision problem with a loss in [0,1], and both full orders having equal assessment costs,

    R*_BA(π) ≤ R*_AB(π) + δ(P_BA,P_AB).

**Proof:** Take any optimal A→B decision rule. A B→A agent samples y from a nearly optimal K after receiving x, then applies the A→B rule to y. The expectation of any [0,1] loss changes by at most the total-variation error under each s. Integrate over π and minimize. The inequality is a direct corollary of standard approximate comparison of experiments, not a novel theorem. The reverse comparison requires its **own** deficiency δ(P_AB,P_BA).

## 3. An explicit shared-approximation certificate specialized to Step108

Fix a **reference** restorative rate ρ₀(a)∈[0,1] and a reference probability distribution Q₀ for B's response after mastery. Neither reference may depend on the unknown θ. The true rate is ρ_θ(a), and the actual response channels for B under unmastered and mastered states are U_θ and M_θ.

Define a θ-independent garbling K₀ on observed (b,a) from B→A:

    output (a,b') where
      b'=b with probability 1−ρ₀(a),
      b'~Q₀ independently with probability ρ₀(a).

**Uniform bound.** Under the exact Step108 structural assumptions, a valid upper bound on the deficiency is

    δ(P_BA,P_AB)
      ≤ ε₀
      := max_{θ,a} [
         |ρ_θ(a)−ρ₀(a)| · TV(U_θ,M_θ)
         + ρ₀(a) · TV(Q₀,M_θ)
      ].

**Proof:** Condition on θ, initial H, and first answer a (A is observed first after relabeling the B→A history). If initial H=M, actual B-after-A law is M_θ while K₀ gives (1−ρ₀)M_θ+ρ₀Q₀, so the conditional TV is ρ₀TV(Q₀,M_θ)≤ε₀. If H=U, actual B-after-A law is (1−ρ_θ)U_θ+ρ_θ M_θ, while K₀ produces (1−ρ₀)U_θ+ρ₀Q₀. Subtract the distributions, add and subtract ρ₀ M_θ, then apply the triangle inequality. The first term has TV ≤ |ρ_θ−ρ₀|TV(U_θ,M_θ), the second ≤ρ₀TV(Q₀,M_θ). Averaging over a and maximizing over s completes the bound. This certificate is conservative and uses known classical inequalities.

### Exact robust dominance is possible under a simple condition

If **all admissible models share the same ρ_θ(a)=ρ₀(a) and mastered B-response law M_θ=Q₀**, then ε₀=0; hence B→A Blackwell-dominates A→B **even when θ is hidden**. This is a **sufficient** condition, **not necessary**: another shared garbling K could exist without these equalities.

### Application to Step109's unknown-model example

Its restorative A always succeeds, so ρ_θ=ρ₀=1. The true mastered-B correctness probability is p=1/5 under θ=0 and p=9/10 under θ=1. Choose the single reference Bernoulli distribution Q₀ with correctness p₀=11/20, the midpoint. For Bernoulli channels, TV=absolute probability difference, hence

    ε₀ = max(|1/5−11/20|, |9/10−11/20|) = 7/20 = 0.35.

Therefore the known-model information comparison has an **explicit uniform approximate** extension, with a bound 0.35 on any [0,1] decision-loss regret caused by simulating the A→B experiment from B→A data. The **actual** optimal deficiency may be much smaller; no optimality of this chosen K₀ is claimed.

Step109's prior-weighted risk reversal additionally implies

    δ(P_BA,P_AB) ≥ 197/800 − 1/5 = 37/800 = 0.04625,

because otherwise the general risk-transfer inequality would fail. Thus the elementary analytically verified bracket is

    37/800 ≤ δ(P_BA,P_AB) ≤ 7/20.

This bracket is **not** a new discovery and does not establish robustness of A→B, only a bounded inability to simulate its answers perfectly from B→A **uniformly across the specified hidden models**. It does not compare adaptive stopping rules, action costs or true historical forgetting events.

## 4. How to test more complex uncertainty families without pretending originality

For finite S and observations x,y, optimizing δ is an **ordinary linear program** with nonnegative variables K(x,y), each row of K summing to one, and auxiliary absolute-value constraints for the TV norm. This is established computational statistical experiment comparison, **not an original learning algorithm**.

Before implementing a planner, demand that its claimed property is **not** already expressed by either (a) the robust Bellman recursion, (b) the common garbling/deficiency program above, or (c) an established sequential change-detection test.

Even an exact LP optimum is a **benchmark or certificate**, not intrinsically an IJCAI research contribution. For the actual application we must first decide whether to predict current mastery, infer initial mastery, or identify a **historical forgetting event** with recorded longitudinal data. These targets are not interchangeable.

## 5. New and decisive novelty information

The closest *mathematical* foundation for the Step108–110 line is older and stronger than the education-specific POMDP papers:

1. Erik Torgersen, *Comparison of Statistical Experiments*, Cambridge University Press, 1991, Chapter 6, **“Deficiencies”**. https://doi.org/10.1017/CBO9780511666353.007 — a classical account of approximate informativeness, risk and randomizations.
2. *Unique Information Through the Lens of Channel Ordering: An Introduction and Review*, **Entropy**, 27, 29 (2025), especially Definition 12 (Le Cam deficiency) and the randomization criterion. https://pmc.ncbi.nlm.nih.gov/articles/PMC11764511/
3. Henrique de Oliveira, *Blackwell's informativeness theorem using diagrams*, **Games and Economic Behavior**, 109 (2018), DOI 10.1016/j.geb.2017.12.008 — includes an extension to sequentially arriving information through **adapted garbling**.
4. Rafferty et al., *Faster Teaching via POMDP Planning*, **Cognitive Science** (2016), DOI 10.1111/cogs.12290 — established instructional planning and diagnosis under partial observability.

These are relevant directly to the proposed novelty, not decorative citations. A result that merely demonstrates a Bayesian ordering reversal or bounds it by deficiency is **not** original AI research.

## 6. Formal decision for Monday November 2

**STOP treating assessment ordering + simple parameter uncertainty as the primary IJCAI originality thesis.** Steps107–110 are useful reproducible *mathematical baselines*, but their central mechanisms are classical comparison-of-experiments and decision theory.

One final narrowly framed question remains suitable for a supervisor's **GO/NO-GO** decision:

> Is there a domain-specific, mathematically substantial improvement for **sequential diagnosis of a *historical path event*** with action-induced hidden-state transitions, nonreusable item inventories, and calibrated uncertainty, that is not simply standard adapted garbling, Le Cam deficiency, or a robust/constrained POMDP formulation?

A **GO** requires a named novel algorithm or theorem, direct rigorous contrast to the strongest closest existing method, strong fair baselines, and realistic data/validation. If that cannot be formulated, **pivot the IJCAI main-track research topic** rather than relabeling current elementary results as novelty.

**P0 now:** present the Step104/105 charter plus Steps107–110 as a **negative-origin / sharp-prior-art** dossier. Preserve the unfavorable V6, Step100 and Step102 development findings, and maintain the human-study NO-GO pending actual independent approvals. No new Python code or RCT changes are justified yet.
