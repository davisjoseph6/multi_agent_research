"""Exact finite-horizon planning for the toy binary-mastery POMDP.

Synthetic research reference only. The solution is exact under
the supplied toy model, not necessarily for real students.

Every simulated step represents one action followed by one
independent probe. This is not yet the real quiz schedule.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import isfinite

from src.planning.pomdp import ACTIONS, ToySingleSkillPOMDP
from src.recovery.controller import RecoveryPlan


MAX_EXACT_HORIZON = 5


@dataclass(frozen=True)
class ExactPlan:
    """Optimal first action under stated synthetic assumptions."""

    first_action: str
    expected_return: float
    action_values: tuple[tuple[str, float], ...]


def available_actions_from_plan(
    plan: RecoveryPlan,
) -> tuple[str, ...]:
    """Convert a validated recovery proposal into allowed actions.

    No offer is always the conservative fallback.
    This function never authorizes assistance delivery.
    """
    if type(plan) is not RecoveryPlan:
        raise TypeError("Expected RecoveryPlan")

    options = plan.proposed_options

    if type(options) is not tuple:
        raise TypeError("Proposed options must be a tuple")

    if any(type(option) is not str for option in options):
        raise TypeError("Proposed options must be strings")

    if len(set(options)) != len(options):
        raise ValueError("Duplicate proposed options")

    if any(option not in ACTIONS[1:] for option in options):
        raise ValueError("Unknown proposed option")

    valid_dispositions = {
        "proposed",
        "no_action",
        "blocked",
        "deferred",
        "abstain",
    }

    if plan.disposition not in valid_dispositions:
        raise ValueError("Unknown recovery disposition")

    if plan.disposition == "proposed":
        if plan.detector_status != "flag" or not options:
            raise ValueError("Inconsistent proposed recovery")
    elif options:
        raise ValueError("Non-proposed recovery contains assistance")

    return tuple(
        action for action in ACTIONS
        if action == "no_offer" or action in options
    )


def solve_exact_pomdp(
    model: ToySingleSkillPOMDP,
    *,
    belief: float,
    horizon: int,
    discount: float = 0.95,
    allowed_actions: tuple[str, ...] = ACTIONS,
) -> ExactPlan:
    """Compute an exact finite-horizon belief-space policy.

    The returned first action maximizes expected discounted
    simulated probe correctness minus assistance-offer costs.

    Subsequent actions are optimized separately for each
    possible future observation.
    """
    if type(model) is not ToySingleSkillPOMDP:
        raise TypeError("Expected ToySingleSkillPOMDP")

    if type(belief) not in (int, float):
        raise TypeError("Belief must be numeric")

    if not isfinite(belief) or not 0.0 <= belief <= 1.0:
        raise ValueError("Belief must be finite and in [0, 1]")

    if type(horizon) is not int:
        raise TypeError("Horizon must be an integer")

    if not 1 <= horizon <= MAX_EXACT_HORIZON:
        raise ValueError("Horizon outside supported range")

    if type(discount) not in (int, float):
        raise TypeError("Discount must be numeric")

    if not isfinite(discount) or not 0.0 <= discount <= 1.0:
        raise ValueError("Discount must be finite and in [0, 1]")

    if type(allowed_actions) is not tuple:
        raise TypeError("Allowed actions must be a tuple")

    if any(type(action) is not str for action in allowed_actions):
        raise TypeError("Allowed actions must be strings")

    if len(set(allowed_actions)) != len(allowed_actions):
        raise ValueError("Duplicate allowed actions")

    if "no_offer" not in allowed_actions:
        raise ValueError("No-offer fallback is required")

    if any(action not in ACTIONS for action in allowed_actions):
        raise ValueError("Unknown allowed action")

    # Canonical ordering makes ties deterministic.
    actions = tuple(
        action for action in ACTIONS if action in allowed_actions
    )

    @lru_cache(maxsize=None)
    def value(depth: int, current_belief: float) -> float:
        if depth == 0:
            return 0.0

        return max(
            action_value(depth, current_belief, action)
            for action in actions
        )

    def action_value(
        depth: int,
        current_belief: float,
        action: str,
    ) -> float:
        predicted = model.predict_belief(
            current_belief, action
        )

        p_correct = (
            predicted * (1.0 - model.params.slip)
            + (1.0 - predicted) * model.params.guess
        )

        immediate = p_correct - model.offer_cost(action)

        if depth == 1:
            return immediate

        future = 0.0

        if p_correct > 0.0:
            correct_belief = model.update_belief(
                current_belief, action, True
            )

            future += p_correct * value(
                depth - 1, correct_belief
            )

        if p_correct < 1.0:
            incorrect_belief = model.update_belief(
                current_belief, action, False
            )

            future += (1.0 - p_correct) * value(
                depth - 1, incorrect_belief
            )

        return immediate + discount * future

    action_values = tuple(
        (action, action_value(horizon, belief, action))
        for action in actions
    )

    # max() keeps the first action on ties.
    best_action, best_value = max(
        action_values,
        key=lambda entry: entry[1],
    )

    return ExactPlan(
        first_action=best_action,
        expected_return=best_value,
        action_values=action_values,
    )
