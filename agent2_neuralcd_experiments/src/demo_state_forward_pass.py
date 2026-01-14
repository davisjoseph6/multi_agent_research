#!/usr/bin/env python3
"""
src.demo_state_forward_pass

Demo one student's state evolution at a specific time t:
- shows u before/after decay
- shows z (=sigmoid(u)) before/after decay
- shows predicted p_correct for that step
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from src.state_neuralcdm import StateNeuralCDM


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True, help="results/.../state_gru/{concept|bloom}")
    parser.add_argument("--student_idx", type=int, required=True)
    parser.add_argument("--t", type=int, required=True)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    ckpt = torch.load(run_dir / "checkpoint.pt", map_location="cpu")

    Q = np.load(ckpt["q_path"])
    logs_path = ckpt["logs_path"]
    df = pd.read_csv(logs_path)

    device = torch.device(args.device if (args.device == "cpu" or torch.cuda.is_available()) else "cpu")

    model = StateNeuralCDM(
        num_items=int(ckpt["num_items"]),
        skill_dim=int(ckpt["skill_dim"]),
        lambda_decay=0.03,
    ).to(device)
    model.load_state_dict(ckpt["model_state"], strict=True)
    model.eval()

    sdf = df[df["student_idx"] == args.student_idx].sort_values("t").reset_index(drop=True)
    if args.t < 0 or args.t >= len(sdf):
        raise ValueError(f"t out of range: t={args.t}, len={len(sdf)}")

    # replay state up to time t
    u = torch.zeros((1, model.skill_dim), dtype=torch.float32, device=device)

    for i in range(args.t + 1):
        row = sdf.iloc[i]
        e = int(row["item_idx"])
        r = float(row["correct"])
        dt = float(row["delta_t"])

        e_t = torch.tensor([e], dtype=torch.long, device=device)
        r_t = torch.tensor([r], dtype=torch.float32, device=device)
        dt_t = torch.tensor([dt], dtype=torch.float32, device=device)
        q_t = torch.tensor(Q[e], dtype=torch.float32, device=device).unsqueeze(0)

        # show details only at i == t
        if i == args.t:
            with torch.no_grad():
                u_decayed = model.decay_u(u, dt_t)
                z_before = torch.sigmoid(u)
                z_after_decay = torch.sigmoid(u_decayed)
                p = model.predict_from_u(u_decayed, e_t, q_t)

                out = {
                    "student_idx": args.student_idx,
                    "t": int(row["t"]),
                    "item_idx": e,
                    "correct": int(row["correct"]),
                    "delta_t": float(dt),
                    "z_before": z_before.squeeze(0).detach().cpu().tolist(),
                    "z_after_decay": z_after_decay.squeeze(0).detach().cpu().tolist(),
                    "p_correct": float(p.item()),
                }

                out_path = run_dir / f"demo_state_s{args.student_idx}_t{args.t}.json"
                out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

                print("Saved:", out_path)
                print("delta_t:", out["delta_t"], "| observed:", out["correct"], "| p_correct:", out["p_correct"])

        # advance state (always)
        with torch.no_grad():
            _, u, _ = model.step(u, e_t, r_t, q_t, dt_t)


if __name__ == "__main__":
    main()

