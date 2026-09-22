# IJCAI — June 22 Team Suggestions Reconciliation

Version: 0.1
Status: Research-planning reconciliation, not experimental results.

## Source documents

1. Rejected IJCAI-ECAI 2026 manuscript.
2. IJCAI rejection review.
3. Supervisor's post-rejection suggestions.
4. Supervisor-approved Phase 1–5 document.
5. Research-team suggestions dated June 22, 2026.
6. Committed Phase 6 evidence manifest and theory audits.

The June 22 document proposes 12 phases and 52 steps.

The separate Phase 1–5 document is reported as
supervisor-approved.

Approval of the additional Phases 6–12 is not established
by the supplied evidence.

Approval of a plan does not establish its implementation.

## Proposed phases and current evidence

| Phase | Team proposal | Current evidence | Status |
|---|---|---|---|
| 6 | Real-data learner-state evaluation, comparisons and calibration. | Frozen ASSISTments BKT and NeuralCD validation; other proposed comparisons and independent confirmation remain to be established. | PARTIAL |
| 7 | Action-effect model and state-aware recovery selection. | Event detection, option proposal and simulated execution exist; validated pedagogical action-effect selection does not. | PARTIAL |
| 8 | A narrower recovery theorem and model-error guarantees. | T01 and T02 identify mathematical gaps; other proof obligations remain open. | OPEN |
| 9 | Human intervention experiment. | No completed approved human intervention study established. | OPEN |
| 10 | Full experimental comparisons. | Predictive evaluation and synthetic fault testing exist; recovery effectiveness and complete policy comparisons remain open. | PARTIAL |
| 11 | Reproducibility package. | Frozen artifacts, source checksums, environment pinning and evidence manifest exist; full paper-to-code reproducibility audit remains open. | PARTIAL |
| 12 | Manuscript and submission. | Rejected manuscript available as a historical baseline; revised claims and complete evidence audit remain open. | OPEN |

## Pedagogical intervention distinction

The fixed four-action instructional sequence is a
baseline, not evidence of adaptive intervention selection.

A recovery controller that offers available options
is not an action-effect model.

A simulated acknowledgement is not verified delivery.

A later correct answer in observational data is not
proof that a particular intervention caused learning.

Independent recovery probes are required for a
separately measured recovery outcome.

## Additional theoretical cautions

T01: Switching away from recovery may precede arrival
at a smaller recovery target.

T02: The displayed drift constant requires additional
assumptions or a corrected transition calculation.

T03: Existence of a recovery policy does not establish
that Algorithm 1 selects that policy.

T05: The proposed hitting-time bound requires attention
to stopping times, overshoot and window length.

Model-error robustness requires an explicit error bound
for the relevant action-dependent expected drift.
Predictive entropy alone does not provide that bound.

A cost comparison requires clearly defined and
comparable objectives, trajectories and cost accounting.

No mathematical repair is adopted by this document.

## Supervisor decisions still to establish

- Approval of the proposed Phases 6–12 research scope.
- The central contribution of the revised paper.
- Which state-estimator comparisons are mandatory.
- The feasible source of intervention-effect evidence.
- The scope of any human study and ethics requirements.
- Which theorem statements will be retained or revised.

Do not treat these decisions as already made.

## Next task

Audit T03 by comparing the quantified policy-existence
assumption with the actual policy selected by Algorithm 1.

No frozen experimental artifact is modified.

The held-out test gate remains closed.
