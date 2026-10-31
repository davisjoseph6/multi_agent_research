# Step 106 — Focused originality adjudication and *proof obligation*, not another prototype

**Prepared:** 2026-10-31. **Purpose:** Decide whether the Step105 research direction merits a new algorithm, and prepare a supervisor-ready research statement by 2026-11-02.

**Status:** preliminary, literature-grounded **risk assessment**. This is **not** a complete systematic review, a priority/novelty certificate, a peer-reviewed theorem, an empirical teaching-effect result, or a released human study. Paper descriptions below are based on the accessible primary publisher article text (Rafferty) and official abstracts (others) rather than asserting that every full proof was audited. This memo adds documentation only; no frozen results or RCT policies changed.

## Decision in one sentence

**The broad Step105 proposal is not new as stated.** Decision-theoretic teaching, belief-dependent diagnostic/teaching actions, active measurement with state effects, and uncertain-transition robust POMDPs already exist. A narrower unproven opportunity might concern *diagnosing the path event of prior forgetting with noisy, state-changing measurements and nonreusable question inventory*. Treat this as an **unverified novelty candidate**, not as an established gap.

## Closest work: what is already solved or modeled

| Existing work | What the work actually includes | Why a Step105 claim is at risk | Unresolved for our project (NOT proven absent from literature) |
|---|---|---|---|
| Rafferty, Brunskill, Griffiths & Shafto, *Faster Teaching via POMDP Planning*, Cognitive Science 2016 | Explicit POMDP state = learner knowledge, observations = student answers/behavior, actions = quizzes, examples, or questions with feedback; long-horizon control of learner knowledge and diagnostic information; simulations and human participants; comparison of learning models. | **Very high** risk: partial observation, tradeoff between teaching and diagnosis, feedback actions and model mismatch are already addressed. | Does this paper distinguish a *historical latent forgetting event* rather than current mastery? Does it prove a tight guarantee for *nonreusable per-concept item inventories* and rate ambiguity? These are research questions to verify in full text, not asserted omissions. |
| Gao et al., *Active Measuring in Reinforcement Learning With Delayed Negative Effects*, AISTATS 2026 | Actively Observable MDP, choice to measure latent state, measurement has future effects; formulated as periodic POMDP; belief-state online RL and sequential Monte Carlo for unknown static model parameters; digital-health application. **Its official abstract states measurement reveals the true latent state.** | **High** risk: sensing with delayed intervention-induced state effects is established; cannot market “assessment can change knowledge” as a first. | Our graded question gives a noisy slip/guess observation, not the true state. Does this distinction enable a **nontrivial new result** rather than simply replacing its observation kernel with an ordinary POMDP? Need a proof, not intuition. |
| Krale, Simão & Jansen, *Act-Then-Measure*, ICAPS 2023 | Joint control and active measurement with an act-then-measure heuristic and a performance-loss bound in action-contingent noiselessly observable MDPs. | **High** risk: formal measurement/control tradeoffs and guarantees exist. | Are there structural lower bounds specific to *restorative, noisy, finite-stock* assessments beyond general POMDP control? Unverified. |
| Rasouli & Saghafian, *Robust Partially Observable Markov Decision Processes*, working paper 2018 | Ambiguous transitions and noisy observations; medical tests with errors and uncertain treatment effects; dynamic programming, sufficient information state. | **Very high** risk: uncertain effects of diagnostic/treatment actions and noisy sensors already coexist in formal robust POMDPs. | Does a narrower *path-history diagnosis* and coupled consumable item stock yield a new computable certificate, or just a state-augmented robust POMDP? This is the main technical obstacle. |
| Zhang & Hoi, *Partially Observable Multi-Sensor Sequential Change Detection*, AAAI 2019 | Active selection of a limited subset of sensors plus sequential changepoint detection, with theoretical analysis. | **High** risk: resource-limited active detection is established. | Their published abstract does not claim that sensing itself changes the target latent state; investigate complete paper before claiming a separation. |
| Galesloot et al., *Robust Finite-Memory Policy Gradients for Hidden-Model POMDPs*, IJCAI 2025 | Robust policy optimization for uncertain hidden-model POMDPs. | **High** risk: generic ambiguity-set robust belief planning is not new. | Any new theorem must use *special structure* and improve a relevant certificate/complexity/sample bound. |

## Essential correction to the Step105 idea

A noisy response versus a noiseless readout is a **model distinction**, not in itself an original method. Generic POMDPs already have arbitrary observation kernels. Likewise, a per-item remaining inventory is an observable part of the state, and a historical forgetting indicator can be added to a POMDP's latent state. These augmentations by themselves are standard modeling operations.

Therefore **reject** the following claims as IJCAI main-track contributions:

- “First to combine POMDPs, noisy student answers, and teaching interventions.”
- “First to recognize diagnostic tests change the latent state.”
- “First to use a budget-limited belief-aware recovery action.”
- “First to model forgetting and a finite question bank in a robust POMDP.”
- “BKT is generally non-identifiable.”
- “Step105's total-variation lemma is a novel theorem.”
- “Step99 is better than V3.” The two 30-seed controlled comparisons are mixed or unfavorable, with descriptive intervals all including zero.

## One candidate result whose truth, utility and novelty must be investigated

**Working candidate: exact finite-budget historical-change diagnosis with *restorative* assessments.** Treat the target as a **path event**: whether a mastered concept underwent an actual mastery→nonmastery transition during a specified window, rather than whether it is currently unmastered. Distinguish this from an ordinary change-point statistic, and require questions to be unique and potentially teaching.

A plausible *research deliverable* would comprise **all** of the following:

1. **Structural proposition** with a nonvacuous dependence on an actual nonreusable question inventory and on state-changing probes, not merely a total-variation identity. State exactly which learning, forgetting, slip/guess bounds are known and whether probes can depend on earlier answers. Prove both a lower bound on achievable diagnostic error and a matching or explicitly quantified upper bound attained by a feasible controller in a nontrivial model family.
2. **Executable algorithm** that uses only observable history to choose an available question, a recovery action, or an explicit abstention. It must satisfy the original question and recovery budgets and implement the exact assumptions of any theorem.
3. **A powerful baseline comparison:** an **exact small-instance augmented-belief finite-horizon POMDP oracle** (e.g. one skill, two to four nonreusable distinct questions), an active sequential test, and relevant robust/constrained POMDP planners. The oracle is a reference, **not** a competitor the new policy can improve upon under exactly the same model/objective.
4. **Calibrated/agnostic evaluation:** vary uncertainty in transition/observation models, actually report confidence/identifiability behavior, use matched interventions and independent assessment. Reused 150000–150029 synthetic learner seeds and the previously inspected V6 development scenarios **cannot become a new confirmatory set**.
5. **Independent novelty review:** show how the proposition exceeds generic state-augmentation, robust Bellman recursion, standard Fano/Le Cam/TV testing bounds, and existing controlled-sensing/dual-control theory.

**Project STOP rule:** If the strongest formal result reduces to a standard finite-horizon belief-state dynamic program or an elementary total-variation lower bound, there is **no established main-track novelty** and the hypothesis must be revised or the research question pivoted.

## Monday, November 2: minimal viable research checkpoint

**P0: mandatory**

- Freeze V6 negative findings, Step100/102 mixed results, Step103 elementary equivalence, Step105 elementary restorative-interference lemma; **do not rewrite negatives**.
- Read Rafferty 2016's formulation and experimental design, Gao 2026's AOMDP assumptions, and Rasouli–Saghafian's robust-POMDP problem formulation. Mark the **exact equation** whose assumptions fail for the proposed assessment model.
- Write a single 150–250-word *novelty statement* containing: established prior work; new structural restriction; one candidate theorem with concrete assumptions; why that theorem would not follow immediately from prior work; one stringent baseline that might disprove any advantage.
- Ask a research supervisor / mathematical collaborator to identify the closest counterexample and prior paper **before** requesting another large code change.

**P1: only after P0 survives**

- Construct the augmented latent state and finite-inventory admissible action set for a one-skill, 2–4-question example. Derive the exact Bellman recursion and Bayesian diagnosis risk **on paper first**. Do not implement until it can be compared mathematically with a genuinely novel proposed bound.
- Determine whether the historical event is distinguishable given the recorded pretransition history. A model in which distinct histories induce exactly the same law cannot be rescued by adding more post-only questions.
- Set an explicit pass/fail criterion for meaningful improvements over strong cost- and dose-matched baselines; declare losses.

**P2: external / cannot be fabricated**

- Real-human trial approvals, expert validation of the 95 draft items, 32 resource texts, fatigue instrument, legal/privacy/stats/independent QA review.
- Empirical teaching-action effectiveness, independent learning outcome calibration, untouched evaluation design, and scientific manuscript novelty signoff.

## Supplied source links and verification status

- Rafferty et al. (2016), complete publisher article text accessible at https://onlinelibrary.wiley.com/doi/10.1111/cogs.12290. Key sections: teaching as POMDP; learner models; experimental pedagogical actions; human results. DOI 10.1111/cogs.12290.
- Gao et al. (AISTATS 2026), official abstract/metadata https://proceedings.mlr.press/v300/gao26d.html. Measurement described as **revealing true latent state**, yet delayed environment effects exist. Full technical proofs require further examination.
- Krale et al. (ICAPS 2023), official abstract https://ojs.aaai.org/index.php/ICAPS/article/view/27197.
- Rasouli & Saghafian (2018), https://www.hks.harvard.edu/publications/robust-partially-observable-markov-decision-processes (official working paper abstract).
- Zhang & Hoi (AAAI 2019), https://ojs.aaai.org/index.php/AAAI/article/view/4519.
- Galesloot et al. (IJCAI 2025), https://ijcai.org/proceedings/2025/947.
- IJCAI 2027 official call https://2027.ijcai.org/ijcai-2027-call-for-papers-main-track/ (abstract **2027-01-04**, paper **2027-01-11**, both 23:59 AoE).

**Final assessment:** A precise mathematical question exists, but its purported *originality* and *solvability within the submission calendar* are **NOT YET ESTABLISHED**. Recommendation: stop building new versions of the simulator, devote the remainder of the weekend to mathematical proofs, source verification, and a supervised problem selection.
