"""Finite-horizon POMCP-style belief-sampling MCTS.

Synthetic research prototype only.

Uses root-state sampling, a history-indexed observation tree,
UCT exploration, and a no-offer rollout policy.

Does not deliver interventions, learn causal treatment effects,
or persist/reuse belief particles between real observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log, sqrt
from random import Random

from src.planning.pomdp import ACTIONS, ToySingleSkillPOMDP


MAX_SIMULATIONS = 20000
MAX_HORIZON = 5


@dataclass(frozen=True)
class MonteCarloPlan:
    first_action: str
    estimated_return: float
    action_values: tuple[tuple[str, float, int], ...]
    simulations: int


class _HistoryNode:
    """Search statistics for one simulated observation history."""

    def __init__(self, actions: tuple[str, ...]):
        self.visits = 0
        self.action_visits = {a: 0 for a in actions}
        self.action_returns = {a: 0.0 for a in actions}
        self.children = {}


def solve_pomcp(
    model: ToySingleSkillPOMDP,
    *,
    belief: float,
    horizon: int,
    simulations: int = 3000,
    discount: float = 0.95,
    exploration: float = 1.4,
    seed: int = 2027,
    allowed_actions: tuple[str, ...] = ACTIONS,
) -> MonteCarloPlan:
    """Approximate the best first action by simulated tree search."""

    if type(model) is not ToySingleSkillPOMDP:
        raise TypeError("Expected ToySingleSkillPOMDP")

    if type(belief) not in (int, float):
        raise TypeError("Belief must be numeric")

    if not isfinite(belief) or not 0 <= belief <= 1:
        raise ValueError("Invalid belief")

    if type(horizon) is not int:
        raise TypeError("Horizon must be an integer")

    if not 1 <= horizon <= MAX_HORIZON:
        raise ValueError("Invalid planning horizon")

    if type(allowed_actions) is not tuple:
        raise TypeError("Allowed actions must be a tuple")

    if any(type(a) is not str for a in allowed_actions):
        raise TypeError("Actions must be strings")

    if len(set(allowed_actions)) != len(allowed_actions):
        raise ValueError("Duplicate actions")

    if "no_offer" not in allowed_actions:
        raise ValueError("No-offer fallback is required")

    if any(a not in ACTIONS for a in allowed_actions):
        raise ValueError("Unknown action")

    # Canonical ordering ensures reproducible tie-breaking.
    actions = tuple(
        a for a in ACTIONS if a in allowed_actions
    )

    if type(simulations) is not int:
        raise TypeError("Simulations must be an integer")

    if not len(actions) <= simulations <= MAX_SIMULATIONS:
        raise ValueError("Invalid simulation budget")

    for name, value in (
        ("discount", discount),
        ("exploration", exploration),
    ):
        if type(value) not in (int, float):
            raise TypeError(f"{name} must be numeric")

        if not isfinite(value):
            raise ValueError(f"{name} must be finite")

    if not 0 <= discount <= 1:
        raise ValueError("Discount must be in [0, 1]")

    if not 0 <= exploration <= 10:
        raise ValueError("Exploration must be in [0, 10]")

    if type(seed) is not int:
        raise TypeError("Seed must be an integer")

    rng = Random(seed)
    root = _HistoryNode(actions)

    def rollout(mastered: bool, depth: int) -> float:
        """Default continuation policy: no further assistance."""

        total = 0.0
        weight = 1.0
        current = mastered

        for _ in range(depth):
            outcome = model.step(current, "no_offer", rng)

            total += weight * outcome.reward
            weight *= discount
            current = outcome.next_mastered

        return total

    def simulate(
        mastered: bool,
        depth: int,
        node: _HistoryNode,
    ) -> float:
        if depth == 0:
            return 0.0

        unvisited = [
            a for a in actions
            if node.action_visits[a] == 0
        ]

        if unvisited:
            action = unvisited[0]
        else:
            def uct(a: str) -> float:
                count = node.action_visits[a]
                mean = node.action_returns[a] / count
                bonus = exploration * sqrt(
                    log(node.visits + 1) / count
                )
                return mean + bonus

            action = max(actions, key=uct)

        result = model.step(mastered, action, rng)

        if depth == 1:
            future = 0.0
        else:
            key = (action, result.probe_correct)

            if key not in node.children:
                node.children[key] = _HistoryNode(actions)

                future = rollout(
                    result.next_mastered,
                    depth - 1,
                )
            else:
                future = simulate(
                    result.next_mastered,
                    depth - 1,
                    node.children[key],
                )

        total = result.reward + discount * future

        node.visits += 1
        node.action_visits[action] += 1
        node.action_returns[action] += total

        return total

    for _ in range(simulations):
        sampled_mastery = rng.random() < belief

        simulate(
            sampled_mastery,
            horizon,
            root,
        )

    action_values = tuple(
        (
            action,
            root.action_returns[action]
            / root.action_visits[action],
            root.action_visits[action],
        )
        for action in actions
    )

    # Select the highest empirical mean; retain canonical ties.
    best_action, best_value, _ = max(
        action_values,
        key=lambda entry: entry[1],
    )

    return MonteCarloPlan(
        first_action=best_action,
        estimated_return=best_value,
        action_values=action_values,
        simulations=simulations,
    )
