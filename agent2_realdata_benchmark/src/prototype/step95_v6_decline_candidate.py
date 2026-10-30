"""V6 *candidate* for synthetic deterioration-aware decisions.

Evidence of decline is based only on item responses; it is not proof of
latent forgetting. No real-student effectiveness or IJCAI novelty claim.
The original V3 and V5 policies are intentionally left unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
import math

from .study_v3_pomcp import CONCEPTS, PRACTICE, GenerativeAssumptions

POLICY_ID = "v6_observation_change_gate_dev_v1"


@dataclass(frozen=True)
class Decision:
    action: str
    concept: str
    signal: bool
    recovery_advantage: float
    policy_id: str = POLICY_ID


class ObservationChangeController:
    """Detect two incorrect responses after two consecutive correct ones.

    A deliberately simple, falsifiable *candidate*, not a validated detector.
    All internal state comes from observed responses, never latent mastery.
    """

    def __init__(self, assumptions: GenerativeAssumptions | None = None,
                 risk_credit: float = 0.012, coverage_weight: float = 0.003):
        if not all(math.isfinite(x) and x >= 0 for x in (risk_credit, coverage_weight)):
            raise ValueError("weights must be finite and nonnegative")
        self.assumptions = assumptions or GenerativeAssumptions()
        self.risk_credit = float(risk_credit)
        self.coverage_weight = float(coverage_weight)
        self.correct_streak = {c: 0 for c in CONCEPTS}
        self.wrong_after_evidence = {c: 0 for c in CONCEPTS}
        self.mastery_evidence = {c: False for c in CONCEPTS}
        self.signals = {c: False for c in CONCEPTS}
        self.observations = {c: 0 for c in CONCEPTS}
        self.signal_onsets = 0

    def observe(self, concept: str, correct: bool) -> None:
        if concept not in CONCEPTS or type(correct) is not bool:
            raise ValueError("invalid observation")
        self.observations[concept] += 1
        if correct:
            self.correct_streak[concept] += 1
            self.wrong_after_evidence[concept] = 0
            if self.correct_streak[concept] >= 2:
                self.mastery_evidence[concept] = True
            # New correct evidence clears a provisional decline flag.
            self.signals[concept] = False
        else:
            self.correct_streak[concept] = 0
            if self.mastery_evidence[concept]:
                self.wrong_after_evidence[concept] += 1
                if self.wrong_after_evidence[concept] >= 2 and not self.signals[concept]:
                    self.signals[concept] = True
                    self.signal_onsets += 1

    def choose(self, belief: Mapping[str, float], resources_left: int) -> Decision:
        if set(belief) != set(CONCEPTS) or any(
            not isinstance(x, (int, float)) or not math.isfinite(x) or not 0 <= x <= 1
            for x in belief.values()
        ):
            raise ValueError("invalid belief")
        if type(resources_left) is not int or not 0 <= resources_left <= 2:
            raise ValueError("invalid resource budget")
        a = self.assumptions
        # Instrumental practice tradeoff plus prespecified coverage preference.
        def practice_score(c):
            return ((1 - belief[c]) * a.rate(PRACTICE) / len(CONCEPTS)
                    - a.cost(PRACTICE)
                    + self.coverage_weight / (1 + self.observations[c]))
        practice = max(CONCEPTS, key=lambda c: (practice_score(c), -CONCEPTS.index(c)))
        if resources_left:
            # Conditional intervention with distinct risk credit; intended to
            # be tested for false alarms, utility and total costs, not assumed beneficial.
            candidates = []
            for c in CONCEPTS:
                if self.signals[c]:
                    action = "WORKED_EXAMPLE"
                    advantage = ((1 - belief[c]) * (a.rate(action) - a.rate(PRACTICE))
                                 / len(CONCEPTS) - (a.cost(action) - a.cost(PRACTICE))
                                 + self.risk_credit)
                    if advantage > 0:
                        candidates.append((advantage, -CONCEPTS.index(c), c))
            if candidates:
                advantage, _, concept = max(candidates)
                self.signals[concept] = False
                self.wrong_after_evidence[concept] = 0
                return Decision("WORKED_EXAMPLE", concept, True, advantage)
        return Decision(PRACTICE, practice, False, 0.0)
