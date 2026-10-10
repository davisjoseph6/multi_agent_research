"""Local demonstration BKT belief-state adapter.

Parameters are illustrative, not calibrated to the
Behavioral Economics pilot population.

This module does not estimate intervention effects.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.models.bkt import BKT, BKTParams


_DEMO_SKILL = (0,)


@dataclass(frozen=True)
class PracticeBeliefEvent:
    """Internal record of one practice-response belief update."""

    correct: bool
    mastery_before: float
    pre_response_probability: float
    mastery_after: float


class DemoBeliefTracker:
    """One learner's single-concept BKT state."""

    def __init__(self) -> None:
        self._bkt = BKT(
            num_concepts=1,
            params=BKTParams(
                initial_mastery=0.20,
                learning=0.10,
                slip=0.10,
                guess=0.25,
            ),
        )

    @property
    def mastery(self) -> float:
        """Current mastery belief, not observed mastery."""
        return float(self._bkt.mastery[0])

    def predict_practice(self) -> float:
        """Predict correctness before observing a response."""
        return self._bkt.predict(_DEMO_SKILL)

    def observe_practice(
        self,
        *,
        correct: bool,
    ) -> PracticeBeliefEvent:
        """Update belief after one practice response."""

        if type(correct) is not bool:
            raise TypeError("correct must be explicitly boolean")

        before = self.mastery
        prediction = self.predict_practice()

        self._bkt.update(
            _DEMO_SKILL,
            int(correct),
        )

        return PracticeBeliefEvent(
            correct=correct,
            mastery_before=before,
            pre_response_probability=prediction,
            mastery_after=self.mastery,
        )
