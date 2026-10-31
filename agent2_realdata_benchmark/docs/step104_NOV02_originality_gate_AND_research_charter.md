# Step 104 — IJCAI 2027 originality gate and Monday research charter

**Prepared:** 2026-10-31. **Decision target:** Monday, 2026-11-02.  
**Status:** Research strategy and *selected literature* triage, not a comprehensive systematic review, novelty certificate, algorithm result, statistical preregistration, or approval for a human experiment.  
**Existing research branch:** `research/ijcai2027-nov02-evidence-gate`. No experimental source files or frozen results changed by this memo.

## Executive decision

**NO-GO to submit the existing V3/V6/Step99 work as a paper claiming:**

1. novel POMDP teaching (known prior work);
2. an executable universal Lyapunov/negative-drift self-healing guarantee (original V3 counterexample and finite inventory violate the needed assumptions);
3. V6 or Step99 recovery superiority (prespecified synthetic comparisons failed their screens);
4. a generally non-identifiable BKT/HMM (false in general; Step103 is a much narrower observational-equivalence example);
5. a real-student causal recovery benefit (no authorized/enrolled RCT or measured human outcome).

**Conditional GO for investigating one original research question** if and only if a research mentor can specify a *precise novel object* (algorithm, theorem or substantive new problem), the strongest two or three closest comparators, and a reproducible falsification experiment that cannot be trivially met by existing methods.

For the Monday checkpoint, do not alter the RCT branch or create Step 105 as another simple simulator. Advance a research thesis only if an originality gap survives the literature.

## Latest source-derived evidence

- On `20c5406093a090795faece3a761a17fdf0beb909`, the researcher reported **1,263/1,263 tests passed**, **21/21 Step 103**, and clean working tree.
- Original V6 five-scenario recovery screen: **NO-GO**; the 30-seed individual V6-versus-its-no-recovery results were unfavorable or uncertain in multiple cases. These are model-defined synthetic mastery differences, not human treatment effects.
- Step 100 30 paired development seeds/scenario, extra resources allowed: Step99 minus V3 posttest mean `[+0.006250,-0.018750,-0.004167,+0.037500]` for nominal, half-learning, noisy-observation, forgetting-shift environments. Every descriptive interval included zero.
- Step 102 30 paired **same development seeds**, 55 questions and zero recovery actions per arm: Step99 minus V3 posttest mean `[-0.004167,-0.037500,+0.008333,-0.035417]` in that scenario order. Every descriptive interval included zero. This experiment **does not test recovery**.
- Step 103: under a *restricted fixed-state binary model*, different unobserved histories with the same current-state distribution generate identical future observation distributions. A hypothetical observed pretransition answer can partially distinguish those two histories; the formula `TV=f|1-slip-guess|` applies only to the specified pair of models. Not a new BKT identifiability result.

The original JSON files remain local to the researcher's workstation. The memo relies on the researcher's terminal outputs and the previously committed evidence audit; no independent experiment has been rerun here.

## Closest verified literature and risk to originality

| Work | Established contribution from source abstract/full description | Originality overlap to investigate |
|---|---|---|
| Murray, VanLehn & Mostow (2004), *Looking Ahead to Select Tutorial Actions* | Decision-theoretic tutorial-action selection using uncertain tutorial state and lookahead, tested with simulated learners | Already anticipates multiobjective, uncertain, planned remediation; **must cite**, directly responds to IJCAI 2026 review |
| Rafferty, Brunskill, Griffiths & Shafto (2016), *Faster Teaching via POMDP Planning* | POMDP planning to choose sequential instruction under uncertain student knowledge and model assumptions, with empirical learner evaluations | Rebuilding POMCP tutoring with belief tracking is not an original AI technique |
| Doroudi & Brunskill (EDM 2017), *The Misidentified Identifiability Problem of BKT* | Under mild conditions standard BKT is identifiable; separately distinguishes semantic model degeneracy | Do not generalize the Step 103 indistinguishable-hidden-history example to all BKT/HMM |
| Zhang & Hoi (AAAI 2019), *Partially Observable Multi-Sensor Sequential Change Detection* | Adaptive measurement selection under partial observability with theoretical analysis and data experiments | Already combines limited probing, change detection and active observation; a basic “budgeted change detector” is not enough |
| Mazzi, Castellini & Farinelli (ICAPS 2021; AI 2023), *Rule-based/Risk-aware shielding for POMCP* | Analyzes POMCP belief-action traces, limits risk, blocks inappropriate actions; also treats potential resource depletion in application scenarios | Generic belief-risk shields and action-feasibility gating are established |
| Russo, Metelli & Restelli (AISTATS 2025), *Achieving sqrt(T) Regret in Average-Reward POMDPs with Known Observation Models* | Regret bounds for learning unknown POMDP transitions with known observation model | Merely proposing uncertainty-aware belief planning with transition estimation is insufficient |
| Galesloot et al. (IJCAI 2025), *Robust Finite-Memory Policy Gradients for Hidden-Model POMDPs* | Robust optimization across sets of POMDP models with formal policy evaluation and numerical experiments | **Direct main-track precedent**: hidden-model robustness with provable planning already exists |
| Galesloot et al. (ECAI 2025; published online 2026), *Pessimistic Iterative Planning with RNNs for Robust POMDPs* | Constructs robust policies over transition/observation ambiguity sets by iterating worst-case model selection and policy construction | A plain “robust POMDP for uncertain learners” claim would be heavily overlapped |

**These papers are a targeted minimum list, NOT proof that no further closely related work exists.** Read full proofs, assumptions, benchmarks, follow-on citations and recent publications before asserting novelty. Distinguish established source description from our own proposed hypotheses.

### Primary references

1. Murray et al. 2004, https://publications.ri.cmu.edu/looking-ahead-to-select-tutorial-actions-a-decision-theoretic-approach
2. Rafferty et al. 2016, https://doi.org/10.1111/cogs.12290
3. Doroudi & Brunskill 2017, https://www.cs.cmu.edu/~shayand/papers/EDM2017.pdf
4. Zhang & Hoi 2019, https://doi.org/10.1609/aaai.v33i01.33015733
5. Mazzi et al. 2021, https://doi.org/10.1609/icaps.v31i1.15968
6. Mazzi et al. 2023, https://doi.org/10.1016/j.artint.2023.103987
7. Russo, Metelli & Restelli 2025, https://proceedings.mlr.press/v258/russo25b.html
8. Galesloot et al. IJCAI 2025, https://ijcai.org/proceedings/2025/947
9. Galesloot et al. ECAI 2025, https://doi.org/10.3233/FAIA251391

## Single *candidate* research charter — budgeted, model-uncertain change diagnosis

**Working question (NOT a novelty claim):** In a finite question bank, where practice also changes hidden knowledge and where response models/forgetting rates are uncertain, can a history-dependent controller decide when it is *epistemically justified* to call an observed response deterioration a latent forgetting event, rather than abstaining or collecting further evidence, with a useful *finite-budget* bound?

Require one explicit formal object:
- Hidden state: concept mastery plus optional forgetting-event flag, with action-dependent transition and observation channels. State precisely when “forgetting” is an observable quantity, a path event, or only a model-defined latent event.
- Observed state: all question IDs/difficulties, responses, time/order, assistance dose and remaining item/resource inventory. NO oracle access to true latent mastery.
- Unknown model: a nonempty set of admissible transition/observation models from data-constrained uncertainty bounds; do not insert fabricated human transition rates as empirical facts.
- Decisions: probe with a legally available assessment/practice item, offer an available resource, decline to assert a decline event, or proceed without intervention. Fix per-decision cost and a total assessment/recovery budget.
- Scientific objective: define a **testable** risk criterion (false-alarm constraint, minimax regret, calibrated posterior reliability, or cost-sensitive value of information); distinguish event detection from forecasting and from instructional effect.

### A nontrivial theorem would need to beat a real baseline

The Step 103 post-only equality is a direct Markov-observational equivalence argument and therefore **does not qualify** as the sought theorem. A potentially useful new theorem would have to handle, for example, **controlled probing that itself induces learning and exhausts a finite question bank under model uncertainty**, and provide a nontrivial lower/upper performance bound tied to an executable algorithm. That remains an **open obligation of this project**, NOT a known original result.

Compare specifically against: optimal finite-horizon small POMDP oracle; belief-state sequential likelihood ratio/optimal stopping; active change detection and bandit sensing; risk-aware POMCP shielding; robust hidden-model POMDP; naive response-pattern gate (V6). If the new approach offers no meaningful advantage or no distinct mathematical guarantee, do not call it original.

### Explicit stop condition

Stop this avenue for IJCAI 2027 if, after full comparison, it reduces to standard Bayes-optimal sensing, change-point testing, robust POMDP planning, or resource-constrained shielding with a different vocabulary. A learning-domain application may remain scientifically useful without meeting main-track novelty expectations.

## Fixed deliverables to complete by 2026-11-02

| Priority | Deliverable | Objective completion criterion | Current status |
|---|---|---|---|
| P0 | Reproducibility baseline | Commit/source hashes, 1,263 passing tests, stored Step95/100/102/103 reports | **Software checks reported complete**; report files local |
| P0 | Claim audit | Negative V6, mixed Step100/102 and restricted Step103 result preserved without overstating | **Complete as documentation** |
| P0 | Literature comparison | Each required paper mapped to a specific component of proposed novelty; full-text priority for Murray, Rafferty, Mazzi, Galesloot, Zhang | **Short targeted audit complete; deep review outstanding** |
| P0 | Primary problem signoff | One sentence naming the novel object; closest existing method; explicit experimental falsifier | **OPEN — supervisor review required** |
| P1 | Formal mathematical research hypothesis | Rigorous environment, feasible action set, model ambiguity, theorem/proposition; test counterexamples | **OPEN** |
| P1 | Experimental credibility plan | Resource/time matched controls, common opportunity-level randomization, realistic measurement, provenance and heldout separation | **OPEN** |
| P2 | Human RCT release | Genuine reviews of 95 items/32 resources/fatigue, measurement protocol, sponsor, ethics/privacy, deployment signoffs | **BLOCKED; must NOT simulate signoffs** |

**What NOT to do by Monday:** claim a validated self-healing method, discard negative runs, optimize on the existing development outputs then report them as untouched, or enroll a single real participant.

## IJCAI 2027 external requirements and dates

Official call: https://2027.ijcai.org/ijcai-2027-call-for-papers-main-track/

- **Abstract:** 2027-01-04, 23:59 Anywhere on Earth.
- **Full paper:** 2027-01-11, 23:59 Anywhere on Earth.
- **Main-track acceptance criterion:** significant, original, previously unpublished AI results.
- **Length:** 7 pages of body (all tables/figures) plus up to 2 additional pages for references, 9 pages total.
- **Double blind:** anonymize the manuscript, *supplementary data and code* (including author-identifying repository URLs, hard-coded filesystem paths and metadata).
- **Reviewing:** designate a qualified author for reciprocal reviewing unless genuinely exempt.
- **Reproducibility:** publish sufficient precise assumptions, proofs, experimental parameters, negative results, data/compute provenance and procedural details.
- **LLM assistance:** models do not qualify for authorship; the human authors bear complete responsibility for originality, accuracy and plagiarism checking and should comply with the call's AI-disclosure requirements.
- **Human study ethics:** IJCAI's ethics statement does **not** substitute for separate institutional, privacy, consent and measurement approvals.

See also https://2027.ijcai.org/reproducibility/.

## Monday supervisory conversation: five sentences to resolve

1. “Our previously rejected V3 theoretical claim has an explicit execution counterexample; we have preserved it.”
2. “The V6 recovery ablation and two controlled Step99 development comparisons do not show broad efficacy or superiority.”
3. “Our original teaching and robust-planning ideas overlap multiple prior papers, including an IJCAI 2025 main-track work.”
4. “We propose to investigate **finite-budget, model-uncertain deterioration diagnosis with action-dependent learning and legal-question constraints**, but novelty has **not** yet been demonstrated.”
5. “Could you help decide whether this is a publishable novel AI problem, identify the closest strong baselines, and review a specific theorem statement before we invest in another implementation?”

**Final decision:** Code correctness and transparent negative evidence are real progress, but **IJCAI research-readiness remains NO-GO pending an original, independently reviewed result**.
