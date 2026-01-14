#!/usr/bin/env python3
"""
src.demo_attn_forward_pass

Demo self-attention context retrieval at a given (student_idx, t).

Writes a JSON showing:
- alpha_{t,i}: attention weights over past interactions
- c_t: context vector (first dims)
- bias decomposition per memory element:
    dot / time bias / concept bias / total score
- p_no_ctx vs p_with_ctx (ablation)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from src.attn_state_neuralcdm import AttnStateNeuralCDM


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--student_idx", type=int, required=True)
    parser.add_argument("--t", type=int, required=True)
    parser.add_argument("--top_k", type=int, default=10)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    ckpt = torch.load(run_dir / "checkpoint.pt", map_location="cpu")

    Q = np.load(ckpt["q_path"])
    df = pd.read_csv(ckpt["logs_path"])

    device = torch.device(args.device if (args.device == "cpu" or torch.cuda.is_available()) else "cpu")

    model = AttnStateNeuralCDM(
        num_items=int(ckpt["num_items"]),
        skill_dim=int(ckpt["skill_dim"]),
        lambda_decay=0.03,
        attn_dim=int(ckpt.get("attn_dim", 0)) or None,
        attn_window=int(ckpt.get("attn_window", 50)),
    ).to(device)
    model.load_state_dict(ckpt["model_state"], strict=True)
    model.eval()

    sdf = df[df["student_idx"] == args.student_idx].sort_values("t").reset_index(drop=True)
    if args.t < 0 or args.t >= len(sdf):
        raise ValueError(f"t out of range: t={args.t}, len={len(sdf)}")

    u = torch.zeros((1, model.skill_dim), dtype=torch.float32, device=device)

    mem_q = torch.zeros((0, model.skill_dim), dtype=torch.float32, device=device)
    mem_r = torch.zeros((0,), dtype=torch.float32, device=device)
    mem_time = torch.zeros((0,), dtype=torch.float32, device=device)

    time_now = torch.zeros((1,), dtype=torch.float32, device=device)

    for i in range(args.t + 1):
        row = sdf.iloc[i]
        e = int(row["item_idx"])
        r = float(row["correct"])
        dt = float(row["delta_t"])

        dt_t = torch.tensor([dt], dtype=torch.float32, device=device)
        time_now = time_now + dt_t

        e_t = torch.tensor([e], dtype=torch.long, device=device)
        r_t = torch.tensor([r], dtype=torch.float32, device=device)
        q_t = torch.tensor(Q[e], dtype=torch.float32, device=device).unsqueeze(0)

        if i == args.t:
            with torch.no_grad():
                # baseline: no context, only decay
                u_decayed = model.decay_u(u, dt_t)
                p_no_ctx = model.predict_from_u(u_decayed, e_t, q_t)

                # full: with attention context
                p, u_new, u_decayed2, u_eff, c_t, attn = model.step(
                    u_prev=u,
                    e_idx=e_t,
                    r=r_t,
                    q_mask=q_t,
                    delta_t=dt_t,
                    mem_q=mem_q,
                    mem_r=mem_r,
                    mem_time=mem_time,
                    time_now=time_now,
                    return_attn=True,
                )

                alpha = attn["alpha"].cpu().numpy()
                order = np.argsort(-alpha)

                top = []
                for j in order[: args.top_k]:
                    top.append(
                        {
                            "rank": int(len(top) + 1),
                            "alpha": float(attn["alpha"][j].item()),
                            "gap": float(attn["gap"][j].item()),
                            "overlap": float(attn["overlap"][j].item()),
                            "score_dot": float(attn["score_dot"][j].item()),
                            "score_time": float(attn["score_time"][j].item()),
                            "score_concept": float(attn["score_concept"][j].item()),
                            "score_total": float(attn["score_total"][j].item()),
                        }
                    )

                out = {
                    "student_idx": int(args.student_idx),
                    "t": int(row["t"]),
                    "item_idx": int(e),
                    "correct": int(row["correct"]),
                    "delta_t": float(dt),
                    "attn_window": int(model.attn_window),
                    "attn_dim": int(model.attn_dim),
                    "p_no_ctx": float(p_no_ctx.item()),
                    "p_with_ctx": float(p.item()),
                    "ctx_first10": c_t.squeeze(0).detach().cpu().tolist()[:10],
                    "top_attended": top,
                }

                out_path = run_dir / f"demo_attn_s{args.student_idx}_t{args.t}.json"
                out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

                print("Saved:", out_path)
                print(
                    "delta_t:", out["delta_t"],
                    "| observed:", out["correct"],
                    "| p_no_ctx:", out["p_no_ctx"],
                    "| p_with_ctx:", out["p_with_ctx"],
                )

        # advance + append to memory for next step
        with torch.no_grad():
            _, u, _, _, _ = model.step(
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

        mem_q = torch.cat([mem_q, q_t.detach()], dim=0)
        mem_r = torch.cat([mem_r, r_t.detach()], dim=0)
        mem_time = torch.cat([mem_time, time_now.detach().view(1)], dim=0)


if __name__ == "__main__":
    main()
