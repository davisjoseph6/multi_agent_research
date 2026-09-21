#!/usr/bin/env python3
"""NeuralCDM architecture adapted to the frozen Phase 6 benchmark.

Reference:
bigdata-ustc/Neural_Cognitive_Diagnosis-NeuralCD
commit de4d9b593c046b807f8696c60782165a6f3a949c

The network architecture follows the reference implementation.
The separate student-logit interface enables later cold-start
adaptation without allocating embeddings for validation students.
"""

from __future__ import annotations

import torch
from torch import nn


class NeuralCDM(nn.Module):
    """Q-matrix-based neural cognitive diagnosis model."""

    def __init__(
        self,
        n_students: int,
        n_items: int,
        n_concepts: int,
    ) -> None:
        super().__init__()

        if min(n_students, n_items, n_concepts) < 1:
            raise ValueError("All model dimensions must be positive")

        self.n_students = n_students
        self.n_items = n_items
        self.n_concepts = n_concepts

        # Use reference names for state-dictionary compatibility.
        self.student_emb = nn.Embedding(
            n_students, n_concepts
        )
        self.k_difficulty = nn.Embedding(
            n_items, n_concepts
        )
        self.e_discrimination = nn.Embedding(
            n_items, 1
        )

        self.prednet_full1 = nn.Linear(
            n_concepts, 512
        )
        self.drop_1 = nn.Dropout(p=0.5)

        self.prednet_full2 = nn.Linear(
            512, 256
        )
        self.drop_2 = nn.Dropout(p=0.5)

        self.prednet_full3 = nn.Linear(
            256, 1
        )

        # Match the reference's Xavier weight initialization.
        for name, parameter in self.named_parameters():
            if "weight" in name:
                nn.init.xavier_normal_(parameter)

        # Ensure monotonicity already holds before the first step.
        self.apply_clipper()

    @torch.no_grad()
    def apply_clipper(self) -> None:
        """Enforce nonnegative prediction-network weights."""
        for layer in (
            self.prednet_full1,
            self.prednet_full2,
            self.prednet_full3,
        ):
            layer.weight.clamp_(min=0.0)

    def _predict_from_logits(
        self,
        student_logits: torch.Tensor,
        item_ids: torch.Tensor,
        q_mask: torch.Tensor,
    ) -> torch.Tensor:
        """Predict with an explicitly supplied student representation."""
        if student_logits.ndim != 2:
            raise ValueError(
                "student_logits must have shape [batch, concepts]"
            )

        batch = student_logits.shape[0]

        if student_logits.shape[1] != self.n_concepts:
            raise ValueError("Incorrect student concept dimension")

        if item_ids.shape != (batch,):
            raise ValueError("item_ids must have shape [batch]")

        if q_mask.shape != (batch, self.n_concepts):
            raise ValueError("Incorrect Q-mask shape")

        if torch.any(q_mask.sum(dim=1) <= 0):
            raise ValueError(
                "NeuralCDM requires annotated questions"
            )

        mastery = torch.sigmoid(student_logits)

        difficulty = torch.sigmoid(
            self.k_difficulty(item_ids)
        )

        discrimination = (
            torch.sigmoid(self.e_discrimination(item_ids))
            * 10.0
        )

        x = (
            discrimination
            * (mastery - difficulty)
            * q_mask
        )

        x = self.drop_1(
            torch.sigmoid(self.prednet_full1(x))
        )

        x = self.drop_2(
            torch.sigmoid(self.prednet_full2(x))
        )

        return torch.sigmoid(
            self.prednet_full3(x)
        )

    def forward(
        self,
        student_ids: torch.Tensor,
        item_ids: torch.Tensor,
        q_mask: torch.Tensor,
    ) -> torch.Tensor:
        """Ordinary NeuralCDM prediction for training students."""
        if student_ids.ndim != 1:
            raise ValueError(
                "student_ids must have shape [batch]"
            )

        return self._predict_from_logits(
            self.student_emb(student_ids),
            item_ids,
            q_mask,
        )

    def predict_with_student_logits(
        self,
        student_logits: torch.Tensor,
        item_ids: torch.Tensor,
        q_mask: torch.Tensor,
    ) -> torch.Tensor:
        """Predict for a supplied student, including an unseen student.

        This method does not itself perform adaptation. A later,
        separately tested procedure will optimize only the local
        student representation using past responses.
        """
        if student_logits.ndim == 1:
            student_logits = student_logits.unsqueeze(0)

        return self._predict_from_logits(
            student_logits,
            item_ids,
            q_mask,
        )

    @torch.no_grad()
    def get_knowledge_status(
        self,
        student_ids: torch.Tensor,
    ) -> torch.Tensor:
        """Return bounded latent proficiency representations."""
        return torch.sigmoid(
            self.student_emb(student_ids)
        ).detach().clone()
