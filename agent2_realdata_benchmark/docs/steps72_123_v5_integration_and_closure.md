# IJCAI 2027 — Steps 72–123: V5 integration, evidence, and closure register

**Status: SYNTHETIC SOFTWARE ONLY; NOT READY FOR HUMAN RECRUITMENT.**

This document is a completion audit, not a claim of completing 52 research and
operational milestones. Reference implementation consists of commits through
`0f3dfc9` plus Step 93–95 additions. The V5 integration in this additive package
has been tested independently of the user's WSL repository; run the complete
WSL suite before acceptance.

## Reproducible V5 findings

- The immutable V3 planner at seed 71, simulations 240, can choose an already
  mastered concept and have **zero** expected one-step latent-state deficit reduction.
- V5 is a distinct **hybrid**: V3 POMCP with a deterministic positive-belief-gain
  safeguard *only when V3's chosen action has exactly zero modeled belief gain*.
- In a paired synthetic decision audit (13 belief scenarios, resource budgets 0/2,
  seeds 71/72, simulations 25), there were **52 cases, 33 original zero-gain
  cases, 29 guard interventions, and 4 remaining zero-gain cases**. The four
  remaining cases had no positive-gain candidate because all concepts were
  believed mastered. These are **decision outputs**, not simulated student outcomes.
- In a three-participant complete synthetic run (simulations 12), 58 V5 planner
  decisions had **zero guard interventions**. In ordinary BKT settings probabilities
  are often strictly between zero and one, making a strictly-zero-gain trigger rare.
  Thus, a safeguard that improves a mathematical edge case may be behaviorally
  inactive in the actual study workflow.
- No evidence here establishes superior learning, true-state drift, robustness
  to incorrect beliefs, or a real-world treatment effect.

## V5 database and action provenance

`PolicyLockedGuardedProtocolEngine` is an **opt-in** subclass, taking the exact
`BeliefSupportGuardedPOMCP` class. It refuses conversion of existing V3 SQLite
protocols into V5, stores a source/configuration fingerprint, and atomically
includes the full raw-and-guarded planning trace in each new action-selection
**event**. This trace remains after a completed pending action has been cleared.

**Limitation:** the old V3 engine is unchanged and cannot be made to reject
opening a V5 database from within the new V5 module alone. Never intentionally
reuse a V5 database for raw V3. The V5 auditor checks the stored policy marker;
this is an engineering development safeguard, not production tamper resistance.
SQLite records are not cryptographically append-only; an actor with DB access
could manipulate events and the lock. No personally identifiable data are
permitted in this synthetic environment.

## Step-by-step closure requirements

| Steps | Implemented evidence | Still needed before **genuine closure** |
|---|---|---|
| 72–74 | Separate fixed, greedy, rule-based, V3 POMCP and V5 hybrid candidate classes | A stable common policy contract, independently checked pseudocode, pre-specified experimental identity |
| 75–78 | Three-arm scaffold and conceptual comparisons | Signed primary/secondary hypotheses, ITT estimand, comparable time/content dose and randomization protocol |
| 79–81 | Recovery budget, drift counterexamples, hashes/configuration | Scientifically meaningful deterioration measure, complete seed provenance, independent architectural review |
| 82–85 | Eight binary latent states, synthetic observation and BKT updates | Real-data model calibration, goodness-of-fit and model-misspecification checks |
| 86–90 | Initial-deficit caveat, recovery actions, fixed/greedy/rule baseline | Validated deterioration trigger and harmonized resource-dose semantics |
| 91–92 | Eight-concept POMCP-style sampled-history search and Group A synthetic integration | Independent algorithm audit, proper belief updating under partial observability, runtime/performance evaluation |
| 93–94 | Conditional finite-horizon drift theorem, exact finite-state checks, V3 drift counterexample | Faithful controller-level assumptions and independent mathematical review; remove unsupported guarantees |
| 95 | Synthetic sensitivity, V5 paired-input decisions and policy-locked protocol | Independent multi-seed/scenario benchmarking with matched learning opportunities, costs, uncertainty and ablations |
| 96–100 | Structural item schema, synthetic fixtures, 8 concepts and 6 Bloom labels | Real blueprint, substantial authored Behavioral Economics items, reviewed scoring rubrics |
| 101–106 | Review-status gate and version hashes | Genuine independent subject-expert review, psychometrics, content-leak testing, real recovery explanations, validated fatigue scale, content freeze |
| 107–112 | Synthetic three-arm protocol including opt-in V3/V5 A, fixed C and greedy B | Final experimental comparator choice, policy dose/cost comparison, independent fidelity audit |
| 113–117 | 16-question pre/post, 3x practice and fatigue, loopback-only synthetic browser | Usability testing, accessible interfaces, real instructional content and approved scheduling |
| 118–122 | Synthetic-ID restriction, disposable dev token, SQLite replay/audit | Identity/consent integration, privacy assessment, retention, access control, security/load/accessibility reviews, disaster recovery |
| 123 | Nine-participant V3 and three-participant V5 complete **synthetic** rehearsals | Independent full-scale dry-run with final approved instruments and sponsor go/no-go; no human enrollment before authorization |

## Mathematical release blocker

The finite-horizon theorem says that if a **uniform, strictly positive**
negative-drift margin holds at every relevant non-target state for the actual
executed policy, a bounded expected truncated hitting-time and Markov
nonrecovery bound follow. The original V3 counterexample refutes that
antecedent for at least one state and planner configuration. V5's **positive
belief-expected** acquisition does not establish **positive true-state** drift
when its beliefs are wrong; no unconditional theorem applies.

## Scientific methodology items to agree with supervisors

1. Name the actual A policy: historical rule-based self-healing, V3 POMCP,
   or V5 hybrid POMCP, and freeze it before randomization. They are not the
   same treatment.
2. Identify the primary contrast (suggested **A vs B**) and independent
   post-test score endpoint, adjusted for baseline; treat A vs C as secondary
   unless specified otherwise. No analysis of human outcomes has occurred.
3. Define the participant population, randomization, missing-data strategy,
   sample-size justification and statistical analysis plan before recruitment.
4. Use matched and reviewed assessments with an item-level leakage and
   difficulty audit; do not put correctness answers into browser payloads.
5. Require institutionally appropriate ethics/privacy/security review and
   signed ownership of experimental materials. Self-attestation is insufficient.

## Evidence gate

**Current disposition: ENGINEERING TESTBED VERIFIED IN ISOLATION; HUMAN STUDY
NO-GO.** Green unit/integration tests cannot count as expert item review,
psychometric validation, ethics authorization, empirical calibration, or
independent mathematical peer review. Preserve all unfavorable simulation
results and code-locked policy versions.
