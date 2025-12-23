#!/usr/bin/env python3
"""
Minimal NeuralCD-style model in PyTorch for proof-of-life experiments.
"""
import torch
import torch.nn as nn


class NeuralCDM(nn.Module):
    """NeuralCD-style cognitive diagnosis model."""

    def __init__(self, num_students: int, num_items: int, skill_dim: int) -> None:
        super().__init__()
        self.num_students = num_students
        self.num_items = num_items
        self.skill_dim = skill_dim

        # Raw tables (pre-sigmoid)
        self.A = nn.Embedding(num_students, skill_dim)  # student mastery
        self.B = nn.Embedding(num_items, skill_dim)     # item requirement
        self.D = nn.Embedding(num_items, 1)             # item discrimination

        nn.init.normal_(self.A.weight, mean=0.0, std=0.01)
        nn.init.normal_(self.B.weight, mean=0.0, std=0.01)
        nn.init.normal_(self.D.weight, mean=0.0, std=0.01)

        # Simple head: enforce non-negative weights for monotonicity (basic)
        self.head = nn.Linear(skill_dim, 1, bias=True)
        nn.init.constant_(self.head.weight, 0.1)
        nn.init.constant_(self.head.bias, 0.0)

    def forward(self, s_idx: torch.Tensor, e_idx: torch.Tensor, q_mask: torch.Tensor) -> torch.Tensor:
        """
        Compute predicted probability of correctness.
        s_idx: (B,)
        e_idx: (B,)
        q_mask: (B, skill_dim) binary mask
        """
        hs = torch.sigmoid(self.A(s_idx))           # (B,skill_dim)
        he_req = torch.sigmoid(self.B(e_idx))       # (B,skill_dim)
        he_disc = torch.sigmoid(self.D(e_idx))      # (B,1)

        x = q_mask * (hs - he_req)                  # (B,skill_dim)
        x = x * he_disc                             # broadcast (B,skill_dim)

        # Enforce positive weights (simple monotone-ish constraint)
        w = torch.relu(self.head.weight)            # (1,skill_dim)
        logits = (x * w).sum(dim=1) + self.head.bias
        p = torch.sigmoid(logits)
        return p

