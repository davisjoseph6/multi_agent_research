#!/usr/bin/env python3
"""
Dump a concrete forward-pass example (inputs -> internals -> output) before/after training.

Run (after training):
  python3 -m src.demo_forward_pass --run_dir results/runs/run_YYYYMMDD_HHMMSS/concept
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import torch

from src.neuralcdm import NeuralCDM


def dump_one(model: NeuralCDM, Q: np.ndarray, s_idx: int, e_idx: int, device: torch.device) -> Dict[str, Any]:
    """Compute internals for one (student,item) pair."""
    model.eval()
    with torch.no_grad():
        s = torch.tensor([s_idx], dtype=torch.long, device=device)
        e = torch.tensor([e_idx], dtype=torch.long, device=device)
        q_mask = torch.tensor(Q[e_idx], dtype=torch.float32, device=device).unsqueeze(0)

        hs = torch.sigmoid(model.A(s)).squeeze(0)          # (skill_dim,)
        he_req = torch.sigmoid(model.B(e)).squeeze(0)      # (skill_dim,)
        he_disc = torch.sigmoid(model.D(e)).squeeze(0)     # (1,)

        x = q_mask.squeeze(0) * (hs - he_req)
        x = x * he_disc

        w = torch.relu(model.head.weight).squeeze(0)       # (skill_dim,)
        logit = (x * w).sum() + model.head.bias.squeeze(0)
        p = torch.sigmoid(logit)

        out = {
            "student_idx": s_idx,
            "item_idx": e_idx,
            "q_mask": Q[e_idx].tolist(),
            "hs": hs.detach().cpu().tolist(),
            "he_req": he_req.detach().cpu().tolist(),
            "he_disc": float(he_disc.item()),
            "x": x.detach().cpu().tolist(),
            "w_pos": w.detach().cpu().tolist(),
            "logit": float(logit.item()),
            "p_correct": float(p.item()),
        }
        return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True, help="Path to run dir containing checkpoint.pt")
    parser.add_argument("--sample_idx", type=int, default=0, help="Which row from logs_synth.csv to use.")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    ckpt_path = run_dir / "checkpoint.pt"
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Missing checkpoint: {ckpt_path}")

    ckpt = torch.load(ckpt_path, map_location="cpu")
    q_path = ckpt["q_path"]
    Q = np.load(q_path)

    df = pd.read_csv("data/synth/logs_synth.csv")
    row = df.iloc[int(args.sample_idx)]
    s_idx = int(row["student_idx"])
    e_idx = int(row["item_idx"])
    correct = int(row["correct"])

    device = torch.device(args.device if (args.device == "cpu" or torch.cuda.is_available()) else "cpu")

    # Before training: fresh init model
    model_before = NeuralCDM(
        num_students=int(ckpt["num_students"]),
        num_items=int(ckpt["num_items"]),
        skill_dim=int(ckpt["skill_dim"])
    ).to(device)

    before = dump_one(model_before, Q, s_idx, e_idx, device)
    before["observed_correct"] = correct

    # After training: load checkpoint
    model_after = NeuralCDM(
        num_students=int(ckpt["num_students"]),
        num_items=int(ckpt["num_items"]),
        skill_dim=int(ckpt["skill_dim"])
    ).to(device)
    model_after.load_state_dict(ckpt["model_state"], strict=True)

    after = dump_one(model_after, Q, s_idx, e_idx, device)
    after["observed_correct"] = correct

    (run_dir / "example_forward_before.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
    (run_dir / "example_forward_after.json").write_text(json.dumps(after, indent=2), encoding="utf-8")

    print("Saved forward-pass dumps to:")
    print(" ", run_dir / "example_forward_before.json")
    print(" ", run_dir / "example_forward_after.json")
    print("\nObserved label:", correct)
    print("p_before:", before["p_correct"])
    print("p_after :", after["p_correct"])


if __name__ == "__main__":
    main()

