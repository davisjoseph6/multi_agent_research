# Phase 6 — Independent test evaluation gate v1

Status: PROTOCOL DEFINED; TEST ACCESS NOT AUTHORIZED.

## Frozen cognitive-diagnosis baselines

BKT:
- Use the parameters in docs/data/bkt_v1_frozen.json.
- Do not refit parameters or select variants using test outcomes.

NeuralCD:
- Use docs/data/neuralcd_v1_frozen.json.
- Epoch 2 of full_train_v1.
- Initialize each new student from mean training-student logits.
- Online SGD learning rate 0.1.
- Prior penalty 0.1.
- One local update after each supported observation.
- Keep all global model parameters frozen.
- No calibration transformation.

Any new calibrated model must have a separate identifier and
must be fitted and selected before test access.

## Chronological prediction

Students remain disjoint between train, validation and test.

Within each student, evaluate interactions in frozen event order.

Predict before revealing the current response.
Afterward, update permitted model state using observed history.

Never use the current or future response as a prediction feature.

Score eligible primary targets only. Earlier eligible historical
observations may be used according to each model's frozen protocol.

## Coverage

Report BKT on all eligible test primary targets.

Define NeuralCD-supported targets using the training-derived
seen-item mask and the frozen Q-matrix.

Compare BKT and NeuralCD on identical supported target source rows,
student IDs and labels.

Report NeuralCD coverage and every unsupported target separately.

Do not evaluate NeuralCD with untrained item embeddings or silently
exclude unsupported targets from coverage reporting.

## Primary prediction metrics

Primary selection-independent comparison:
- Negative log-likelihood on matched targets.

Secondary metrics:
- Brier score.
- Accuracy at a fixed threshold of 0.5.
- ROC-AUC, when both outcome classes are present.
- Ten-bin equal-width expected calibration error.
- Mean prediction minus observed positive-response rate.

Do not optimize thresholds or calibrators using test labels.

## Uncertainty analysis

Use paired student-cluster bootstrap resampling.

Prespecified replication counts:
- 1000 replicates for NLL, Brier and accuracy differences.
- 300 replicates for ROC-AUC differences.

Report point estimates and percentile 95% intervals.
Preserve paired target identities across models.

## Descriptive subgroup analyses

Use the prespecified prior-supported-observation groups:
- 0
- 1 through 4
- 5 through 19
- 20 or more

Report subgroup sample sizes and outcome prevalence.

Report clean-prefix versus BKT-only-history-exposed targets as
a sensitivity analysis. Do not describe this restriction as
a counterfactual BKT evaluation.

Subgroup findings are exploratory.

## Interpretation

The models predict observed binary response outcomes. Their latent
proficiency values are not independently verified student mastery.

Validation estimates were used for model selection and must not be
reported as independent test evidence.

The final end-to-end pedagogical recovery system requires its own
prespecified intervention and recovery metrics.

## Test access conditions

Do not access test response records until:
1. All intended baselines and system components are finalized.
2. The uncertainty and recovery policies are frozen.
3. Planned ablations and primary outcomes are specified.
4. All code and artifact identities are recorded.
5. The complete evaluation protocol is committed.

After test access, do not use test outcomes for hyperparameter
selection, calibration fitting, architecture revision or policy design.

If a technical defect invalidates evaluation, document the defect
and its consequences before deciding how results can be reported.

Current status: GATE CLOSED.
