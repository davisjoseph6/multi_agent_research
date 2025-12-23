#!/usr/bin/env python3
"""
Evaluation utilities for NeuralCD experiments.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import torch
from sklearn.metrics import roc_auc_score


@dataclass
class EvalResult:
    """Container for evaluation metrics."""
    auc: float
    acc: float
    n: int


@torch.no_grad()
def evaluate_predictions(y_true: np.ndarray, y_prob: np.ndarray, threshold: float = 0.5) -> EvalResult:
    """
    Compute AUC and accuracy from probabilities.

    Args:
        y_true: Binary labels shape (N,).
        y_prob: Predicted probabilities shape (N,).
        threshold: Decision threshold.

    Returns:
        EvalResult
    """
    y_true = y_true.astype(np.int64)
    y_prob = y_prob.astype(np.float64)

    # AUC is undefined if only one class appears; guard for tiny toy cases
    if len(np.unique(y_true)) < 2:
        auc = float("nan")
    else:
        auc = float(roc_auc_score(y_true, y_prob))

    y_pred = (y_prob >= threshold).astype(np.int64)
    acc = float((y_pred == y_true).mean())
    return EvalResult(auc=auc, acc=acc, n=int(y_true.shape[0]))

