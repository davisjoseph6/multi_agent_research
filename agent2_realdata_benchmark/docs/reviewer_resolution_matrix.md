# IJCAI — Reviewer Resolution Matrix

Version: 0.1
Status: Initial evidence audit
Source submission: IJCAI-ECAI 2026, submission #3789

## Purpose

Track every substantive reviewer criticism against:

1. The original rejected manuscript.
2. The supervisor's research instructions.
3. The approved Phase 1–5 research plan.
4. Existing experimental and implementation evidence.
5. Remaining scientific and engineering work.

A completed software component is not automatically evidence
of successful pedagogical intervention.

A supervisor-approved plan is not automatically an executed
or experimentally validated result.

## Resolution matrix

| ID | Criticism or requirement | Current evidence | Status | Required next work |
|---|---|---|---|---|
| R01 | Pedagogical recovery actions are unclear. | Recovery controller proposes optional hint and scaffolding. Supervisor specifies summary, easier question, worked example, and Socratic hint with reattempt. | PARTIAL | Freeze the complete action catalogue and instructional content; distinguish proposal, selection, delivery, and outcome. |
| R02 | The recovery condition A2-prime assumes the existence of an effective recovery policy. | Synthetic recovery machinery and observational ASSISTments follow-up audits exist. | OPEN | Formulate a testable action-effect condition; prove the appropriate conditional result and evaluate action effects using suitable intervention evidence. |
| R03 | Corollary 1 and T_max are insufficiently explained. | Original theorem and corollary are available. No independent formal audit is recorded in Phase 6. | OPEN | Audit all definitions, assumptions, proof steps, constants, horizon constraints, and failure cases. |
| R04 | The algorithms and their components are insufficiently explained. | Frozen event detector, controller, execution contracts, SQLite journal, and synthetic tests exist. | PARTIAL | Write complete end-to-end pseudocode, define all inputs and outputs, and connect it to the proposed pedagogical planner. |
| R05 | Evaluation uses simulated learners rather than real data. | ASSISTments real-data preprocessing and predictive validation exist. Training-only recovery follow-up feasibility is documented. | PARTIAL | Clearly separate real-data prediction from intervention effectiveness; perform further evaluation only under an appropriate frozen protocol. |
| R06 | Appropriate educational-policy baselines are missing or insufficient. | BKT and NeuralCD predictive baselines exist. | OPEN | Specify and implement fixed recovery, greedy, matched-dose, always-on, and event-triggered policy comparisons where valid outcome data permit. |
| R07 | The DKT and alternative state-estimator comparisons are inadequate. | Frozen BKT and NeuralCD results exist. | OPEN | Audit H1 and complete the prespecified estimator comparisons, calibration analysis, and independent evaluation. |
| R08 | Recovery thresholds and detection need empirical justification. | Frozen event-detection policies and validation results exist. | PARTIAL | Document selection, sensitivity, distinction between predictive entropy and epistemic uncertainty, and the status of hysteresis. |
| R09 | A concrete worked educational scenario is missing. | Supervisor specifies a Behavioral Economics study and four pedagogical recovery actions. | PARTIAL | Produce a complete trace from learner response through diagnosis, detection, action selection, presentation, and independent recovery probe. |
| R10 | Reproducibility of the original evaluation is inadequate. | Phase 6 evidence manifest and synthetic fault-evaluation report exist; 180 regression tests were reported passing. | PARTIAL | Audit dataset provenance, seeds, splits, environments, baselines, executable experiments, and paper-to-code traceability. |
| R11 | Student-related ethical concerns have not been adequately addressed. | Software implements abstention and permission checks. | OPEN | Obtain formal ethics approval or institutional determination before recruitment; specify actual consent, privacy, withdrawal, access control, and adverse-event procedures. |
| R12 | Recovery effectiveness has not been demonstrated. | Training-only shared-skill follow-up audit contains 126,995 observational transitions. Simulation tests establish software behavior. | OPEN | Define and evaluate independent recovery probes and learning outcomes; do not interpret observational association as an intervention effect. |
| R13 | Computational savings require valid policy comparisons. | Event-triggering and simulation-only orchestration have been implemented. | OPEN | Compare planning calls, intervention count, runtime, fatigue, and recovery outcomes against matched baselines. |

## Existing Phase 6 evidence

The following artifact locations are based on the completed
research workflow and must be checked against the repository.

- docs/data/bkt_v1_frozen.json
- docs/data/neuralcd_v1_frozen.json
- docs/data/event_detection_v1_frozen.json
- docs/data/disagreement_v1_frozen.json
- docs/data/recovery_feasibility_train_v1.json
- docs/data/recovery_followup_train_v1.json
- docs/data/recovery_shared_skill_train_v1.json
- docs/data/recovery_fault_evaluation_v1.json
- docs/data/phase6_evidence_manifest_v1.json

## Approved scientific hypotheses

H1: State-estimation accuracy and reliability.

H2: Recovery effectiveness measured using independent probes
and post-test learning.

H3: Event-triggered switching efficiency relative to
always-on planning.

No hypothesis is marked confirmed by this matrix.

## Evidence boundaries

The present work does not establish:

- causal effectiveness of hints or scaffolding;
- improved student learning from the recovery controller;
- existence of an effective recovery action in every state;
- a validated real-world recovery-time guarantee;
- exactly-once delivery in a production environment;
- completion of an approved human intervention study.

The held-out test gate remains closed.

## Next review

Audit the original manuscript's formal definitions,
Assumptions A1–A5, Theorem 1, Corollary 1, Proposition 2,
and Algorithms 1–2.

Do not change frozen research artifacts during this audit.
