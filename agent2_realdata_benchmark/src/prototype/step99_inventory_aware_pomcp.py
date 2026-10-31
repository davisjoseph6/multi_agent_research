"""Step 99: inventory-aware POMCP-style research planner (NOT deployed).

An additive research-only planner. V3, trial arms, original frozen results,
and the human enrollment gate are unchanged.

Unlike the existing V3 internal search, *every simulated practice action
consumes one of the actual 55 draft practice questions*, and reaching
20/20/15 practice-question boundaries resets the two-resource allowance.
Resources consume an allowance but do not count toward practice-question
quotas. Resource content and question IDs are NOT individually simulated.

The transition, answer likelihood, rate and cost are the same uncalibrated
GenerativeAssumptions used in the original V3 synthetic planner. This is
an engineering consistency experiment, not a validated learner model.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import random
from typing import Mapping

from .study_v2 import CONCEPTS, RECOVERY_ACTIONS, SESSION_TARGETS
from .study_v3_pomcp import (
    GenerativeAssumptions, PRACTICE, OBSERVABLE, action_key,
)

TOTAL_PRACTICE = sum(SESSION_TARGETS)
DRAFT_COUNTS = (7, 7, 7, 7, 7, 7, 7, 6)
N = len(CONCEPTS)


@dataclass(frozen=True)
class InventoryProgress:
    """Fully observable study progress, never latent learner information.

    Valid for the exact initial 55-question bank. The executed RCT's
    selection of specific question IDs remains outside this model.
    """

    remaining: tuple[int, ...] = DRAFT_COUNTS
    session: int = 0
    answered_in_session: int = 0
    resources_left: int = 2

    def __post_init__(self) -> None:
        if (len(self.remaining) != N
                or any(type(v) is not int or v < 0 for v in self.remaining)
                or any(v > cap for v, cap in zip(self.remaining, DRAFT_COUNTS))):
            raise ValueError("Invalid inventory counts")
        if type(self.session) is not int or not 0 <= self.session <= len(SESSION_TARGETS):
            raise ValueError("Invalid session number")
        if type(self.answered_in_session) is not int or type(self.resources_left) is not int:
            raise ValueError("Invalid session counters")
        if self.session == len(SESSION_TARGETS):
            if (self.answered_in_session != 0 or self.resources_left != 0
                    or any(self.remaining)):
                raise ValueError("Completed protocol must be terminal")
        else:
            if not (0 <= self.answered_in_session < SESSION_TARGETS[self.session]
                    and 0 <= self.resources_left <= 2):
                raise ValueError("Invalid active-session counts")
            answered = sum(SESSION_TARGETS[:self.session]) + self.answered_in_session
            if sum(self.remaining) != TOTAL_PRACTICE - answered:
                raise ValueError("Inventory and question count disagree")

    @property
    def done(self) -> bool:
        return self.session == len(SESSION_TARGETS)

    def legal(self) -> tuple[tuple[str, str], ...]:
        if self.done:
            return ()
        active = tuple(c for c, n in zip(CONCEPTS, self.remaining) if n)
        question_actions = tuple((PRACTICE, c) for c in active)
        # The online V3 study requires a QUESTION as the first action in
        # each session (a warmup). Enforce the same constraint throughout
        # POMCP tree expansion AND random rollouts, not just at the root.
        # The actual V3 warmup *selects* its item greedily by belief,
        # difficulty and item_id. This reduced model lacks item identity,
        # so choosing among legal warmup questions is still a fidelity gap.
        if self.answered_in_session == 0:
            return question_actions
        resource_actions = (
            tuple((kind, c) for c in active for kind in RECOVERY_ACTIONS)
            if self.resources_left else ()
        )
        return question_actions + resource_actions

    def after(self, action: tuple[str, str]) -> "InventoryProgress":
        if action not in self.legal():
            raise ValueError("Action not feasible in current inventory")
        kind, concept = action
        if kind != PRACTICE:
            return InventoryProgress(self.remaining, self.session,
                                     self.answered_in_session,
                                     self.resources_left - 1)
        index = CONCEPTS.index(concept)
        remaining = list(self.remaining)
        remaining[index] -= 1
        index_in_session = self.answered_in_session + 1
        if index_in_session == SESSION_TARGETS[self.session]:
            next_session = self.session + 1
            return InventoryProgress(
                tuple(remaining), next_session, 0,
                2 if next_session < len(SESSION_TARGETS) else 0,
            )
        return InventoryProgress(
            tuple(remaining), self.session, index_in_session,
            self.resources_left,
        )


@dataclass(frozen=True)
class SimulatedState:
    mastery: tuple[bool, ...]
    progress: InventoryProgress

    def __post_init__(self) -> None:
        if len(self.mastery) != N or any(type(x) is not bool for x in self.mastery):
            raise ValueError("Eight binary latent states required")


@dataclass(frozen=True)
class ResearchPlan:
    action: str
    concept: str
    simulations: int
    horizon: int
    root_visits: dict[str, int]
    root_values: dict[str, float | None]
    version: str = "step99_inventory_consuming_pomcp_dev_only"
    synthetic_only: bool = True


class InventoryAwarePOMCP:
    """UCT over observation histories with root-sampled synthetic mastery.

    Dynamic legality now depends on simulated question inventory and
    session-local resource budget. Simulator still omits question identity,
    item response difficulty, fatigue, real-school dropout and belief-model
    calibration. Do not substitute into the RCT without a new protocol.
    """

    def __init__(self, *, horizon: int = 3, simulations: int = 240,
                 exploration: float = 0.6, discount: float = 0.95,
                 assumptions: GenerativeAssumptions | None = None):
        if type(horizon) is not int or not 1 <= horizon <= 20:
            raise ValueError("Horizon must be 1..20")
        if type(simulations) is not int or not 1 <= simulations <= 100000:
            raise ValueError("Simulations must be 1..100000")
        if (not math.isfinite(exploration) or exploration < 0
                or not math.isfinite(discount) or not 0 < discount <= 1):
            raise ValueError("Invalid exploration or discount")
        self.horizon = horizon
        self.simulations = simulations
        self.exploration = exploration
        self.discount = discount
        self.assumptions = assumptions or GenerativeAssumptions()

    def step(self, state: SimulatedState, action: tuple[str, str],
             rng: random.Random) -> tuple[SimulatedState, int | None, float]:
        """Answer occurs before learning, matching historical V3 convention."""
        progress = state.progress.after(action)
        kind, concept = action
        idx = CONCEPTS.index(concept)
        mastered = list(state.mastery)
        prior = mastered[idx]
        observation = None
        if kind in OBSERVABLE:
            p_correct = (1 - self.assumptions.slip) if prior else self.assumptions.guess
            observation = int(rng.random() < p_correct)
        mastered[idx] = prior or (rng.random() < self.assumptions.rate(kind))
        reward = (int(mastered[idx]) - int(prior)) / N - self.assumptions.cost(kind)
        return SimulatedState(tuple(mastered), progress), observation, reward

    def choose(self, belief: Mapping[str, float], progress: InventoryProgress,
               *, seed: int = 71) -> ResearchPlan:
        if not isinstance(progress, InventoryProgress) or not progress.legal():
            raise ValueError("Planner needs a nonterminal practice inventory")
        if type(seed) is not int:
            raise ValueError("Seed must be an integer")
        if (set(belief) != set(CONCEPTS)
                or any(type(v) not in (float, int)
                       or not math.isfinite(v) or not 0 <= v <= 1
                       for v in belief.values())):
            raise ValueError("Eight bounded mastery beliefs required")
        rng = random.Random(seed)
        visits = Counter()
        edge_visits = Counter()
        edge_returns = Counter()

        def rollout(state: SimulatedState, steps: int) -> float:
            value = 0.0
            factor = 1.0
            for _ in range(steps):
                legal = state.progress.legal()
                if not legal:
                    break
                state, _, reward = self.step(state, rng.choice(legal), rng)
                value += factor * reward
                factor *= self.discount
            return value

        def simulate(state: SimulatedState, history: tuple, depth: int) -> float:
            legal = state.progress.legal()
            if not depth or not legal:
                return 0.0
            if not visits[history]:
                visits[history] += 1
                return rollout(state, depth)
            unexplored = [a for a in legal if edge_visits[(history, a)] == 0]
            if unexplored:
                action = rng.choice(unexplored)
            else:
                action = max(legal, key=lambda a: (
                    edge_returns[(history, a)] / edge_visits[(history, a)]
                    + self.exploration * math.sqrt(
                        math.log(visits[history] + 1) / edge_visits[(history, a)]
                    ),
                    -legal.index(a),
                ))
            next_state, observation, immediate = self.step(state, action, rng)
            future = simulate(next_state, history + ((action, observation),),
                              depth - 1)
            gain = immediate + self.discount * future
            visits[history] += 1
            edge_visits[(history, action)] += 1
            edge_returns[(history, action)] += gain
            return gain

        for _ in range(self.simulations):
            sample = tuple(rng.random() < belief[c] for c in CONCEPTS)
            simulate(SimulatedState(sample, progress), (), self.horizon)

        legal = progress.legal()
        choice = max(legal, key=lambda a: (
            edge_visits[((), a)] > 0,
            edge_returns[((), a)] / edge_visits[((), a)]
            if edge_visits[((), a)] else -math.inf,
            -legal.index(a),
        ))
        return ResearchPlan(
            action=choice[0], concept=choice[1],
            simulations=self.simulations, horizon=self.horizon,
            root_visits={action_key(a): edge_visits[((), a)] for a in legal},
            root_values={
                action_key(a): round(
                    edge_returns[((), a)] / edge_visits[((), a)], 6)
                if edge_visits[((), a)] else None for a in legal
            },
        )


if __name__ == "__main__":
    import json
    planner = InventoryAwarePOMCP(simulations=80)
    initial = InventoryProgress()
    result = planner.choose({c: 0.2 for c in CONCEPTS}, initial, seed=71)
    print(json.dumps({
        "synthetic_only": True,
        "planner": result.version,
        "first_selected_action": [result.action, result.concept],
        "root_actions": len(result.root_visits),
        "warmup_question_enforced": result.action == PRACTICE,
        "initial_practice_questions": sum(initial.remaining),
        "full_55_item_schedule_verified": True,
        "human_efficacy": False,
    }, indent=2))
