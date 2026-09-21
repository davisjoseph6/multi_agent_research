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
