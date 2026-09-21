#!/usr/bin/env python3
"""BKT with an explicit factorized conjunctive multi-skill extension.

Single-skill questions use standard BKT.

Multi-skill questions assume all required concepts must be mastered,
with independent Bernoulli concept-mastery beliefs.

Parameters here are initial values, not fitted estimates. Fit them
using training students before reporting benchmark performance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


EPS = 1e-12


@dataclass(frozen=True)
class BKTParams:
    """Shared BKT parameters for an initial baseline."""

    initial_mastery: float = 0.20
    learning: float = 0.10
    slip: float = 0.10
    guess: float = 0.25

    def __post_init__(self) -> None:
        values = (
            self.initial_mastery,
            self.learning,
            self.slip,
            self.guess,
        )

        if not all(np.isfinite(value) for value in values):
            raise ValueError("BKT parameters must be finite")

        if not 0 < self.initial_mastery < 1:
            raise ValueError("Initial mastery must be in (0, 1)")

        if not 0 <= self.learning <= 1:
            raise ValueError("Learning must be in [0, 1]")

        if not 0 <= self.slip < 1:
            raise ValueError("Slip must be in [0, 1)")

        if not 0 <= self.guess < 1:
            raise ValueError("Guess must be in [0, 1)")

        if self.slip + self.guess >= 1:
            raise ValueError(
                "Require slip + guess < 1 so correctness "
                "is positively associated with mastery"
            )


class BKT:
    """Maintain one learner's factorized concept-mastery belief."""

    def __init__(
        self,
        num_concepts: int,
        params: BKTParams | None = None,
    ) -> None:
        if num_concepts < 1:
            raise ValueError("num_concepts must be positive")

        self.num_concepts = num_concepts
        self.params = params or BKTParams()

        self._mastery = np.full(
            num_concepts,
            self.params.initial_mastery,
            dtype=np.float64,
        )

    @property
    def mastery(self) -> np.ndarray:
        """Return a copy; callers cannot mutate the internal state."""
        return self._mastery.copy()

    def _indices(self, skills: Sequence[int]) -> np.ndarray:
        """Validate an ordered set of concept indices."""
        indices = []

        for index in skills:
            if isinstance(index, (bool, np.bool_)) or not isinstance(
                index, (int, np.integer)
            ):
                raise ValueError(f"Invalid concept index: {index!r}")

            value = int(index)

            if not 0 <= value < self.num_concepts:
                raise ValueError(f"Concept index out of range: {value}")

            indices.append(value)

        if len(indices) != len(set(indices)):
            raise ValueError("Duplicate concept indices are not allowed")

        return np.asarray(indices, dtype=np.int64)

    def predict(self, skills: Sequence[int]) -> float:
        """Predict correctness BEFORE observing the current response."""
        indices = self._indices(skills)

        if len(indices) == 0:
            raise ValueError(
                "Cannot predict a question without concept annotations"
            )

        joint_mastery = float(np.prod(self._mastery[indices]))

        probability = (
            self.params.guess
            + (1.0 - self.params.slip - self.params.guess)
            * joint_mastery
        )

        return float(np.clip(probability, EPS, 1.0 - EPS))

    def update(self, skills: Sequence[int], correct: int) -> None:
        """Observe the response and update all tagged concepts together."""
        if correct not in (0, 1):
            raise ValueError("correct must be 0 or 1")

        indices = self._indices(skills)

        # Unknown concept annotations do not justify a mastery update.
        if len(indices) == 0:
            return

        prior = self._mastery[indices].copy()
        probability_correct = self.predict(indices.tolist())

        guess = self.params.guess
        discrimination = 1.0 - self.params.slip - guess

        posterior = np.empty_like(prior)

        # Compute every posterior using the SAME pre-response state.
        for position, mastery in enumerate(prior):
            other_mastery = float(np.prod(
                np.delete(prior, position)
            ))

            # P(correct | concept i mastered), marginalizing others.
            p_correct_if_mastered = (
                guess + discrimination * other_mastery
            )

            if correct == 1:
                likelihood = p_correct_if_mastered
                evidence = probability_correct
            else:
                likelihood = 1.0 - p_correct_if_mastered
                evidence = 1.0 - probability_correct

            posterior[position] = (
                mastery * likelihood / max(evidence, EPS)
            )

        posterior = np.clip(posterior, 0.0, 1.0)

        # Apply the learning transition after observing the response.
        updated = (
            posterior
            + (1.0 - posterior) * self.params.learning
        )

        self._mastery[indices] = np.clip(updated, 0.0, 1.0)

    def reset(self) -> None:
        """Reset this learner to the population initial mastery."""
        self._mastery.fill(self.params.initial_mastery)
