#!/usr/bin/env python3
"""
src.train_attn_state_neuralcdm

Train AttnStateNeuralCDM on sequential logs, with explicit self-attention retrieval.

- concept space: uses data/synth/Q.npy and logs_seq.csv
- bloom space:   uses data/synth/Q_CB.npy and logs_seq_bloom.csv if --use_bloom

Splits by students: 80% train students, 20% val students.
Saves checkpoint + metrics like other trainers.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from src.attn_state_neuralcdm import AttnStateNeuralCDM
from src.config import Config
from src.eval import evaluate_predictions


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
    model: AttnStateNeuralCDM,
    df: pd.DataFrame,
    students: List[int],
    Q: np.ndarray,
    device: torch.device,
    optim: torch.optim.Optimizer | None,
) -> Tuple[float, np.ndarray, np.ndarray]:
    """
    If optim is None => eval mode (no grad).
    Processes one student at a time to maintain sequence + memory.
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

        u = torch.zeros((1, model.skill_dim), dtype=torch.float32, device=device)

        # memory of past interactions (sliding window handled inside model._attend)
        mem_q = torch.zeros((0, model.skill_dim), dtype=torch.float32, device=device)
        mem_r = torch.zeros((0,), dtype=torch.float32, device=device)
        mem_time = torch.zeros((0,), dtype=torch.float32, device=device)

        time_now = torch.zeros((1,), dtype=torch.float32, device=device)

        step_losses = []

        for e, r, dt in zip(e_seq, r_seq, dt_seq):
            # advance time (timestamp)
            dt_t = torch.tensor([float(dt)], dtype=torch.float32, device=device)
            time_now = time_now + dt_t  # current time

            e_t = torch.tensor([int(e)], dtype=torch.long, device=device)
            r_t = torch.tensor([float(r)], dtype=torch.float32, device=device)
            q_t = torch.tensor(Q[int(e)], dtype=torch.float32, device=device).unsqueeze(0)

            if optim is None:
                with torch.no_grad():
                    p, u, _, _, _ = model.step(
                        u_prev=u,
                        e_idx=e_t,
                        r=r_t,
                        q_mask=q_t,
                        delta_t=dt_t,
                        mem_q=mem_q,
                        mem_r=mem_r,
                        mem_time=mem_time,
                        time_now=time_now,
                        return_attn=False,
                    )
            else:
                p, u, _, _, _ = model.step(
                    u_prev=u,
                    e_idx=e_t,
                    r=r_t,
                    q_mask=q_t,
                    delta_t=dt_t,
                    mem_q=mem_q,
                    mem_r=mem_r,
                    mem_time=mem_time,
                    time_now=time_now,
                    return_attn=False,
                )

            loss = bce(p, r_t)
            step_losses.append(loss)

            y_true_all.append(float(r))
            y_prob_all.append(float(p.detach().cpu().item()))

            # append current interaction to memory (past for next step)
            mem_q = torch.cat([mem_q, q_t.detach()], dim=0)                 # (L+1, skill_dim)
            mem_r = torch.cat([mem_r, r_t.detach()], dim=0)                 # (L+1,)
            mem_time = torch.cat([mem_time, time_now.detach()], dim=0)  # (L+1,)

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
    parser.add_argument("--use_bloom", action="store_true")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--attn_window", type=int, default=50)
    parser.add_argument("--attn_dim", type=int, default=0, help="0 => auto")
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

    attn_dim = None if args.attn_dim == 0 else int(args.attn_dim)

    model = AttnStateNeuralCDM(
        num_items=M,
        skill_dim=skill_dim,
        lambda_decay=0.03,
        attn_dim=attn_dim,
        attn_window=int(args.attn_window),
    ).to(device)

    optim = torch.optim.Adam(model.parameters(), lr=cfg.lr)

    run_id = time.strftime("%Y%m%d_%H%M%S")
    run_dir = Path("results/runs") / f"run_{run_id}" / "state_attn" / mode
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
        "attn_dim": model.attn_dim,
        "attn_window": model.attn_window,
        "model_state": model.state_dict(),
    }
    torch.save(ckpt, run_dir / "checkpoint.pt")

    (run_dir / "loss_curve.csv").write_text(
        "epoch,train_loss,val_loss,val_auc,val_acc,val_n\n"
        + "\n".join(
            [
                f'{r["epoch"]},{r["train_loss"]},{r["val_loss"]},{r["val_auc"]},{r["val_acc"]},{r["val_n"]}'
                for r in curve
            ]
        ),
        encoding="utf-8",
    )
    metrics = {"final": curve[-1], "run_dir": str(run_dir)}
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("\nSaved:", run_dir)


if __name__ == "__main__":
    main()
