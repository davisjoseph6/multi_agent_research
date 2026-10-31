# Step 98 — finite-inventory feasibility gate (research-only)

**Status:** Hypothetical mathematical model and read-only analysis. NOT a deployed intervention, approved protocol, human-outcome claim, or IJCAI novelty certificate.

## Why this gate was necessary

The Step 97 uniform-coverage result silently depends on every concept remaining actionable at every decision where the drift bound is invoked. The existing RCT candidate's draft practice bank has **exactly 55 practice questions**: seven for each of Utility, Loss Aversion, Anchoring, Sunk Cost, Framing, Heuristics, and Prospect Theory, but **six for Nudge Theory**. Practice questions are not reusable once answered.

The V3 online selector filters root actions to concepts with unused practice questions. Its internal POMCP rollout holds this root concept set fixed and does not decrement the individual question inventory. That makes a global 55-step feasibility/drift assertion unjustified.

## Mathematically checked single-decision certificate

`src/prototype/step98_finite_inventory_certificate.py` explicitly accepts remaining practice counts for all eight concepts, at most two remaining recovery-resource slots, allowed resource types, and whether the mandatory session warmup forces practice only.

For a *given* feasible probability distribution over the legal actions and an uncertainty box with learning lower bounds \\(p_a^-\\) and per-concept forgetting upper bounds \\(f_j^+\\), it computes

\\[
r_j^-=\sum_a q(a,j)p_a^-,
\qquad
\max_{s:D(s)>0}\mathbb E[\Delta D\mid s]\le
\frac{\sum_j f_j^+-\min_k(f_k^++r_k^-)}{8}.
\\]

Within the explicit rectangular rate model the bound is sharp. It certifies strictly negative **one-step** statewise drift when that right-hand side is negative. These are **assumed** rate bounds, not confidence intervals learned from students.

The suggested `feasible_coverage_mixture` is an exploratory distribution that mixes a feasible primary action with uniform selection across **currently available** practice concepts. This is not V3, V5, V6 or the human-trial A arm, and no such policy has been evaluated for outcomes.

## Immediate counterexamples

1. Initial draft bank: all eight concepts have a practice item, so uniform practice gives the Step 97 hypothetical no-forgetting margin \\(1/1280\\) at **this snapshot only**.
2. After all six Nudge Theory practice questions are consumed, no remaining legal action can target Nudge in the V3 root interface, even with two unused recovery slots. With Nudge unmastered, the deficit has zero expected improvement in the no-forgetting model. Hence a strict global statewise drift guarantee fails.
3. Once all practice questions are exhausted, no additional practice-stage choice exists; the certificate refuses to run, rather than quietly pretending questions replenish.
4. Even at full initial inventory, a forgetting upper rate of 0.001 per mastered concept invalidates the nominal randomized-coverage certificate under the default 0.05 practice learning rate.

The finite 20/20/15 session schedule has two resource slots *per session*, not a global two-slot budget. This diagnostic does not independently certify chronological session transitions, learner-specific item difficulty, action effects, BKT correctness, or the POMCP internal search distribution.

## Irreducible finite-horizon limitation

Even if every conditional opportunity to learn an unmastered concept has at most success chance 0.05 for a practice question and 0.14 for a recovery action, **six** practice opportunities and **six** resource opportunities yield a strictly positive no-learning probability of at least \\(0.95^6\times0.86^6\\), conditional on the model's stated event-probability bounds and opportunity counts. This does not estimate the actual non-recovery probability in the RCT and does not imply that all six resources would target that concept.

## What remains essential for Monday

1. Researcher executes the new focused tests and full regression suite.
2. Supervisor chooses what the primary scientific claim is, identifying an actual novelty gap relative to adaptive POMDP teaching and risk-aware shielding.
3. A new finite-horizon planner *if justified* must track full inventory and session boundaries in its generative rollouts; this is a nontrivial policy change requiring held-apart development and evaluation.
4. A quantitative comparison must use fixed dose/resources, matched learners and independent post-assessment, plus computation costs and uncertainty intervals, while preserving negative or null scenarios.
5. Human enrollment stays prohibited until true content reviews, measurements, statistical decisions, institutional/ethics/privacy determination and deployment signoffs are complete.

The existence of this mathematical diagnostic **does not raise project completion percentage or establish IJCAI acceptance likelihood**.
