# Step 105 — Formal research problem, baseline lemma, and originality falsification

**Date:** 2026-10-31. **Decision deadline:** 2026-11-02.
**Status:** research specification / pencil-and-paper derivation, **not** a claimed novel theorem, a calibrated learner model, a new empirical result, or an approved RCT.
**Repository policy:** documentation-only; freeze the V3/V5/V6/RCT controllers, Steps 95/97–103, existing datasets, and all favorable and negative synthetic outcomes.

## 1. Candidate scientific question

**Working title:** Finite-Budget Diagnosis and Recovery under Intervention-Induced State Changes.

**Question:** When a diagnostic assessment yields a noisy response **and can change hidden mastery**, and each assessment consumes a nonrenewable inventory item, what guarantees can an adaptive decision maker give for distinguishing a recent loss of previously acquired mastery from poor performance or low initial knowledge while keeping diagnostic, recovery, and intervention costs controlled under uncertainty over learner dynamics?

This is a candidate *AI research question*, not a claim of novelty. Known POMDP teaching, dual control, controlled change detection, active measurement, robust POMDP optimization, and testing-effect work already touch multiple components. An accepted IJCAI paper needs a new algorithm/theorem/observation with a defensible literature gap and substantial evidence.

## 2. Mathematical objects and timing convention

Fix one initially calibrated skill first; do not introduce all eight skills until the one-skill subproblem is rigorous.

- Time t = 0,...,T, with fixed, **finite** planning horizon T.
- Hidden mastery M_t in {0,1}. If a learner is unmastered at the beginning of a question, M_t=0.
- Hidden **path event** F_{t+1} = 1{M_t=1 and M_{t+1}=0}, a loss of previously held mastery. Do not conflate this with M_t=0, a BKT posterior drop, or an incorrect response.
- A possible **diagnostic target** is G_t=1 if the skill became mastered and then suffered a mastery-to-nonmastery transition since an explicitly observed/documented baseline, and remains unmastered at decision time t. Tracking G_t requires augmenting the latent state with history; it is **not** a Markov function of current mastery alone.
- Action A_t: select one unused question q from inventory I_t, offer a recovery resource r if its remaining budget R_t permits, wait, or stop and issue a qualified diagnosis / abstention. Restrict actions based on genuinely available questions/resources.
- If A_t=q: observation Y_t in {0,1} is generated from O_theta(Y_t|M_t,q) **before** the question-induced learning transition, matching current V3 synthetic order; then latent state evolves via T_theta(M_{t+1}|M_t,q). This ordering is a *modeling assumption*, not established human cognitive timing. Assistance may also induce learning or forgetting; a pure test may not be noninvasive.
- Resource actions can update M_t without producing an objectively graded answer. Question inventory decreases by one only when an actual question is consumed. A recovery resource decreases the separate allowed resource budget.
- theta belongs to a stated uncertainty set Theta of transition and emission models. These must be justified by data, confidence regions, or unambiguously labeled hypothetical bounds; there is no empirical calibration simply because a simulator contains numerical values.
- Observable history H_t consists of available-item identities and difficulty, past selected actions, answers, resource exposure, timestamps/session boundaries, remaining inventory and budgets. **No true M_t, G_t, or F_t is supplied to the controller**.

The policy pi maps H_t to a distribution over **feasible** actions. It may stop with: diagnosed deterioration, no diagnosis, or abstention. The independent assessment target and historical baseline must be fixed before estimating detection quality.

## 3. One possible falsifiable objective

A primary scientific objective could be minimizing expected diagnosis error + burden:

    inf_pi sup_{theta in Theta} E_theta^pi [
        c_FA * 1{diagnose deterioration while G_tau=0}
      + c_M * 1{deny deterioration while G_tau=1}
      + c_A * number_of_diagnostic_actions
      + c_R * number_of_recovery_resources
      + c_ABSTAIN * 1{abstain}
    ]

subject to action feasibility, finite inventory, T and resource limits, plus an explicitly stated false-alarm constraint such as

    sup_{theta in Theta: P_theta(G_tau=0)>0}
        P_theta^pi(diagnose deterioration | G_tau=0) <= alpha.

Here tau is the stopping time and G_tau depends on the **entire unobserved path**. Define whether undiagnosed late events count as misses; avoid trivial abstention by charging a meaningful abstain cost. This is a conceptual robust POMDP / optimal stopping formulation, and **is not novel by itself**.

An alternative objective emphasizing recovery is the independent, later measured mastery conditional on the same total assessment and recovery dose; the diagnosis and recovery estimands must not be silently substituted for one another.

## 4. Preliminary proposition — assessment can erase evidence of past mastery

**This is an elementary auxiliary lemma derived from common-component overlap / total variation; do NOT advertise as an original IJCAI theorem.**

Consider two hypotheses about hidden mastery *before* the first assessment:

- H_M: the learner is mastered.
- H_U: the learner is unmastered.

The first question emits a binary response Y_1 **before learning**, with

    P(Y_1=1|H_M) = 1-s,    P(Y_1=1|H_U) = g,

where s is slip and g is guess. Let d = |(1-s)-g|.

Under H_U only, **after the first response**, the question causes mastery with probability rho, independent of Y_1. Under H_M, mastery persists, and neither hypothesis incurs an additional hidden model difference after an H_U learner becomes mastered. Subsequent feasible questions/actions can be adaptively chosen from the observed history. Conditional on same observed Y_1 and a mastered post-first-question state, future response/action laws coincide between H_M and the successfully learned H_U branch.

**Proposition (irreducible diagnostic error under restorative probing).** Under equal priors on H_M and H_U, for any number of additional questions and any common observation-history-dependent policy,

    Bayes_error >= rho * (1-d) / 2.

If rho=1 (the first question **certainly teaches** an unmastered learner), equality holds for every finite or infinite number of additional questions:

    Bayes_error = (1-d)/2.

Consequently, later questions cannot disambiguate *original* mastery after the initial question has certainly erased the difference in post-question state.

**Proof.** Let P_M and P_U denote distributions of all observed action/answer histories, including the first answer. Conditional on first answer y, denote the common future law after mastery by Q_y. The H_M history contains the nonnegative probability submeasure P_M(Y_1=y) Q_y, and H_U contains at least rho P_U(Y_1=y) Q_y from the successfully learned branch. Their common overlap, sum_h min(P_M(h),P_U(h)), is therefore at least

    rho * sum_y min(P_M(Y_1=y), P_U(Y_1=y))
      = rho*(1-d).

The minimal equal-prior classification error is one-half the overlap, proving the bound. When rho=1 both hypotheses have the same conditional future law Q_y, giving equality. This uses the standard total-variation testing identity; it is not a novel statistical theorem.

**Example.** With s=1/10 and g=1/4, the initial response separation is d=13/20=0.65. If the first assessment guarantees acquisition (rho=1), the lowest possible equal-prior error is (1-13/20)/2=7/40=0.175, no matter how many further questions are asked. If rho=1/4, the guaranteed lower bound is 7/160=0.04375; this weaker bound is not an equality in general.

**Do NOT confuse this result with Step 103:** Step 103 compares possible earlier *forgetting versus initial weakness* histories that have the same current mastery distribution and post-only observations. The present proposition compares *mastered versus unmastered immediately before an assessment*. Neither is a verified real-world forgetting detector.

**Limitations.** The proposition does not require a finite question bank (so it cannot establish a novel finite-inventory bound). It requires the specified pre-learning response order, an H_M hypothesis unaffected by forgetting at the first transition, a constant rho independent of the answer, and identical future mechanisms once mastered. If successful learning depends on answer, the uniform bound needs a justified lower bound on conditional conversion. If assistance affects future outcomes differently despite identical mastery, the future-common-law assumption fails. This lemma is a **sanity check** for a harder future theory, not a publication contribution.

## 5. Why the research is not yet novel: closest known methods

| Established line | Verified prior-art observation | Specific obligation for this project |
|---|---|---|
| Murray, VanLehn & Mostow (2004), tutorial decision networks | Uncertain teaching state, action impact and lookahead were modeled explicitly | Explain what is not already decision-theoretic tutoring |
| Rafferty et al. (2016), POMDP teaching | State changes, learning/forgetting and diagnostic versus teaching actions are already part of the formulation | Do not claim the POMDP dual role of questions is new |
| Zhang & Hoi (AAAI 2019), partially observable active change detection | Selects constrained observation subsets and detects hidden changes | Show a contribution beyond adaptive sensing/change detection |
| Controlled sensing/change detection literature (2012–2024) | Risk constraints, active action choice and observation-model uncertainty are known | Define the **state-changing** intervention difference and prove it matters |
| Krale, Simão & Jansen (ICAPS 2023), Act-Then-Measure | Joint environment control and costly measurement, with a performance bound | A POMDP which trades information and control is established |
| Gao et al. (AISTATS **2026**), Active Measuring with Delayed Negative Effects | State measurement itself has effects on future outcomes; belief-space online RL is studied | This is a **major new originality blocker** for simply saying probes have side effects |
| Galesloot et al. (IJCAI 2025), robust hidden-model POMDPs | Worst-case policy optimization over uncertain models and formal verification | Do not call uncertainty-set robust POMDP a new algorithm |
| Schuetze, Yan & Carvalho (2025), learning/forgetting model failure on longitudinal study | BKT variants can fit retrospectively yet fail at later-session prediction | Longitudinal out-of-time validation must be part of any empirical claim |
| Carpenter et al. (2008), testing effect | Tests can affect learning/forgetting | Do not treat assessments as passive sensors without measuring their effects |

**Priority reading**, exact sources:
1. Murray et al. (2004), https://publications.ri.cmu.edu/looking-ahead-to-select-tutorial-actions-a-decision-theoretic-approach
2. Rafferty et al. (2016), https://doi.org/10.1111/cogs.12290
3. Zhang & Hoi (2019), https://doi.org/10.1609/aaai.v33i01.33015733
4. Krale, Simão & Jansen (2023), https://doi.org/10.1609/icaps.v33i1.27197
5. Gao et al. (2026), https://proceedings.mlr.press/v300/gao26d.html
6. Galesloot et al. (2025), https://ijcai.org/proceedings/2025/947
7. Schuetze et al. (2025), https://doi.org/10.1007/s40593-025-00508-3
8. Carpenter et al. (2008), https://pubmed.ncbi.nlm.nih.gov/18426072/
9. Doroudi & Brunskill (2017), https://www.cs.cmu.edu/~shayand/papers/EDM2017.pdf

This is a **targeted** screen, not an exhaustive full-text novelty certification. Avoid claiming that the proposed question is unresolved across all published work.

## 6. One precise hypothesis worth attempting to *falsify*

**Candidate H105 (unproven; not established novel):**

A resource-feasible, history-dependent controller that explicitly accounts for action-induced changes in mastery can **trade off diagnostic accuracy against state improvement more effectively under transition-model shift**, compared with a fixed-response-model sequential change detector or standard POMCP baselines, **at the same feasible action inventory, item exposure, and total time/resource cost**.

This is currently a **research hypothesis, not a theorem**. It could already be fully or partially addressed by robust POMDP, active-measurement or dual-control methods. “More effectively” MUST be made numerical before implementation: for example a statistically supported, prespecified improvement in worst-case cost-sensitive error at matched action cost, while not reducing independent final knowledge below a fixed tolerance.

Candidate **new theorem** to investigate, not assert: a *nonvacuous*, problem-structure-exploiting upper/lower bound on attainable misclassification risk and education gain for a finite inventory of diagnostic items that also induce learning, **under an explicitly specified family of learning/forgetting models**, plus an implementable controller that approaches the bound. Ordinary Bayes risk, TV identities, Bellman recursion and generic robust POMDP bounds do not count as originality.

### Falsification / stop criteria

- Compare with exact finite-horizon belief-state dynamic programming for **one concept and 2–4 distinguishable items**. This is the oracle in the tiny case. A purported algorithm cannot beat it on its own model.
- Compare with sequential likelihood-ratio / change-point testing, active sensing, decision-theoretic tutoring, original V3, resource-matched POMCP, and robust constrained POMDP / shielding.
- Vary learning and forgetting rates outside the development simulator assumptions; report null and worse cases, and estimator calibration, not just nominal scenario wins.
- Match **total instructional and assessment exposures**, independent outcome timing, response difficulty, and question inventory. Control computational budget separately (planning simulations/wall time).
- If the “new” method is only a restatement of robust POMDP optimal stopping, **STOP** and pivot.
- Do not use sealed Phase 6 test membership or prior viewed Step95/100/102 development seeds as pristine confirmation.
- Do not enroll humans without genuine sponsor, content, measurement, ethics/privacy, and statistical/QA authorization.

## 7. Monday, November 2 decision sheet

**Completed today:** problem semantics; hidden event vs observed response distinction; feasible finite-inventory action model; explicit uncertainty set and risk objective; an elementary rigorously proved interference lemma; target bibliography; a falsifiable *candidate* hypothesis.

**Still open and externally dependent:**
- Supervisory judgment of the strongest closely related paper and whether H105 is genuinely distinct.
- A nontrivial new theorem or algorithm beyond generic dual control / robust POMDP.
- Model-valid empirical learning effects, out-of-time longitudinal validation, and independent evaluation design.
- Human study signoffs, expert review of content and measurements, practical exposure/time matching.

**Supervisor's decisive questions:**
1. Does the 2026 active-measurement paper or earlier decision-theoretic tutoring already cover the precise H105 objective?
2. Which finite-inventory / state-changing-probe assumption yields a **mathematically new** theorem rather than a standard Bellman recursion or testing lower bound?
3. Can we define an implementable algorithm with a rigorous guarantee **about its executed policy** and realistically evaluate it before January 2027?
4. If not, should we pivot to a narrower theoretical limitation paper or seek another original AI problem?

**Claim boundary:** Engineering readiness = strong for a synthetic study. IJCAI 2027 *main-track scientific readiness* = **not yet established**.
