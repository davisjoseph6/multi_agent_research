# Step 107 — Exact two-question counterexample, adaptive decision and finite-inventory Bellman equation

**Date:** 2026-10-31. **Research status:** pencil-and-paper mathematics, not a verified *original* AI theorem; no code or RCT policy changes. This is a single-skill example aimed at distinguishing genuinely new proof obligations from standard POMDP optimal stopping.

## 1. A precisely specified model

Hypothesis H ∈ {M,U} is **initial mastery** before any question, with prior P(H=M)=P(H=U)=1/2. This is **not itself a forgetting event**. A later model must separately represent the historical forgetting path event F and previously observed baseline.

There are exactly two distinct, single-use questions, A and B, with equal action cost c=1/100. The answer Y is generated **before** learning, with

    P(Y=correct | current mastered) = 9/10
    P(Y=correct | current unmastered) = 1/4.

Question A **certainly restores mastery** immediately after its answer if the learner was initially unmastered at that action; A leaves a mastered learner mastered. Question B is a purely diagnostic question and does **not** change mastery. No forgetting occurs. Each item can be asked at most once. Responses are conditionally independent given mastery immediately before each assessment. The objective is to diagnose **H**, the *initial* state, with zero–one error loss, plus c per question; both hypotheses have equal prior probability. A/B teaching rates are hypothetical limiting cases, not estimates from students or the V3 simulator.

We allow an adaptive policy to stop and diagnose after 0, 1, or 2 questions. This is a **finite-stock decision problem** in which the order of two measurement actions can matter.

## 2. Two fixed orders have different information

### Order A then B

The first observed response comes from H. After A, the learner is certainly mastered regardless of H. Therefore the second answer B has likelihood 9/10 of being correct under both hypotheses, conditional on the first response; it provides no additional discrimination of the original state.

The total-variation distance between the two observation-history distributions is |9/10 - 1/4| = 13/20. With equal prior, the minimum Bayes classification error is

    e(A,B) = (1 - 13/20)/2 = 7/40 = 0.175.

The optimal classifier uses only A's response: correct → initially mastered; incorrect → initially unmastered. Giving B second adds cost but no diagnostic benefit.

### Order B then A

B does **not** teach, so both responses are conditionally independent observations of H. Let K ∈ {0,1,2} count correct answers.

| K | P(K | H=M) | P(K | H=U) |
|---:|---:|---:|
| 0 | 1/100 | 9/16 |
| 1 | 9/50 | 3/8 |
| 2 | 81/100 | 1/16 |

Under equal prior, classify *initially mastered* if and only if both answers were correct. The exact optimal error is

    e(B,A) = (1/2)[P_M(K≤1) + P_U(K=2)]
           = (1/2)[19/100 + 1/16]
           = 101/800 = 0.12625.

Thus asking the **nonteaching** question first improves minimum possible historical diagnosis error by

    e(A,B) - e(B,A) = 7/40 - 101/800
                    = 39/800 = 0.04875.

Both orders use the same two distinct nonreusable items at equal cost and, because A is guaranteed to teach when needed, both leave final mastery at 1 with probability one. **This is a strict order-of-actions effect in an explicit, finite-inventory toy model.** It is not a claim that either kind of question has these effects in a real classroom.

## 3. Adaptive stopping: the exact optimum with c = 1/100

Now allow the policy to choose whether to administer A **after seeing B's answer**.

- If B is incorrect: even an additional correct answer on A would not overcome the likelihood evidence favoring initially unmastered. The optimal diagnosis stays U, so A brings *no diagnostic error reduction*. Stop.
- If B is correct: an incorrect answer on A reverses the optimal diagnosis from M to U. Asking A reduces expected diagnostic error, and its cost 1/100 is smaller than the corresponding expected benefit. Ask A, then diagnose M iff A is correct.

The probability B is correct under the equal prior is

    P(B=correct) = (1/2)(9/10 + 1/4) = 23/40.

This adaptive policy has the same zero–one diagnostic error as the complete B→A order, 101/800. It uses on average

    E[number of questions] = 1 + 23/40 = 63/40,

and incurs action cost 63/4000. Its total expected diagnostic-plus-action loss is

    V* = 101/800 + 63/4000
       = 505/4000 + 63/4000
       = 568/4000
       = 71/500
       = 0.142.

For comparison, the best one-question policy has risk

    7/40 + 1/100 = 37/200 = 0.185,

and the unconditional B→A two-question order has risk

    101/800 + 2/100 = 117/800 = 0.14625.

A→B has risk 7/40 + 2/100 = 0.195, and stopping without asking has risk 1/2. Hence **under this model and objective the adaptive B-first policy is optimal** among all observation-history-dependent policies (also allowing randomization, which cannot lower the minimum of expected losses).

### The *teaching* tradeoff

The adaptive diagnosis-optimal policy does not always ask A. Its final mastery probability is

    P(H=M) + P(H=U)P(B=correct | H=U)
    = 1/2 + (1/2)(1/4) = 5/8.

Always using both questions in order B→A yields final mastery 1, at an additional expected action cost 17/4000 = 0.00425, with the **same diagnostic error**. If the objective also charges λ per unit *remaining unmastered probability*, complete B→A becomes preferable to the adaptive diagnosis-optimal policy when

    λ > (17/4000)/(1 - 5/8) = 17/1500 ≈ 0.01133.

This is only a **pairwise** comparison of two explicitly specified policies; once λ is introduced the global optimal policy must be recomputed via dynamic programming and may differ from both.

This example shows the tradeoff among *historical diagnostic confidence*, *end mastery*, and *question burden*—but all three are already ordinary ingredients of decision-theoretic partially observable control.

## 4. General exact finite-inventory Bellman equation (standard POMDP result)

For the same initial-state diagnosis target H, define the belief over **both** original and current mastery:

    μ_t(h,m) := P(H=h, M_t=m | observed history up to t),

where h,m∈{0,1}. In particular, the controller must **not** maintain only P(M_t=1): the original state H is a latent path summary that can differ from M_t after teaching.

Let I_t be the set of unused item IDs, c_q the cost to use q, O_q(y|m) the *pre-learning* response kernel, and T_q(m'|m) the question-induced mastery transition.

Upon choosing q and observing y, the predictive observation probability is

    z_q(y) = Σ_{h,m} μ_t(h,m) O_q(y|m).

The updated joint belief **after** the teaching transition is

    μ_{t+1}(h,m')
       = (1/z_q(y)) Σ_m μ_t(h,m) O_q(y|m) T_q(m'|m),

for z_q(y)>0; zero-probability outcomes are omitted. The inventory changes to I_{t+1}=I_t\{q}; each item is truly nonreusable.

If the stop action must diagnose H with false-positive cost c_FP and false-negative cost c_FN, the minimal *immediate* expected diagnostic loss is

    L_stop(μ) = min{
        c_FP * P_μ(H=0),    // declare initially mastered
        c_FN * P_μ(H=1)     // declare initially unmastered
    }.

An abstention option can be added as a third cost if it is explicitly priced. (For actual forgetting detection, swap the target H for an augmented state representing a specified historical forgetting event, and carry its posterior in μ.)

With remaining inventory I and at most k additional questions, the exact finite-budget recursion is

    V_0(μ,I) = L_stop(μ),

    V_k(μ,I) = min{
        L_stop(μ),
        min_{q∈I} [c_q + Σ_{y∈{0,1}} z_q(y)
                    V_{k-1}(Φ_q(μ,y), I\{q})]
    }.

Set V_k=L_stop whenever I is empty. Additional independent resource budgets, transition uncertainty and final mastery penalties enlarge the state/objective and require explicit modeling. The recursion above is **ordinary finite-horizon POMDP dynamic programming**, not new AI theory, and it does not handle worst-case model ambiguity unless extended.

The two-question example is an exact benchmark for checking any proposed approximation: with these assumptions, the globally optimal diagnostic-plus-action risk at c=1/100 is 71/500; no claim about a practical algorithm may surpass that value for the same model, information set and loss.

## 5. What is NOT proven, and what would constitute the next research step

**Not yet addressed**:
1. Actual *historical forgetting* F rather than initial mastery H.
2. A prior baseline whose evidence of mastery is itself uncertain and could be contaminated by teaching.
3. Partial acquisition (0<ρ<1), per-item calibrated difficulty and response likelihood, true forgetting, question-dependence and learner heterogeneity.
4. Robust model set Θ with uncertain transitions and observations; an admissible cost-aware policy with a nontrivial **proved** bound beyond Bellman optimality.
5. A meaningful *new* structural restriction or an algorithmic complexity improvement over the closest already published work.
6. Valid human-intervention estimates, content review, protocol authorization, or a causal RCT outcome.

**Scientific STOP rule:** If the only result is that questions have teaching effects, order matters, or finite-budget POMDP DP chooses an optimal policy, then **do not claim IJCAI originality**. Use this exact toy case as a test fixture / analytic baseline and identify a stronger open theorem before writing another simulator.

## 6. Supervisor discussion: an exact falsifier

> “Under two nonreusable questions, one of which certainly teaches, we can derive the exact cost-sensitive optimal adaptive diagnosis risk 71/500. This is a model sanity-check, not our claimed contribution. A new algorithm must agree with this tiny-instance optimum and then show something genuinely nontrivial about robust, finite-budget *historical forgetting* decisions that generic POMDP planning does not already establish.”

**References for required novelty review:** Step106, Rafferty et al. (2016), Krale et al. (2023), Gao et al. (2026), Rasouli & Saghafian (2018), Zhang & Hoi (2019), Galesloot et al. (IJCAI 2025). 
