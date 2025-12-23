# Agent2 NeuralCDM Proof-of-Life (Thermo v0)

## What we proved
- End-to-end pipeline works: taxonomy+items -> Q-matrix -> synthetic logs -> NeuralCDM training -> validation metrics.
- Model learns meaningful student mastery / item requirement parameters and produces calibrated probabilities.

## Key results
- Best validation epoch: 8
- Best val AUC: 0.7176 (concept-only Q)
- Best val acc: 0.6581
- Evidence of mild overfitting after epoch 8 (train loss keeps decreasing while AUC declines), so we report best epoch / early stopping.

## Concrete forward-pass demonstrations
- Positive example (label=1): p_before≈0.50 -> p_after≈0.94
- Negative example (label=0): p_before≈0.50 -> p_after≈0.017
Each JSON includes: Q-mask, student mastery hs, item requirement he_req, discrimination he_disc, intermediate x, and final probability.

## Files
- curve.png: training loss + val AUC
- metrics.json: final + best epoch metrics
- example_forward_*_pos.json: forward pass for positive case
- example_forward_*_neg.json: forward pass for negative case
