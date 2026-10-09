"""Synthetic single-skill POMDP generative model.

This model is for simulation and planner development only.
Its action effects and uptake probabilities are assumptions,
not measured causal effects or guarantees of real learning.

Sequence:
    assistance offer -> possible use -> mastery transition
    -> independent unhinted probe -> observed correctness

Mastery is binary and absorbing in this initial toy model.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from random import Random


ACTIONS = (
    "no_offer",
    "optional_hint",
    "optional_scaffold",
)


@dataclass(frozen=True)
class ToyPOMDPParameters:
    baseline_learning: float
    hint_increment: float
    scaffold_increment: float
    hint_uptake: float
    scaffold_uptake: float
    slip: float
    guess: float
    hint_cost: float
    scaffold_cost: float

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)

            if type(value) not in (int, float):
                raise TypeError(f"{name} must be numeric")

            if not isfinite(value) or not 0 <= value <= 1:
                raise ValueError(
                    f"{name} must be a finite probability or "
                    "normalized cost in [0, 1]"
                )

        if self.slip + self.guess >= 1:
            raise ValueError("Require slip + guess < 1")


@dataclass(frozen=True)
class ToyStep:
    """One simulated transition and independent response."""

    next_mastered: bool
    assistance_used: bool
    probe_correct: bool
    reward: float


class ToySingleSkillPOMDP:
    """Explicit toy generative model for recovery planning."""

    def __init__(self, params: ToyPOMDPParameters):
        if type(params) is not ToyPOMDPParameters:
            raise TypeError("Expected ToyPOMDPParameters")

        self.params = params

    @staticmethod
    def _validate_action(action: str) -> None:
        if action not in ACTIONS:
            raise ValueError("Unknown planning action")

    @staticmethod
    def _validate_belief(belief: float) -> None:
        if type(belief) not in (int, float):
            raise TypeError("Belief must be numeric")

        if not isfinite(belief) or not 0 <= belief <= 1:
            raise ValueError("Belief must be finite and in [0, 1]")

    def uptake_probability(self, action: str) -> float:
        self._validate_action(action)

        if action == "optional_hint":
            return self.params.hint_uptake

        if action == "optional_scaffold":
            return self.params.scaffold_uptake

        return 0.0

    def learning_increment(self, action: str) -> float:
        self._validate_action(action)

        if action == "optional_hint":
            return self.params.hint_increment

        if action == "optional_scaffold":
            return self.params.scaffold_increment

        return 0.0

    def offer_cost(self, action: str) -> float:
        self._validate_action(action)

        if action == "optional_hint":
            return self.params.hint_cost

        if action == "optional_scaffold":
            return self.params.scaffold_cost

        return 0.0

    def expected_learning_probability(
        self, action: str
    ) -> float:
        """P(next mastered | currently unmastered, offer).

        A used intervention provides an additional chance to
        learn after the baseline learning opportunity.
        """
        base = self.params.baseline_learning

        return base + (1.0 - base) * (
            self.uptake_probability(action)
            * self.learning_increment(action)
        )

    def predict_belief(
        self, belief: float, action: str
    ) -> float:
        """Predict mastery after the action, before the probe."""
        self._validate_belief(belief)

        learning = self.expected_learning_probability(action)

        return belief + (1.0 - belief) * learning

    def update_belief(
        self,
        belief: float,
        action: str,
        probe_correct: bool,
    ) -> float:
        """Bayesian belief update after the independent probe."""
        if type(probe_correct) is not bool:
            raise TypeError("probe_correct must be boolean")

        prior = self.predict_belief(belief, action)

        mastered_likelihood = (
            1.0 - self.params.slip
            if probe_correct
            else self.params.slip
        )

        unmastered_likelihood = (
            self.params.guess
            if probe_correct
            else 1.0 - self.params.guess
        )

        evidence = (
            prior * mastered_likelihood
            + (1.0 - prior) * unmastered_likelihood
        )

        if evidence <= 0.0:
            raise ValueError("Impossible synthetic observation")

        return prior * mastered_likelihood / evidence

    def step(
        self,
        mastered: bool,
        action: str,
        rng: Random,
    ) -> ToyStep:
        """Sample one transition and independent unhinted probe."""
        if type(mastered) is not bool:
            raise TypeError("mastered must be boolean")

        if not isinstance(rng, Random):
            raise TypeError("Expected an explicit random generator")

        self._validate_action(action)

        used = (
            rng.random() < self.uptake_probability(action)
            if action != "no_offer"
            else False
        )

        learning = self.params.baseline_learning

        if used:
            learning += (
                (1.0 - learning)
                * self.learning_increment(action)
            )

        next_mastered = (
            mastered or rng.random() < learning
        )

        p_correct = (
            1.0 - self.params.slip
            if next_mastered
            else self.params.guess
        )

        correct = rng.random() < p_correct

        return ToyStep(
            next_mastered=next_mastered,
            assistance_used=used,
            probe_correct=correct,
            reward=float(correct) - self.offer_cost(action),
        )
