#!/usr/bin/env python3
"""
src.state_neuralcdm

Context-aware NeuralCD:
- NO student embedding table A
- Maintains an online student state u (raw), z = sigmoid(u)
- Applies exponential decay using delta_t
- Updates u using a GRUCell
- Predicts correctness using the NeuralCD-style masked interaction with item params
"""
from __future__ import annotations

import torch
import torch.nn as nn


class StateNeuralCDM(nn.Module):
    """NeuralCD head + GRU-based student state with exponential forgetting."""

    def __init__(self, num_items: int, skill_dim: int, lambda_decay: float = 0.03) -> None:
        super().__init__()
        self.num_items = num_items
        self.skill_dim = skill_dim
        self.lambda_decay = float(lambda_decay)

        # Item requirement & discrimination (same idea as baseline)
        self.B = nn.Embedding(num_items, skill_dim)  # item requirement
        self.D = nn.Embedding(num_items, 1)          # item discrimination

        nn.init.normal_(self.B.weight, mean=0.0, std=0.01)
        nn.init.normal_(self.D.weight, mean=0.0, std=0.01)

        # GRU update for student latent u (raw)
        # input = [q_mask (skill_dim), r (1)]
        self.gru = nn.GRUCell(input_size=skill_dim + 1, hidden_size=skill_dim)

        # Prediction head (monotone-ish like baseline)
        self.head = nn.Linear(skill_dim, 1, bias=True)
        nn.init.constant_(self.head.weight, 0.1)
        nn.init.constant_(self.head.bias, 0.0)

    def decay_u(self, u: torch.Tensor, delta_t: torch.Tensor) -> torch.Tensor:
        """
        Exponential decay on raw state:
          u <- u * exp(-lambda * delta_t)
        u: (skill_dim,) or (B, skill_dim)
        delta_t: scalar or (B,)
        """
        dt = delta_t.float().unsqueeze(-1) if delta_t.ndim == 1 else delta_t.float()
        factor = torch.exp(-self.lambda_decay * dt)
        return u * factor

    def predict_from_u(
        self,
        u_decayed: torch.Tensor,
        e_idx: torch.Tensor,
        q_mask: torch.Tensor,
    ) -> torch.Tensor:
        """
        Predict correctness probability using NeuralCD formula but hs := sigmoid(u_decayed).
        Shapes (batch):
          u_decayed: (B, skill_dim)
          e_idx: (B,)
          q_mask: (B, skill_dim)
        """
        hs = torch.sigmoid(u_decayed)            # (B, skill_dim)
        he_req = torch.sigmoid(self.B(e_idx))    # (B, skill_dim)
        he_disc = torch.sigmoid(self.D(e_idx))   # (B, 1)

        x = q_mask * (hs - he_req)               # (B, skill_dim)
        x = x * he_disc                          # broadcast

        w = torch.relu(self.head.weight)         # (1, skill_dim)
        logits = (x * w).sum(dim=1) + self.head.bias
        return torch.sigmoid(logits)

    def step(
        self,
        u_prev: torch.Tensor,
        e_idx: torch.Tensor,
        r: torch.Tensor,
        q_mask: torch.Tensor,
        delta_t: torch.Tensor,
    ):
        """
        One interaction step:
        - decay u_prev using delta_t
        - predict p using u_decayed
        - update u using GRU(u_decayed, [q_mask, r])
        Returns: p, u_new, u_decayed
        """
        u_decayed = self.decay_u(u_prev, delta_t)  # (B, skill_dim)

        p = self.predict_from_u(u_decayed, e_idx=e_idx, q_mask=q_mask)

        # Update state with GRUCell
        inp = torch.cat([q_mask, r.unsqueeze(-1)], dim=1)  # (B, skill_dim+1)
        u_new = self.gru(inp, u_decayed)                   # (B, skill_dim)
        return p, u_new, u_decayed

