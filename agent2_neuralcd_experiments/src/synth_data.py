#!/usr/bin/env python3
"""
Generate synthetic student-item response logs for NeuralCD proof-of-life experiments.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.config import Config


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def generate_synth_logs(cfg: Config, q_path: str, item_index_path: str, out_csv: str) -> None:
    Q = np.load(q_path)  # (M, K)
    M, K = Q.shape

    item_index = json.loads(Path(item_index_path).read_text(encoding="utf-8"))
    item_ids = list(item_index.keys())

    # Ground-truth student mastery and item requirements
    theta = np.random.normal(loc=0.0, scale=1.0, size=(cfg.num_students, K))  # (N,K)
    beta = np.random.normal(loc=0.0, scale=1.0, size=(M, K))  # (M,K)
    disc = sigmoid(np.random.normal(loc=0.0, scale=0.5, size=(M,)))  # (M,)

    rows = []
    for s in range(cfg.num_students):
        for _ in range(cfg.interactions_per_student):
            item_id = np.random.choice(item_ids)
            e = item_index[item_id]
            mask = Q[e]  # (K,)
            # score: only required concepts contribute
            score = np.sum(mask * (theta[s] - beta[e])) * disc[e]
            p = float(sigmoid(score))
            r = int(np.random.rand() < p)
            rows.append((s, e, r))

    df = pd.DataFrame(rows, columns=["student_idx", "item_idx", "correct"])
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)


if __name__ == "__main__":
    cfg = Config()
    np.random.seed(cfg.seed)
    generate_synth_logs(
        cfg,
        "data/synth/Q.npy",
        "data/synth/item_index.json",
        "data/synth/logs_synth.csv"
    )

