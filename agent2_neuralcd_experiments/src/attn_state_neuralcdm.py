#!/usr/bin/env python3
"""
src.attn_state_neuralcdm

Attention + state (GRU) variant of NeuralCDM.

Adds an explicit context retrieval step:
- Keep a memory of past interactions (q_i, r_i, time_i)
- Compute attention weights alpha_{t,i} using:
    score = dot(query_t, key_i)/sqrt(d)
          + concept_bias * overlap(q_t, q_i)
          - time_bias * gap(time_t - time_i)
- Context vector c_t = sum_i alpha_{t,i} * value_i

Then integrate context into:
- effective state u_eff = decay(u_prev) + ctx_to_u(c_t)
- prediction p_correct using NeuralCD-style masked interaction
- update u_new using GRUCell with input [q_t, r_t, c_t]
"""
from __future__ import annotations

import math
from typing import Dict, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class AttnStateNeuralCDM(nn.Module):
    """NeuralCD head + GRU state + explicit self-attention context retrieval."""

    def __init__(
        self,
        num_items: int,
        skill_dim: int,
        lambda_decay: float = 0.03,
        attn_dim: int | None = None,
        attn_window: int = 50,
    ) -> None:
        super().__init__()
        self.num_items = int(num_items)
        self.skill_dim = int(skill_dim)
        self.lambda_decay = float(lambda_decay)
        self.attn_dim = int(attn_dim) if attn_dim is not None else int(min(32, skill_dim))
        self.attn_window = int(attn_window)

        # Item requirement & discrimination (same idea as baseline)
        self.B = nn.Embedding(self.num_items, self.skill_dim)
        self.D = nn.Embedding(self.num_items, 1)

        nn.init.normal_(self.B.weight, mean=0.0, std=0.01)
        nn.init.normal_(self.D.weight, mean=0.0, std=0.01)

        # Attention projections: build (key,value) from past (q_i, r_i)
        self.k_proj = nn.Linear(self.skill_dim + 1, self.attn_dim, bias=True)
        self.v_proj = nn.Linear(self.skill_dim + 1, self.attn_dim, bias=True)

        # Query: from current decayed state + current q mask
        self.q_from_state = nn.Linear(self.skill_dim, self.attn_dim, bias=True)
        self.q_from_item = nn.Linear(self.skill_dim, self.attn_dim, bias=True)

        # Bias strengths (kept positive via softplus at runtime)
        self.time_w = nn.Parameter(torch.tensor(0.10))
        self.concept_w = nn.Parameter(torch.tensor(0.10))

        # Inject context into state space
        self.ctx_to_u = nn.Linear(self.attn_dim, self.skill_dim, bias=True)

        # GRU update for student latent u
        # input = [q_mask (skill_dim), r (1), context c_t (attn_dim)]
        self.gru = nn.GRUCell(input_size=self.skill_dim + 1 + self.attn_dim, hidden_size=self.skill_dim)

        # Prediction head (monotone-ish like your baseline)
        self.head = nn.Linear(self.skill_dim, 1, bias=True)
        nn.init.constant_(self.head.weight, 0.1)
        nn.init.constant_(self.head.bias, 0.0)

    def decay_u(self, u: torch.Tensor, delta_t: torch.Tensor) -> torch.Tensor:
        """
        Exponential decay on raw state:
          u <- u * exp(-lambda * delta_t)
        u: (B, skill_dim)
        delta_t: (B,) or scalar
        """
        dt = delta_t.float().unsqueeze(-1) if delta_t.ndim == 1 else delta_t.float()
        factor = torch.exp(-self.lambda_decay * dt)
        return u * factor

    def predict_from_u(self, u_eff: torch.Tensor, e_idx: torch.Tensor, q_mask: torch.Tensor) -> torch.Tensor:
        """
        Predict correctness probability using NeuralCD formula but hs := sigmoid(u_eff).

        Shapes:
          u_eff: (B, skill_dim)
          e_idx: (B,)
          q_mask: (B, skill_dim)
        """
        hs = torch.sigmoid(u_eff)
        he_req = torch.sigmoid(self.B(e_idx))
        he_disc = torch.sigmoid(self.D(e_idx))

        x = q_mask * (hs - he_req)
        x = x * he_disc  # broadcast (B,1)

        w = torch.relu(self.head.weight)  # (1, skill_dim)
        logits = (x * w).sum(dim=1) + self.head.bias
        return torch.sigmoid(logits)

    def _attend(
        self,
        u_decayed: torch.Tensor,
        q_t: torch.Tensor,
        mem_q: torch.Tensor,
        mem_r: torch.Tensor,
        mem_time: torch.Tensor,
        time_now: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Compute attention context c_t over memory.

        Inputs:
          u_decayed: (1, skill_dim)
          q_t: (1, skill_dim)
          mem_q: (L, skill_dim)
          mem_r: (L,)  (0/1 floats)
          mem_time: (L,) time stamps
          time_now: (1,) current time stamp

        Returns:
          c_t: (1, attn_dim)
          info: dict with alpha, gaps, overlap and score components
        """
        L = int(mem_q.shape[0])
        if L == 0:
            c0 = torch.zeros((1, self.attn_dim), dtype=u_decayed.dtype, device=u_decayed.device)
            info0 = {
                "alpha": torch.zeros((0,), device=u_decayed.device),
                "gap": torch.zeros((0,), device=u_decayed.device),
                "overlap": torch.zeros((0,), device=u_decayed.device),
                "score_dot": torch.zeros((0,), device=u_decayed.device),
                "score_time": torch.zeros((0,), device=u_decayed.device),
                "score_concept": torch.zeros((0,), device=u_decayed.device),
                "score_total": torch.zeros((0,), device=u_decayed.device),
            }
            return c0, info0

        # windowing (most recent interactions)
        if L > self.attn_window:
            mem_q = mem_q[-self.attn_window :]
            mem_r = mem_r[-self.attn_window :]
            mem_time = mem_time[-self.attn_window :]
            L = int(mem_q.shape[0])

        # Build keys/values from [q_i, r_i]
        r_col = mem_r.float().unsqueeze(1)                     # (L,1)
        kv_in = torch.cat([mem_q.float(), r_col], dim=1)       # (L, skill_dim+1)
        K = self.k_proj(kv_in)                                 # (L, attn_dim)
        V = self.v_proj(kv_in)                                 # (L, attn_dim)

        # Query from current state + current item mask
        q_state = self.q_from_state(torch.sigmoid(u_decayed))   # (1, attn_dim)
        q_item = self.q_from_item(q_t.float())                  # (1, attn_dim)
        Q = q_state + q_item                                    # (1, attn_dim)

        # dot-product attention score
        dot = (K * Q).sum(dim=1) / math.sqrt(float(self.attn_dim))  # (L,)

        # time bias: penalize far past
        gap = (time_now.squeeze(0) - mem_time.float()).clamp(min=0.0)  # (L,)
        time_w = F.softplus(self.time_w)  # positive
        score_time = -time_w * gap

        # concept bias: reward concept overlap
        overlap = (mem_q.float() * q_t.squeeze(0).float()).sum(dim=1)   # (L,)
        concept_w = F.softplus(self.concept_w)  # positive
        score_concept = concept_w * overlap

        score_total = dot + score_time + score_concept
        alpha = F.softmax(score_total, dim=0)  # (L,)

        c_t = (alpha.unsqueeze(1) * V).sum(dim=0, keepdim=True)  # (1, attn_dim)

        info = {
            "alpha": alpha.detach(),
            "gap": gap.detach(),
            "overlap": overlap.detach(),
            "score_dot": dot.detach(),
            "score_time": score_time.detach(),
            "score_concept": score_concept.detach(),
            "score_total": score_total.detach(),
        }
        return c_t, info

    def step(
        self,
        u_prev: torch.Tensor,
        e_idx: torch.Tensor,
        r: torch.Tensor,
        q_mask: torch.Tensor,
        delta_t: torch.Tensor,
        mem_q: torch.Tensor,
        mem_r: torch.Tensor,
        mem_time: torch.Tensor,
        time_now: torch.Tensor,
        return_attn: bool = False,
    ):
        """
        One interaction step with explicit context retrieval.

        - time_now is assumed to be the *current* timestamp (after applying delta_t upstream)
        - mem_* contain previous interactions only (i < t)

        Returns:
          p, u_new, u_decayed, u_eff, c_t, attn_info (optional)
        """
        u_decayed = self.decay_u(u_prev, delta_t)  # (1, skill_dim)

        c_t, attn_info = self._attend(
            u_decayed=u_decayed,
            q_t=q_mask,
            mem_q=mem_q,
            mem_r=mem_r,
            mem_time=mem_time,
            time_now=time_now,
        )

        u_eff = u_decayed + self.ctx_to_u(c_t)     # (1, skill_dim)

        p = self.predict_from_u(u_eff, e_idx=e_idx, q_mask=q_mask)

        inp = torch.cat([q_mask, r.unsqueeze(-1), c_t], dim=1)  # (1, skill_dim+1+attn_dim)
        u_new = self.gru(inp, u_eff)

        if return_attn:
            return p, u_new, u_decayed, u_eff, c_t, attn_info
        return p, u_new, u_decayed, u_eff, c_t
