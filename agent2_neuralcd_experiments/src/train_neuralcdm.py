#!/usr/bin/env python3
"""
Train NeuralCD-style model on synthetic logs and save metrics + checkpoint.

Run:
  python3 -m src.train_neuralcdm
  python3 -m src.train_neuralcdm --use_bloom
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from src.config import Config
from src.neuralcdm import NeuralCDM
from src.eval import evaluate_predictions


class LogDataset(Dataset):
    """Dataset of (student_idx, item_idx, correct) with preloaded Q masks."""

    def __init__(self, df: pd.DataFrame, Q: np.ndarray) -> None:
        self.s = df["student_idx"].to_numpy(dtype=np.int64)
        self.e = df["item_idx"].to_numpy(dtype=np.int64)
        self.r = df["correct"].to_numpy(dtype=np.float32)
        self.Q = Q.astype(np.float32)

    def __len__(self) -> int:
        return int(self.r.shape[0])

    def __getitem__(self, idx: int):
        s = self.s[idx]
        e = self.e[idx]
        r = self.r[idx]
        q_mask = self.Q[e]  # (skill_dim,)
        return s, e, r, q_mask


def set_seeds(seed: int) -> None:
    """Set RNG seeds for reproducibility."""
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def split_df(df: pd.DataFrame, seed: int, train_ratio: float = 0.8) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Random train/val split."""
    rng = np.random.default_rng(seed)
    idx = np.arange(len(df))
    rng.shuffle(idx)
    cut = int(train_ratio * len(df))
    train_idx = idx[:cut]
    val_idx = idx[cut:]
    return df.iloc[train_idx].reset_index(drop=True), df.iloc[val_idx].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use_bloom", action="store_true", help="Use Bloom-aware Q_CB (skill_dim=K*B).")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="Training device.")
    args = parser.parse_args()

    cfg = Config()
    set_seeds(cfg.seed)

    q_path = "data/synth/Q_CB.npy" if args.use_bloom else "data/synth/Q.npy"
    logs_path = "data/synth/logs_synth.csv"

    Q = np.load(q_path)  # (M, skill_dim)
    M, skill_dim = Q.shape

    df = pd.read_csv(logs_path)
    train_df, val_df = split_df(df, seed=cfg.seed, train_ratio=0.8)

    train_ds = LogDataset(train_df, Q)
    val_ds = LogDataset(val_df, Q)

    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_ds, batch_size=cfg.batch_size, shuffle=False, drop_last=False)

    num_students = int(df["student_idx"].max() + 1)

    device = torch.device(args.device if (args.device == "cpu" or torch.cuda.is_available()) else "cpu")
    model = NeuralCDM(num_students=num_students, num_items=M, skill_dim=skill_dim).to(device)

    optim = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    bce = nn.BCELoss()

    # results dir
    run_id = time.strftime("%Y%m%d_%H%M%S")
    run_dir = Path("results/runs") / f"run_{run_id}" / ("bloom" if args.use_bloom else "concept")
    run_dir.mkdir(parents=True, exist_ok=True)

    loss_curve = []

    for epoch in range(1, cfg.epochs + 1):
        model.train()
        train_losses = []

        for s_idx, e_idx, r, q_mask in train_loader:
            s_idx = s_idx.to(device)
            e_idx = e_idx.to(device)
            r = r.to(device)

            q_mask = torch.from_numpy(np.asarray(q_mask)).to(device)  # (B, skill_dim)

            p = model(s_idx, e_idx, q_mask)
            loss = bce(p, r)

            optim.zero_grad()
            loss.backward()
            optim.step()

            train_losses.append(float(loss.item()))

        # validation
        model.eval()
        y_true = []
        y_prob = []

        with torch.no_grad():
            for s_idx, e_idx, r, q_mask in val_loader:
                s_idx = s_idx.to(device)
                e_idx = e_idx.to(device)
                q_mask = torch.from_numpy(np.asarray(q_mask)).to(device)
                p = model(s_idx, e_idx, q_mask).detach().cpu().numpy()

                y_prob.append(p)
                y_true.append(r.numpy())

        y_true_np = np.concatenate(y_true, axis=0)
        y_prob_np = np.concatenate(y_prob, axis=0)

        er = evaluate_predictions(y_true_np, y_prob_np)

        row = {
            "epoch": epoch,
            "train_loss": float(np.mean(train_losses)),
            "val_auc": er.auc,
            "val_acc": er.acc,
            "val_n": er.n,
        }
        loss_curve.append(row)
        print(json.dumps(row, indent=2))

    # save checkpoint + metrics
    ckpt = {
        "config": cfg.__dict__,
        "use_bloom": bool(args.use_bloom),
        "q_path": q_path,
        "num_students": num_students,
        "num_items": M,
        "skill_dim": skill_dim,
        "model_state": model.state_dict(),
    }
    torch.save(ckpt, run_dir / "checkpoint.pt")

    (run_dir / "loss_curve.csv").write_text(
        "epoch,train_loss,val_auc,val_acc,val_n\n" +
        "\n".join([f'{r["epoch"]},{r["train_loss"]},{r["val_auc"]},{r["val_acc"]},{r["val_n"]}' for r in loss_curve]),
        encoding="utf-8"
    )

    metrics = {"final": loss_curve[-1], "run_dir": str(run_dir)}
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("\nSaved:", run_dir)


if __name__ == "__main__":
    main()

