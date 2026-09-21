"""Causal online student adaptation for a frozen NeuralCDM.

Only a new student's local logits are optimized.
All trained global weights and item embeddings remain frozen.
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from src.models.neuralcd import NeuralCDM


class OnlineStudentAdapter:
    """Personalize a frozen NeuralCDM using previously observed responses."""

    def __init__(
        self,
        model: NeuralCDM,
        q_matrix: np.ndarray,
        seen_item_mask: np.ndarray,
        *,
        learning_rate: float = 0.1,
        prior_penalty: float = 0.01,
        device: str = "cpu",
    ) -> None:
        if learning_rate <= 0:
            raise ValueError("learning_rate must be positive")

        if prior_penalty < 0:
            raise ValueError("prior_penalty must be nonnegative")

        self.device = torch.device(device)
        self.model = model.to(self.device)

        # Disable dropout and freeze ALL global model parameters.
        self.model.eval()
        self.model.requires_grad_(False)

        q = np.asarray(q_matrix)

        if q.shape != (
            model.n_items,
            model.n_concepts,
        ):
            raise ValueError("Q-matrix shape mismatch")

        if not np.isin(q, [0, 1]).all():
            raise ValueError("Q-matrix must be binary")

        seen = np.asarray(seen_item_mask, dtype=bool)

        if seen.shape != (model.n_items,):
            raise ValueError("Seen-item mask shape mismatch")

        self.q = torch.tensor(
            q,
            dtype=torch.float32,
            device=self.device,
        )

        self.seen = seen.copy()
        self.prior_penalty = prior_penalty

        # A training-derived prior; NO validation student embedding.
        self.prior = (
            self.model.student_emb.weight
            .detach()
            .mean(dim=0)
            .clone()
        )

        self.local_logits = nn.Parameter(
            self.prior.clone()
        )

        self.optimizer = torch.optim.SGD(
            [self.local_logits],
            lr=learning_rate,
        )

        self.observations = 0

    def supported(self, item_idx: int) -> bool:
        """Whether this question has trained item parameters and tags."""
        if not 0 <= item_idx < self.model.n_items:
            raise ValueError("Item index out of range")

        return bool(
            self.seen[item_idx]
            and self.q[item_idx].sum().item() > 0
        )

    def _forward(self, item_idx: int) -> torch.Tensor:
        item = torch.tensor(
            [item_idx],
            dtype=torch.long,
            device=self.device,
        )

        mask = self.q[item_idx].unsqueeze(0)

        return self.model.predict_with_student_logits(
            self.local_logits.unsqueeze(0),
            item,
            mask,
        )

    def predict(self, item_idx: int) -> float | None:
        """Predict without observing or updating from the current answer."""
        if not self.supported(item_idx):
            return None

        with torch.no_grad():
            probability = float(
                self._forward(item_idx).item()
            )

        if not np.isfinite(probability):
            raise RuntimeError("Nonfinite prediction")

        return probability

    def observe(self, item_idx: int, correct: int) -> bool:
        """After observing the response, update ONLY local student logits."""
        if correct not in (0, 1):
            raise ValueError("correct must be 0 or 1")

        if not self.supported(item_idx):
            return False

        target = torch.tensor(
            [[float(correct)]],
            dtype=torch.float32,
            device=self.device,
        )

        self.optimizer.zero_grad(set_to_none=True)

        probability = self._forward(item_idx)

        loss = F.binary_cross_entropy(
            probability,
            target,
        )

        regularization = (
            self.local_logits - self.prior
        ).square().mean()

        objective = (
            loss + self.prior_penalty * regularization
        )

        if not torch.isfinite(objective):
            raise RuntimeError("Nonfinite adaptation objective")

        objective.backward()

        if (
            self.local_logits.grad is None
            or not torch.isfinite(
                self.local_logits.grad
            ).all()
        ):
            raise RuntimeError("Invalid local adaptation gradient")

        self.optimizer.step()

        if not torch.isfinite(self.local_logits).all():
            raise RuntimeError("Nonfinite local student state")

        self.observations += 1
        return True

    def mastery_proxy(self) -> np.ndarray:
        """Return bounded latent proficiency, not verified true mastery."""
        with torch.no_grad():
            return (
                torch.sigmoid(self.local_logits)
                .detach()
                .cpu()
                .numpy()
                .copy()
            )


class FrozenPriorAdapter(OnlineStudentAdapter):
    """No-adaptation control with the identical training-derived prior.

    Observations are counted to satisfy the chronological evaluator's
    accounting contract, but no local or global parameters are updated.
    """

    def observe(self, item_idx: int, correct: int) -> bool:
        if correct not in (0, 1):
            raise ValueError("correct must be 0 or 1")

        if not self.supported(item_idx):
            return False

        self.observations += 1
        return True
