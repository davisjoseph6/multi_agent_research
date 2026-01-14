#!/usr/bin/env python3
"""
src.train_state_neuralcdm

Train StateNeuralCDM on sequential logs:
- concept space: uses data/synth/Q.npy and logs_seq.csv
- bloom space:   uses data/synth/Q_CB.npy and logs_seq_bloom.csv if --use_bloom

Splits by students: 80% train students, 20% val students.
Saves checkpoint + metrics like the baseline trainer.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from src.config import Config
from src.eval import evaluate_predictions
from src.state_neuralcdm import StateNeuralCDM


def set_seeds(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def split_students(df: pd.DataFrame, seed: int, train_ratio: float = 0.8) -> Tuple[List[int], List[int]]:
    rng = np.random.default_rng(seed)
    students = np.array(sorted(df["student_idx"].unique().tolist()), dtype=np.int64)
    rng.shuffle(students)
    cut = int(train_ratio * len(students))
    return students[:cut].tolist(), students[cut:].tolist()


def run_epoch(
    model: StateNeuralCDM,
    df: pd.DataFrame,
    students: List[int],
    Q: np.ndarray,
    device: torch.device,
    optim: torch.optim.Optimizer | None,
) -> Tuple[float, np.ndarray, np.ndarray]:
    """
    If optim is None => eval mode (no grad).
    Returns: mean_loss, y_true, y_prob
    """
    bce = nn.BCELoss()
    losses = []
    y_true_all = []
    y_prob_all = []

    model.train() if optim is not None else model.eval()

    for s in students:
        sdf = df[df["student_idx"] == s].sort_values("t")
        e_seq = sdf["item_idx"].to_numpy(dtype=np.int64)
        r_seq = sdf["correct"].to_numpy(dtype=np.float32)
        dt_seq = sdf["delta_t"].to_numpy(dtype=np.float32)

        # batch = 1 student sequence
        u = torch.zeros((1, model.skill_dim), dtype=torch.float32, device=device)

        step_losses = []

        for e, r, dt in zip(e_seq, r_seq, dt_seq):
            e_t = torch.tensor([int(e)], dtype=torch.long, device=device)
            r_t = torch.tensor([float(r)], dtype=torch.float32, device=device)
            dt_t = torch.tensor([float(dt)], dtype=torch.float32, device=device)

            q_t = torch.tensor(Q[int(e)], dtype=torch.float32, device=device).unsqueeze(0)

            if optim is None:
                with torch.no_grad():
                    p, u, _ = model.step(u, e_t, r_t, q_t, dt_t)
            else:
                p, u, _ = model.step(u, e_t, r_t, q_t, dt_t)

            loss = bce(p, r_t)
            step_losses.append(loss)

            y_true_all.append(float(r))
            y_prob_all.append(float(p.detach().cpu().item()))

        seq_loss = torch.stack(step_losses).mean()

        if optim is not None:
            optim.zero_grad()
            seq_loss.backward()
            optim.step()

        losses.append(float(seq_loss.detach().cpu().item()))

    mean_loss = float(np.mean(losses)) if losses else float("nan")
    return mean_loss, np.array(y_true_all), np.array(y_prob_all)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use_bloom", action="store_true", help="Use Bloom-space Q_CB and logs_seq_bloom.csv")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    args = parser.parse_args()

    cfg = Config()
    set_seeds(cfg.seed)

    if args.use_bloom:
        q_path = "data/synth/Q_CB.npy"
        logs_path = "data/synth/logs_seq_bloom.csv"
        mode = "bloom"
    else:
        q_path = "data/synth/Q.npy"
        logs_path = "data/synth/logs_seq.csv"
        mode = "concept"

    if not Path(logs_path).exists():
        raise FileNotFoundError(
            f"Missing {logs_path}. Generate it first:\n"
            f"  python3 -m src.synth_seq_data {'--use_bloom' if args.use_bloom else ''}"
        )

    Q = np.load(q_path)
    M, skill_dim = Q.shape

    df = pd.read_csv(logs_path)

    train_students, val_students = split_students(df, seed=cfg.seed, train_ratio=0.8)

    device = torch.device(args.device if (args.device == "cpu" or torch.cuda.is_available()) else "cpu")

    model = StateNeuralCDM(num_items=M, skill_dim=skill_dim, lambda_decay=0.03).to(device)
    optim = torch.optim.Adam(model.parameters(), lr=cfg.lr)

    run_id = time.strftime("%Y%m%d_%H%M%S")
    run_dir = Path("results/runs") / f"run_{run_id}" / "state_gru" / mode
    run_dir.mkdir(parents=True, exist_ok=True)

    curve = []

    for epoch in range(1, cfg.epochs + 1):
        train_loss, _, _ = run_epoch(model, df, train_students, Q, device, optim)
        val_loss, y_true, y_prob = run_epoch(model, df, val_students, Q, device, optim=None)

        er = evaluate_predictions(y_true, y_prob)

        row = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "val_auc": er.auc,
            "val_acc": er.acc,
            "val_n": er.n,
        }
        curve.append(row)
        print(json.dumps(row, indent=2))

    ckpt = {
        "config": cfg.__dict__,
        "use_bloom": bool(args.use_bloom),
        "q_path": q_path,
        "logs_path": logs_path,
        "num_items": M,
        "skill_dim": skill_dim,
        "model_state": model.state_dict(),
    }
    torch.save(ckpt, run_dir / "checkpoint.pt")

    (run_dir / "loss_curve.csv").write_text(
        "epoch,train_loss,val_loss,val_auc,val_acc,val_n\n" +
        "\n".join([f'{r["epoch"]},{r["train_loss"]},{r["val_loss"]},{r["val_auc"]},{r["val_acc"]},{r["val_n"]}' for r in curve]),
        encoding="utf-8"
    )
    metrics = {"final": curve[-1], "run_dir": str(run_dir)}
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("\nSaved:", run_dir)


if __name__ == "__main__":
    main()

