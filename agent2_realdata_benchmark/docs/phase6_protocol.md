| Item | Protocol |
|---|---|
| Research task | Predict correctness of the next learner response |
| Datasets | Corrected ASSISTments 2009–2010; EdNet KT1 |
| Primary split | 70/15/15 by student |
| Secondary split | Chronological within-student evaluation |
| Baselines | BKT, NeuralCD, DKT, AKT |
| Additional baseline | UKT or another relevant uncertainty-aware model |
| Primary predictive metric | Held-out negative log-likelihood |
| Other metrics | AUC, accuracy, Brier score, calibration |
| Model selection | Validation performance only |
| Test evaluation | Once after model selection |
| Reproducibility | Fixed dataset version, split seed, model seeds |
| Inference restriction | No current-response information before prediction |

Canonical interaction record

Illustrative schema, not a row from either dataset.
```json
{
  "dataset": "assist2009",
  "student_id": "S001",
  "item_id": "Q103",
  "concept_ids": ["C04", "C07"],
  "event_order": 18,
  "timestamp": null,
  "correct": 1,
  "response_time_ms": null,
  "attempt_number": 1
}
```


## Frozen ASSISTments primary split

The primary experiment uses a student-disjoint split.

- Random seed: 7
- Training: 2951 students
- Validation: 633 students
- Test: 633 students

The exact student memberships and interaction assignments are saved in
data/splits/assist2009/ and excluded from Git.

The non-identifying split manifest is versioned under docs/data/.

All interactions belonging to a student remain in one partition.

Global model parameters may be fitted using training students only.
Validation students may be used for model selection and calibration,
but their outcomes must not be used for final test evaluation.
Test students must not influence fitting, model selection or calibration.

During sequential evaluation, earlier observed responses from a test
student may be used as that student's history. The current target response
must remain hidden until its prediction has been generated.

The primary prediction population consists of skill-annotated main
problems. Earlier scaffolding and unannotated interactions remain
preserved in the canonical data.

This split evaluates generalization to unseen students from a known
question bank. It does not establish unseen-item generalization.

## BKT baseline specification

The first BKT benchmark uses one shared set of parameters:
initial mastery L0, learning T, slip S and guess G.

Multi-concept questions use a factorized conjunctive approximation.
This extension is reported separately from ordinary single-skill BKT.

Parameters are fitted using the training students only, by minimizing
mean sequential negative log-likelihood on eligible primary targets.

Each student's mastery is initialized independently. For every tagged
interaction, the model predicts before seeing the outcome, then updates
its mastery using the observed outcome.

Tagged scaffolding interactions update learner history but are not
scored as primary targets. Untagged interactions produce no BKT concept
update.

Validation students are processed sequentially with globally frozen
parameters. No test-student predictions are generated during fitting
or validation model selection.

The predicted target is the dataset's recorded binary outcome, which
can include help requests among zero-valued labels. This is not a
direct measurement of true knowledge.

## NeuralCD benchmark design

The student-disjoint primary split remains unchanged.

The first NeuralCD experiment uses the original NeuralCDM-style
architecture, reproduced against the authors' reference implementation.

All global model parameters, including training-student embeddings and
training-item parameters, are fitted using training students only.

The initial baseline may train on skill-tagged training interactions,
including scaffolding, but scores only the frozen primary target
population. Training data selection must be fixed before fitting.

For validation students, global parameters are frozen. A new student
representation must be initialized from a training-derived prior.

Cold-start adaptation may use earlier observed responses from that
validation student, but it must not use the current or future response.

Only the new student's local representation may be updated during
validation inference. Any adaptation learning rate, regularization
and initialization strategy must be selected using validation data
and frozen before final test evaluation.

The first item-embedding comparison covers only validation targets
whose items occur in the annotated training interactions.

BKT must be evaluated on exactly the same target identifiers.
Uncovered items and excluded target counts must be reported.

The original NeuralCD preprocessing must not overwrite the frozen
ASSISTments source, student memberships or target definition.

A separate known-student chronological experiment requires its own
training-prefix split and model refitting. No student representation
may be trained on future responses relative to its evaluation target.

Unseen-item generalization requires a separately documented inductive
item model or fallback. Randomly initialized item embeddings do not
constitute a validated unseen-item solution.

This NeuralCD experiment evaluates prediction of recorded responses,
not recovery effectiveness or independently verified mastery.

### NeuralCD initial training-population decision

The initial NeuralCDM baseline trains on all skill-annotated
interactions belonging to training students, including scaffolding.

Only the frozen eligible primary targets contribute to the principal
validation metrics.

This differs from the original shared-parameter BKT fitting objective,
which scores primary targets but incorporates tagged scaffolding
responses through sequential belief updates.

A primary-target-only NeuralCD training ablation will assess sensitivity
to this difference.

Training-student IDs must use a compact training-only index.
Validation-student IDs are not allocated learned training embeddings.

An item may be used for validation personalization only when its
parameters were fitted using training interactions. Unknown items must
not contribute gradients through random, untrained item embeddings.

Validation personalization is strictly chronological:
predict current target, reveal response, then update local student state.

The network's nonnegative prediction-layer constraint is enforced
after every optimizer update.

### NeuralCD training smoke test

Before full training, a three-batch training-only smoke test verifies:

- Compact training-student indexing.
- Frozen data and split identities.
- Skill-annotated training-row eligibility.
- Q-matrix and item-index alignment.
- Valid binary training labels.
- Forward and backward passes.
- Adam optimization.
- Post-update nonnegative prediction-layer weights.
- Checkpoint serialization and reconstruction.

The smoke-test checkpoint is incomplete and must not be reported
as a trained benchmark model.

No validation or test predictions are generated during this test.

### NeuralCD cold-start adaptation contract

The adapted NeuralCD baseline is distinct from the original
transductive NeuralCD architecture.

For each unseen learner:

1. Initialize local student logits from the mean training-student
   embedding logits.
2. Freeze all globally fitted model parameters.
3. Disable dropout during adaptation and prediction.
4. Predict each eligible current response before observing its label.
5. After observing the response, update only local student logits.
6. Use earlier tagged scaffolding interactions when their item
   parameters were trained.
7. Skip adaptation for untrained items and unknown concept tags.
8. Reset the local state independently for every new learner.

Initial adaptation hyperparameters:
- SGD learning rate: 0.1
- Prior penalty: 0.01
- One update after each eligible observed interaction.

These values are provisional and must be selected using validation
data only. They are not final benchmark hyperparameters.

The adaptation algorithm must never be run on the incomplete
three-batch smoke-test checkpoint to report benchmark metrics.

Original NeuralCD, adapted NeuralCD and any future inductive
student model must be identified as distinct methods.

Latent proficiency outputs are not independently verified measures
of actual student mastery.

### NeuralCD chronological evaluator

The primary adapted-NeuralCD evaluator uses a newly initialized
student adapter for every learner.

Within each learner, interactions must have strictly increasing
event_order values and unique source_row identifiers.

For every supported interaction:
1. Predict using the state before the current observation.
2. Record the prediction only for an eligible primary target.
3. Reveal the current binary outcome.
4. Perform exactly one local student update.

Supported scaffolding interactions contribute to adaptation history,
but not to primary evaluation metrics.

Unsupported questions contribute neither predictions nor updates.
Unsupported primary targets must be counted and reported.

Every recorded prediction includes the source row, student ID,
event order, item index, observed outcome, predicted probability,
and number of preceding supported observations.

The evaluator must verify:
- Independent initialization for each learner.
- No duplicate source rows across learner histories.
- Exact primary-target accounting.
- No state changes during prediction.
- Exactly one update after a supported observation.

Model checkpoints produced by incomplete smoke tests are forbidden
for reported validation or test results.

Checkpoint selection, adaptation hyperparameters and matched target
coverage must be fixed before final test evaluation.

### NeuralCD full training experiment v1

NeuralCD full training uses 188223 skill-annotated interactions
from 2951 training students.

Training configuration:
- Random seed: 7
- Optimizer: Adam
- Learning rate: 0.002
- Batch size: 256
- Epochs: 5
- Candidate checkpoints: every epoch, 1 through 5.

Every epoch checkpoint is preserved with a SHA-256 checksum.

A fixed training sample of 2048 interactions is evaluated without
dropout before training and after every epoch. Its NLL and
probability-saturation diagnostics are training diagnostics only.

The full training script does not read validation or test outcomes.

A separate chronological validation procedure will select among
the prespecified epoch checkpoints using matched-population
validation NLL.

Validation personalization may optimize only each unseen
student's local representation.

No final test evaluation is permitted before checkpoint selection
and adaptation hyperparameter selection are complete.

### NeuralCD initialization and first validation

The initial untrained model produced probabilities above 0.99
for all 2048 monitored training-sample interactions.

After each of five training epochs, the monitored fractions
below 0.01 and above 0.99 were both zero.

This is a training diagnostic, not proof of validation calibration.

The initial chronological validation configuration uses:
- Training checkpoint candidate: epoch 5.
- Student initialization: mean training-student embedding logits.
- Local optimizer: SGD.
- Local learning rate: 0.1.
- Prior penalty: 0.01.
- One local update per supported observed interaction.

These settings are provisional and must not be described as
the finally selected NeuralCD configuration.

The first matched comparison requires 42437 validation targets.
The remaining 311 primary targets involve items with no trained
item embeddings and must be reported as unsupported.

Model selection will use validation NLL on the identical
known-item population for NeuralCD and frozen BKT.

No validation outcomes are used to update global model weights.
The test partition remains locked.

### Initial NeuralCD checkpoint selection

Five training checkpoints, epochs 1 through 5, were evaluated
on the same 42437 known-item validation targets.

Adaptation settings were held fixed:
- SGD learning rate: 0.1
- Prior penalty: 0.01
- One local update after each supported observation.

The prespecified minimum-validation-NLL rule selected epoch 2.

This checkpoint selection is conditional on the provisional
adaptation configuration. Any subsequent adaptation-hyperparameter
search must reconsider checkpoint selection jointly.

Paired student-cluster bootstrap comparisons with frozen BKT
are development analyses conditional on the selected models.
They do not correct for checkpoint-selection bias.

No test outcomes have been evaluated.

### NeuralCD online-adaptation ablation

The initial adaptation ablation compares the selected epoch-2
checkpoint under two conditions:

1. Online SGD adaptation with learning rate 0.1 and prior penalty 0.01.
2. A frozen-prior control that never updates the local student logits.

Both conditions use identical globally trained weights, training-
derived initial representations, Q-matrix, student histories and
matched target identifiers.

The frozen-prior control counts supported observations but ignores
their labels for representation updates.

Predictions with zero preceding supported observations must agree
between conditions.

The ablation is evaluated on the validation partition only.
Its findings are development results, not independent test evidence.

### NeuralCD adaptation-effect analysis

Online adaptation and frozen-prior predictions are compared
on identical source rows using the selected epoch-2 checkpoint.

Paired student-cluster bootstrap intervals quantify the
conditional validation differences in NLL, Brier, accuracy
and ROC-AUC.

Prespecified history groups are:
- Zero preceding supported observations.
- 1 through 4.
- 5 through 19.
- 20 or more.

History-group analyses are exploratory.

Epoch 2 was selected using online-adaptation validation NLL.
Therefore, these bootstrap intervals do not correct for
checkpoint-selection bias and are not confirmatory evidence.

The test partition remains locked.

### Prespecified NeuralCD joint validation grid v1

The joint model-selection search is registered before any new
grid evaluations.

Candidates:
- Epochs: 1, 2, 3, 4, 5.
- Online SGD learning rates: 0.01, 0.1, 0.3.
- Prior penalties: 0, 0.01, 0.1.

There are 45 combinations. The five previously evaluated
learning-rate-0.1, penalty-0.01 combinations are reused without
recalculation. Forty additional combinations remain.

Every configuration uses the identical 42437 known-item
validation target population.

Selection minimizes matched validation NLL, breaking exact ties
by earlier epoch, lower learning rate and lower prior penalty.

The validator and wrapper source hashes are recorded in
docs/data/neuralcd_grid_spec_v1.json.

Existing training weights and historical validation reports
must not be modified.

Grid results are development estimates. The test partition
remains locked until configuration selection and all planned
sensitivity analyses are finalized.

### Joint NeuralCD grid selection v1

The preregistered grid consists of 45 combinations of five
training checkpoints, three learning rates and three prior penalties.

The selection procedure independently verifies all 45 prediction
files, target identities, checkpoint identities and BKT comparisons.

Selection minimizes matched validation NLL. Exact ties are
resolved by earlier epoch, lower learning rate and lower penalty.

The selected configuration and runner-up are recorded in
docs/data/neuralcd_grid_selection_v1.json.

This selection is conditional on the successful annotation-history
audit and remains a development-set selection.

The test partition has not been evaluated.

The small NLL difference between the selected configuration and
runner-up must not be interpreted as established evidence that
their generalization performance differs.

### NeuralCD–BKT matched-history sensitivity v1

The selected NeuralCD configuration is epoch 2, online SGD
learning rate 0.1 and prior penalty 0.1.

For each validation interaction, a BKT-only history event is
defined as a preceding skill-annotated interaction whose
item embedding was not fitted on NeuralCD training data.

The analysis divides the identical scored target population into:

1. Clean-prefix targets with zero prior BKT-only history events.
2. Exposed targets with one or more prior BKT-only history events.

Both models' existing predictions are compared on each subset.
The current event is excluded from its own history count.

The clean-prefix analysis is a restricted-population
sensitivity analysis. It is not a counterfactual evaluation
of BKT after removing unavailable history from every student.

The groups can differ in their populations and outcomes.
Comparisons across groups are descriptive, not causal.

The selected NeuralCD configuration and its grid results
are not changed by this analysis.

The test partition remains locked.

### Selected NeuralCD calibration diagnostics v1

The selected configuration is:
- Epoch 2.
- Online SGD learning rate 0.1.
- Prior penalty 0.1.

Calibration is assessed descriptively on the same 42437 matched
validation targets used for the NeuralCD-BKT comparison.

Both models are evaluated using ten equal-width probability bins.

Reported diagnostics include:
- Expected calibration error.
- Bin-wise mean probability and observed positive fraction.
- Mean prediction bias.
- NLL, Brier score and ROC-AUC.
- Near-zero and near-one prediction fractions.
- Calibration by preceding supported NeuralCD history length.

The history groups are 0, 1-4, 5-19 and 20+.

No calibrator is fitted and no model predictions are modified.

ECE is bin-dependent, and small calibration subgroups may produce
unstable estimates. The selected configuration was chosen using
validation outcomes, so these remain development diagnostics.

Observed binary responses, including help-request outcomes, are
not independent ground-truth measurements of student mastery.

The test partition remains locked.

### Frozen NeuralCD baseline v1

The selected uncalibrated NeuralCD configuration is frozen as
neuralcd_v1.

Configuration:
- Training checkpoint: epoch 2 of full_train_v1.
- Student initialization: mean training embedding logits.
- Local optimizer: SGD.
- Adaptation learning rate: 0.1.
- Prior penalty: 0.1.
- Exactly one update after each supported observed interaction.
- Globally trained parameters remain frozen.

The selection used the preregistered 45-configuration grid and
minimum matched-validation NLL.

The model is intentionally frozen without a probability
calibration transformation.

Descriptive calibration diagnostics showed lower overall NLL
and Brier score than BKT but higher ten-bin ECE. Zero-history
and long-history calibration discrepancies remain limitations.

A future calibrated variant must have a separate identifier,
fitting protocol and evaluation record. It must not silently
replace neuralcd_v1.

Validation performance is not independent test performance.

The model predicts observed binary responses rather than
independently verified true student mastery.

The final test protocol must be frozen separately before test
records are accessed.

### Model-independent predictive uncertainty interface v1

Frozen BKT and NeuralCD predictions are converted into a common
signal representation without changing either baseline.

For pre-response predicted correctness probability p:

- Predicted failure risk is 1-p.
- Predictive entropy is -p ln(p) - (1-p) ln(1-p).
- Normalized predictive entropy divides entropy by ln(2).

Boundary entropy is defined as zero at p=0 and p=1.

The conversion function receives only the predicted probability.
It receives neither current-response labels nor future outcomes.

Failure risk and predictive entropy have different meanings.
A high predicted failure risk does not imply high entropy.

Predictive entropy describes uncertainty in the model's binary
outcome distribution. It is not a separately identified measure
of epistemic uncertainty, estimator uncertainty, out-of-
distribution uncertainty, or independently verified mastery.

Calibration diagnostics must accompany any claim that these
probabilities reliably quantify response uncertainty.

Unsupported items require an explicit unsupported status.
They must not receive artificial certainty or a prediction
from an untrained item embedding.

No intervention threshold, recovery action or recovery policy
is selected by this interface.

All threshold selection and policy development must occur
without accessing held-out test outcomes.

The held-out test gate remains closed.

### Frozen-model uncertainty bridge v1

The uncertainty bridge uses frozen BKT v1 and uncalibrated
NeuralCD v1 validation prediction files.

It reads only:
- source_row
- student_id
- predicted_probability

It does not read response labels.

There are two signal records for every eligible primary target:
one for BKT and one for NeuralCD.

BKT must have a supported prediction for every eligible target.

NeuralCD targets without a trained item embedding receive
status unsupported_training_item. Their probability, risk and
entropy fields are null, not zero, one or one-half.

For supported predictions, the bridge records predicted
correctness, failure risk and predictive entropy using the
model-independent mathematical interface.

No event trigger, intervention threshold or recovery policy
is applied during signal generation.

The signal dataset is a development artifact and contains
no independent test results.

The held-out test gate remains closed.

### Deterministic event detector v1

The event detector accepts only a validated, label-free
predictive-signal record and a separately specified configuration.

The implemented control and candidate policies are:
- no_trigger
- risk_only
- entropy_only
- risk_or_entropy
- risk_and_entropy

Risk and entropy thresholds must be finite values in [0, 1].

A supported prediction may produce flag or no_flag.
An unsupported prediction always produces abstain.
Abstention must not be counted as an ordinary no-flag decision.

The detector checks that risk and entropy are consistent with
the supplied probability. Unexpected input fields, including
response labels, are rejected.

Risk and entropy are deterministic transformations of the same
forecast. Combining them does not introduce an independent
uncertainty estimate.

The numerical thresholds used in unit tests are illustrative.
No operational thresholds have been selected.

A flag indicates that an event-detection rule was satisfied.
It is not an intervention, a verified learning difficulty,
an improvement in learning, or a claim of causal recovery.

Candidate thresholds, policy-selection rules and offline
evaluation measures must be registered before examining
validation outcomes for this detector.

The held-out test gate remains closed.

### Offline event-detection experiment v1

The experiment specification is registered in
docs/data/event_detection_experiment_v1.json before examining
validation response labels for event-detector policy selection.

Detection target: observed negative response (correct = 0).

This target is not a validated measure of intervention need.

Both frozen models are evaluated on the same 42437 supported
validation targets for policy selection.

The candidate search contains 25 policies per model:
- One no-trigger control.
- Three risk-only configurations.
- Three entropy-only configurations.
- Nine risk-or-entropy configurations.
- Nine risk-and-entropy configurations.

The candidate risk thresholds are 0.5, 0.7 and 0.9.
The candidate entropy thresholds are 0.5, 0.8 and 0.95.

A candidate is eligible for selection only if its alert rate
is at most 30 percent of matched supported targets.

Selection maximizes detected negative responses within this
budget. Ties are broken by fewer false-positive alerts,
fewer total alerts, registered policy order and ascending
threshold values.

The 30-percent budget is a research design assumption and
does not represent an empirically established classroom
intervention capacity.

Unsupported NeuralCD predictions are abstentions and are
reported separately.

Policies selected using validation outcomes are development
results. Student-cluster confidence intervals on those same
data do not correct for policy-selection bias.

No alert is interpreted as evidence that a pedagogical
intervention would improve learning.

No test outcomes may be used for policy selection.

The held-out test gate remains closed.

### Event-detection validation evaluation v1

The event-detection evaluation implementation was committed
before validation labels were loaded for policy scoring.

All 50 registered model-policy configurations were evaluated.

Every candidate generated its decisions from the frozen,
label-free uncertainty signals before response labels were read.

The two models were selected independently using the registered
rule on the same 42437 matched validation targets.

Selected decisions are preserved without response labels.

The frozen BKT model is additionally evaluated on all 42748
eligible validation targets under its selected policy.

The 311 unsupported NeuralCD targets remain abstentions.

The alert budget applies to the pooled response population,
not separately to every student or classroom.

Policy selection and reported detection performance use the
same validation outcomes. These are development results and
cannot be treated as independent test estimates.

The target is observed negative response, including the
dataset's help-request outcome coding. It is not a
counterfactual measure of intervention need.

No pedagogical intervention was administered or evaluated.

The held-out test gate remains closed.

### Selected event-policy structure audit v1

A post-selection, label-free audit verifies the exact decisions
produced by the two selected event-detection policies.

For the selected BKT rule, risk >= 0.5 OR normalized binary
entropy >= 0.95 is mathematically equivalent to one threshold
on predicted correctness.

The equivalent threshold is derived analytically and verified
against every saved BKT decision.

This derived threshold is not a newly selected policy and does
not modify the preregistered experiment.

Binary predictive entropy is a deterministic function of
predicted correctness. The selected BKT combination therefore
does not demonstrate an independent information contribution
from entropy.

The audit also measures overlap between BKT and NeuralCD
alerts on identical matched validation targets.

Alert overlap is descriptive and does not measure intervention
effectiveness.

The original selected policies and validation reports remain
unchanged.

The held-out test gate remains closed.

### Frozen event-detection policies v1

The registered negative-response detection experiment is
frozen in docs/data/event_detection_v1_frozen.json.

BKT v1:
- Selected policy: risk_or_entropy.
- Risk threshold: 0.5.
- Entropy threshold: 0.95.

NeuralCD v1:
- Selected policy: risk_only.
- Risk threshold: 0.5.

Selection used the same 42437 matched validation targets
and the registered 30-percent pooled alert budget.

The selected BKT OR policy is mathematically equivalent
to a single probability cutoff. It does not demonstrate
an independent information contribution from entropy.

Selected policy metrics are development results because
the policies were selected using validation outcomes.

The frozen event policies do not administer interventions
or establish intervention benefit.

Future disagreement-based or uncertainty-aware policies
must have separate version identifiers and evaluation
protocols. They must not silently replace these policies.

The held-out test gate remains closed.

### Cross-model disagreement experiment v1

A separate development experiment is registered in
docs/data/disagreement_experiment_v1.json.

For matched supported targets, disagreement is defined as
the absolute difference between BKT and NeuralCD predicted
positive-response probabilities.

The primary comparison tests whether adding disagreement
to NeuralCD failure risk changes negative-response detection
at an identical alert budget.

The controls include continuous NeuralCD risk, continuous
BKT risk, mean risk and maximum risk.

Eight candidate scores are registered. Every candidate
generates exactly 12731 alerts on the same 42437 targets
for the primary comparison.

Ten-percent and twenty-percent alert budgets are additional
descriptive sensitivity analyses.

Scores are ranked without response labels. Equal scores
receive the registered deterministic tie-break.

The primary metric is the number of observed negative
responses detected at the fixed thirty-percent budget.

The comparison reuses validation outcomes that informed earlier
model and policy selection. It therefore cannot provide
independent confirmatory evidence of incremental benefit.

Disagreement is not independently calibrated epistemic
uncertainty. A combined ranking score is not a probability.

No intervention or causal recovery outcome is evaluated.

The existing frozen models and selected event policies
remain unchanged. The held-out test gate remains closed.

### Label-free disagreement rankings v1

All eight registered candidate scores are computed using
the frozen BKT and NeuralCD validation predictions.

Each candidate ranks the same 42437 supported targets.

Scores are ordered descending, with the registered SHA256
tie-break and ascending source-row fallback.

Each ranking contains exactly:
- 4243 alerts at the ten-percent budget.
- 8487 alerts at the twenty-percent budget.
- 12731 alerts at the thirty-percent budget.

The budget sets are nested.

The ranking artifact contains model-derived scores,
identities and alert decisions, but no response outcomes.

The scores are not calibrated response probabilities.

The 311 unsupported NeuralCD targets remain excluded from
this matched-population experiment and are reported separately.

No candidate has been evaluated or selected in this stage.
The held-out test gate remains closed.

### Cross-model disagreement validation evaluation v1

The outcome evaluator was committed before validation response
labels were loaded for the registered disagreement experiment.

All eight previously constructed label-free rankings were
reconstructed and verified before outcome scoring.

All candidates use the same 42437 matched targets and exactly:
- 4243 alerts at the ten-percent budget.
- 8487 alerts at the twenty-percent budget.
- 12731 alerts at the thirty-percent budget.

The primary comparison uses observed negative-response
detections at the thirty-percent budget.

The registered selection considers NeuralCD risk and its
four positive-alpha disagreement variants only.

BKT risk, mean risk and maximum risk are reported controls,
not candidates for the registered family selection.

For each candidate, the report identifies how many alerts
were reallocated relative to NeuralCD risk and the resulting
gain or loss in detected negative responses.

Because the alert count is fixed, each additional true
positive corresponds to one fewer false-positive alert.

The same validation outcomes informed prior model development.
The reported findings are exploratory development results,
not independent confirmatory estimates.

Disagreement is not a calibrated epistemic uncertainty measure.

No intervention was performed and no causal learning benefit
was evaluated.

The frozen BKT, NeuralCD and event-detection policies remain
unchanged. The held-out test gate remains closed.
