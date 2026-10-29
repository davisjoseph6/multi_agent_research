"""Eight-concept POMCP-like history-tree planner for SYNTHETIC software studies.

This uses sampled 8-bit latent states, UCT over action-observation histories,
synthetic Bernoulli learning transitions and a limited resource budget. It is
NOT calibrated with educational data, does not establish a learning benefit,
and must not be represented as a validated treatment or proven recovery policy.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
import math
import random
from typing import Mapping, Sequence

from .study_v2 import CONCEPTS, RECOVERY_ACTIONS

PRACTICE = "QUESTION"
ACTIONS = (PRACTICE,) + RECOVERY_ACTIONS
OBSERVABLE = (PRACTICE, "DROP_2")


@dataclass(frozen=True)
class GenerativeAssumptions:
    """Hypotheses for software verification, NOT measured learning effects."""
    learn_practice: float = 0.05
    learn_summary: float = 0.10
    learn_drop2: float = 0.06
    learn_worked: float = 0.14
    learn_socratic: float = 0.09
    slip: float = 0.10
    guess: float = 0.25
    cost_practice: float = 0.001
    cost_summary: float = 0.006
    cost_drop2: float = 0.004
    cost_worked: float = 0.010
    cost_socratic: float = 0.007

    def __post_init__(self):
        for name, value in asdict(self).items():
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"invalid synthetic assumption {name}")

    @property
    def fingerprint(self) -> str:
        return sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()

    def rate(self, action: str) -> float:
        return {
            PRACTICE: self.learn_practice,
            "CONCEPT_SUMMARY": self.learn_summary,
            "DROP_2": self.learn_drop2,
            "WORKED_EXAMPLE": self.learn_worked,
            "SOCRATIC_HINT": self.learn_socratic,
        }[action]

    def cost(self, action: str) -> float:
        return {
            PRACTICE: self.cost_practice,
            "CONCEPT_SUMMARY": self.cost_summary,
            "DROP_2": self.cost_drop2,
            "WORKED_EXAMPLE": self.cost_worked,
            "SOCRATIC_HINT": self.cost_socratic,
        }[action]


@dataclass(frozen=True)
class PlanningState:
    mastered: tuple[bool, ...]
    resources_left: int

    def __post_init__(self):
        if len(self.mastered) != len(CONCEPTS) or not all(type(x) is bool for x in self.mastered):
            raise ValueError("expected eight Boolean synthetic latent states")
        if type(self.resources_left) is not int or self.resources_left < 0:
            raise ValueError("invalid resource budget")


@dataclass(frozen=True)
class PlanResult:
    action: str
    concept: str
    root_visits: dict[str, int]
    root_values: dict[str, float | None]
    simulations: int
    horizon: int
    assumption_hash: str
    synthetic_only: bool = True


def action_key(action: tuple[str, str]) -> str:
    return f"{action[0]}::{action[1]}"


class EightConceptPOMCP:
    """POMCP-style UCT action/observation history search with root sampling.

    The planner assumes independent binary concept mastery *at the root* and
    uses a fully specified synthetic transition model. It does not perform an
    empirical calibration, a clinical/safety validation, or a formal proof of
    convergence at any finite simulation budget.
    """

    def __init__(self, *, horizon: int = 3, simulations: int = 240,
                 exploration: float = 0.6, discount: float = 0.95,
                 assumptions: GenerativeAssumptions | None = None):
        if type(horizon) is not int or not 1 <= horizon <= 20:
            raise ValueError("horizon must be 1..20")
        if type(simulations) is not int or not 1 <= simulations <= 100000:
            raise ValueError("simulations must be 1..100000")
        if not math.isfinite(exploration) or exploration < 0:
            raise ValueError("exploration must be finite and nonnegative")
        if not math.isfinite(discount) or not 0 < discount <= 1:
            raise ValueError("discount must lie in (0,1]")
        self.horizon, self.simulations = horizon, simulations
        self.exploration, self.discount = exploration, discount
        self.assumptions = assumptions or GenerativeAssumptions()

    def _step(self, state: PlanningState, action: tuple[str, str],
              rng: random.Random) -> tuple[PlanningState, int | None, float]:
        name, concept = action
        idx = CONCEPTS.index(concept)
        old = state.mastered[idx]
        if name != PRACTICE and not state.resources_left:
            raise ValueError("synthetic resource budget exhausted")
        observation = None
        # The observation precedes the learning transition, as in the BKT
        # update convention used in study_v2.py.
        if name in OBSERVABLE:
            p_correct = (1-self.assumptions.slip) if old else self.assumptions.guess
            observation = int(rng.random() < p_correct)
        mastered = list(state.mastered)
        mastered[idx] = old or rng.random() < self.assumptions.rate(name)
        new_state = PlanningState(tuple(mastered), state.resources_left - (name != PRACTICE))
        reward = (int(mastered[idx]) - int(old)) / len(CONCEPTS) - self.assumptions.cost(name)
        return new_state, observation, reward

    @staticmethod
    def _validate_belief(belief: Mapping[str, float]):
        if set(belief) != set(CONCEPTS):
            raise ValueError("mastery belief must cover exactly eight concepts")
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1
               for v in belief.values()):
            raise ValueError("invalid mastery belief")

    def choose(self, belief: Mapping[str, float], *,
               practice_concepts: Sequence[str],
               resource_actions: Sequence[str] = RECOVERY_ACTIONS,
               resources_left: int = 2, seed: int = 71) -> PlanResult:
        self._validate_belief(belief)
        if type(resources_left) is not int or not 0 <= resources_left <= 10:
            raise ValueError("invalid resource budget")
        if type(seed) is not int:
            raise ValueError("seed must be an integer")
        if any(x not in CONCEPTS for x in practice_concepts) or not practice_concepts:
            raise ValueError("no available practice concepts")
        if len(set(practice_concepts)) != len(practice_concepts):
            raise ValueError("duplicate practice concepts")
        if any(a not in RECOVERY_ACTIONS for a in resource_actions) or len(set(resource_actions)) != len(resource_actions):
            raise ValueError("invalid recovery action list")
        ordered = tuple(c for c in CONCEPTS if c in practice_concepts)
        allowed_resources = tuple(a for a in RECOVERY_ACTIONS if a in resource_actions)
        practice_actions = tuple((PRACTICE, c) for c in ordered)
        resource_choices = tuple((a,c) for c in ordered for a in allowed_resources)
        rng = random.Random(seed)
        visits: Counter[tuple] = Counter()
        edge_visits: Counter[tuple] = Counter()
        edge_returns: Counter[tuple] = Counter()

        def legal(state: PlanningState) -> tuple[tuple[str, str], ...]:
            return practice_actions + (resource_choices if state.resources_left else ())

        def rollout(state: PlanningState, depth: int) -> float:
            value, weight = 0.0, 1.0
            while depth:
                # Evaluates an executable policy with the SAME action/budget constraints.
                a = rng.choice(legal(state))
                state, _, reward = self._step(state, a, rng)
                value += weight * reward
                weight *= self.discount
                depth -= 1
            return value

        def simulate(state: PlanningState, history: tuple, depth: int) -> float:
            if not depth:
                return 0.0
            available = legal(state)
            if not visits[history]:
                visits[history] += 1
                return rollout(state, depth)
            unexplored = [a for a in available if edge_visits[(history, a)] == 0]
            if unexplored:
                chosen = rng.choice(unexplored)
            else:
                chosen = max(available, key=lambda a: (
                    edge_returns[(history,a)] / edge_visits[(history,a)] +
                    self.exploration * math.sqrt(
                        math.log(visits[history] + 1) / edge_visits[(history,a)]),
                    -available.index(a),
                ))
            next_state, observation, immediate = self._step(state, chosen, rng)
            subtree = history + ((chosen, observation),)
            future = simulate(next_state, subtree, depth - 1)
            reward = immediate + self.discount * future
            visits[history] += 1
            edge_visits[(history, chosen)] += 1
            edge_returns[(history, chosen)] += reward
            return reward

        for _ in range(self.simulations):
            root = PlanningState(tuple(rng.random() < belief[c] for c in CONCEPTS), resources_left)
            simulate(root, (), self.horizon)
        available = legal(PlanningState((False,)*len(CONCEPTS),resources_left))
        chosen = max(available, key=lambda a: (
            edge_visits[((),a)] > 0,
            edge_returns[((),a)] / edge_visits[((),a)] if edge_visits[((),a)] else -math.inf,
            -available.index(a),
        ))
        return PlanResult(
            action=chosen[0], concept=chosen[1],
            root_visits={action_key(a):edge_visits[((),a)] for a in available},
            root_values={action_key(a): round(edge_returns[((),a)]/edge_visits[((),a)],6)
                         if edge_visits[((),a)] else None for a in available},
            simulations=self.simulations, horizon=self.horizon,
            assumption_hash=self.assumptions.fingerprint,
        )
