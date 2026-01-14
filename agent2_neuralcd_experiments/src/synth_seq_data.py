#!/usr/bin/env python3
"""
src.synth_seq_data

Generate sequential student logs with timestamps / delta_t for context-aware KT.
Outputs:
- data/synth/logs_seq.csv        (concept space, uses Q.npy)
- data/synth/logs_seq_bloom.csv  (bloom space, uses Q_CB.npy) if --use_bloom

Each student's rows are ordered by t = 0..T-1 and include delta_t
(simulated time gaps, including occasional large gaps like 40 days).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd

from src.config import Config


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def sample_delta_t(rng: np.random.Generator) -> int:
    """Mostly small gaps, sometimes a big one to demo forgetting."""
    if rng.random() < 0.08:
        return 40
    return int(rng.integers(1, 4))  # 1..3


def generate_logs(
    cfg: Config,
    Q: np.ndarray,
    out_csv: str,
    seed: int,
    lambda_true: float = 0.03,
    practice_lr: float = 0.15,
) -> None:
    """
    Simulate sequential data with true forgetting + practice.
    True latent theta decays over time and is nudged by correctness.
    """
    rng = np.random.default_rng(seed)

    M, skill_dim = Q.shape

    # True item params in same skill space
    beta = rng.normal(0.0, 1.0, size=(M, skill_dim))
    disc = sigmoid(rng.normal(0.0, 0.5, size=(M,)))

    rows = []

    for s in range(cfg.num_students):
        theta = rng.normal(0.0, 1.0, size=(skill_dim,))  # true state for this student

        for t in range(cfg.interactions_per_student):
            e = int(rng.integers(0, M))
            q = Q[e].astype(np.float32)

            delta_t = sample_delta_t(rng)

            # True forgetting in latent state
            theta = theta * np.exp(-lambda_true * float(delta_t))

            # Score uses only required skills
            score = float(np.sum(q * (theta - beta[e])) * disc[e])
            p = float(sigmoid(score))
            r = int(rng.random() < p)

            # Practice effect: correct strengthens required skills, wrong slightly weakens
            if r == 1:
                theta = theta + practice_lr * q
            else:
                theta = theta - (0.5 * practice_lr) * q

            rows.append((s, e, r, t, delta_t))

    df = pd.DataFrame(rows, columns=["student_idx", "item_idx", "correct", "t", "delta_t"])
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    print("Saved:", out_csv, "| rows:", len(df))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use_bloom", action="store_true", help="Generate in Bloom space using Q_CB.npy.")
    args = parser.parse_args()

    cfg = Config()

    if args.use_bloom:
        Q = np.load("data/synth/Q_CB.npy")
        out_csv = "data/synth/logs_seq_bloom.csv"
    else:
        Q = np.load("data/synth/Q.npy")
        out_csv = "data/synth/logs_seq.csv"

    generate_logs(cfg, Q, out_csv=out_csv, seed=cfg.seed)


if __name__ == "__main__":
    main()

