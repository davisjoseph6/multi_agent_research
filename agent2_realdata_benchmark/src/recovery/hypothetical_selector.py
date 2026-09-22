"""Isolated selector using explicitly hypothetical intervention scores.

Research prototype only. No learned causal effects, student-facing
delivery, response outcomes, or modifications to frozen Phase 6 models.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from src.recovery.controller import RecoveryPlan


ALLOWED_OPTIONS = frozenset({
    "optional_hint",
    "optional_scaffold",
})


@dataclass(frozen=True)
class HypotheticalScore:
    """Synthetic assumptions, never estimated intervention effects.

    Both quantities use assumed probability-point-equivalent units.
    Their difference is a hypothetical decision score, not evidence.
    """

    assumed_benefit: float
    assumed_burden: float

    def __post_init__(self) -> None:
        for name in ("assumed_benefit", "assumed_burden"):
            value = getattr(self, name)

            if type(value) not in (int, float):
                raise TypeError(f"{name} must be numeric")

            if not isfinite(value):
                raise ValueError(f"{name} must be finite")

        if not -1.0 <= self.assumed_benefit <= 1.0:
            raise ValueError("assumed_benefit must be in [-1, 1]")

        if not 0.0 <= self.assumed_burden <= 1.0:
            raise ValueError("assumed_burden must be in [0, 1]")


@dataclass(frozen=True)
class HypotheticalSelection:
    """A synthetic choice; never evidence of intervention delivery."""

    disposition: str
    selected_option: str | None
    assumed_net_score: float | None
    reason: str


def select_hypothetical(
    plan: RecoveryPlan,
    *,
    scores: dict[str, HypotheticalScore],
) -> HypotheticalSelection:
    """Select among already proposed options; otherwise abstain."""

    if type(plan) is not RecoveryPlan:
        raise TypeError("Expected RecoveryPlan")

    if type(scores) is not dict:
        raise TypeError("Expected a dictionary of hypothetical scores")

    options = plan.proposed_options

    if type(options) is not tuple:
        raise TypeError("Expected a tuple of proposed options")

    if len(options) != len(set(options)):
        raise ValueError("Duplicate proposed options")

    if not set(options).issubset(ALLOWED_OPTIONS):
        raise ValueError("Unknown proposed option")

    if plan.disposition != "proposed":
        if options or scores:
            raise ValueError("Non-proposed plans cannot supply options or scores")

        return HypotheticalSelection(
            disposition="abstain",
            selected_option=None,
            assumed_net_score=None,
            reason="upstream_plan_not_proposed",
        )

    if not options:
        raise ValueError("Proposed plan must contain options")

    if set(scores) != set(options):
        raise ValueError("Scores must match proposed options exactly")

    for score in scores.values():
        if type(score) is not HypotheticalScore:
            raise TypeError("Expected HypotheticalScore values")

    best_option = None
    best_score = 0.0

    # Sorting establishes a reproducible tie-breaking order.
    for option in sorted(options):
        score = scores[option]
        utility = score.assumed_benefit - score.assumed_burden

        if utility > best_score:
            best_option = option
            best_score = utility

    if best_option is None:
        return HypotheticalSelection(
            disposition="abstain",
            selected_option=None,
            assumed_net_score=None,
            reason="no_positive_assumed_utility",
        )

    return HypotheticalSelection(
        disposition="selected",
        selected_option=best_option,
        assumed_net_score=best_score,
        reason="highest_positive_assumed_utility",
    )
