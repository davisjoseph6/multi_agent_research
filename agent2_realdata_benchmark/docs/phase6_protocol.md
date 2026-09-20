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

