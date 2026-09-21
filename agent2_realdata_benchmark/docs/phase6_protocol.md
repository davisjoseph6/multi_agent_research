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
