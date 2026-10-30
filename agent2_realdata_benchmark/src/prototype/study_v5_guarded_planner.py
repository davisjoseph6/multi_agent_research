"""Opt-in belief-support guard for V3's synthetic eight-concept POMCP.

The original V3 planner is unchanged, preserving counterexample tests.
This is a development policy, not a validated recovery intervention.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .study_v3_pomcp import (
    CONCEPTS, RECOVERY_ACTIONS, PRACTICE,
    EightConceptPOMCP, PlanResult,
)


@dataclass(frozen=True)
class GuardedPlanResult(PlanResult):
    policy_id: str = "pomcp_v5_positive_belief_support_guard_v1"
    guard_applied: bool = False
    raw_action: str = ""
    raw_concept: str = ""
    expected_mastery_gain: float = 0.0
    guard_reason: str = ""


class BeliefSupportGuardedPOMCP(EightConceptPOMCP):
    """Run V3 POMCP, then intercept only zero model-expected learning.

    When the original action has zero *belief-expected* acquisition and an
    available action has positive expected acquisition, choose the best
    immediate acquisition candidate with deterministic tie-breaking.

    This guard does not establish true-state drift, since beliefs can be wrong.
    It also changes the actual policy, and needs separate scientific evaluation.
    """

    policy_id = "pomcp_v5_positive_belief_support_guard_v1"

    def choose(
        self,
        belief: Mapping[str, float],
        *,
        practice_concepts: Sequence[str],
        resource_actions: Sequence[str] = RECOVERY_ACTIONS,
        resources_left: int = 2,
        seed: int = 71,
    ) -> GuardedPlanResult:
        raw = super().choose(
            belief,
            practice_concepts=practice_concepts,
            resource_actions=resource_actions,
            resources_left=resources_left,
            seed=seed,
        )
        allowed_concepts = tuple(c for c in CONCEPTS if c in practice_concepts)
        allowed_resources = tuple(a for a in RECOVERY_ACTIONS if a in resource_actions)
        legal = [(PRACTICE, c) for c in allowed_concepts]
        if resources_left:
            legal.extend((a, c) for c in allowed_concepts for a in allowed_resources)

        def gain(action: tuple[str, str]) -> float:
            kind, concept = action
            return (1.0 - belief[concept]) * self.assumptions.rate(kind) / len(CONCEPTS)

        raw_action = (raw.action, raw.concept)
        if raw_action not in legal:
            raise AssertionError("Raw planner selected illegal action")
        original_gain = gain(raw_action)
        largest_gain = max(gain(a) for a in legal)
        guarded = original_gain <= 0 and largest_gain > 0
        chosen = max(legal, key=gain) if guarded else raw_action
        why = (
            "V3 selected zero-belief-gain action; deterministic positive-gain fallback"
            if guarded else "No intervention; original V3 POMCP action retained"
        )
        return GuardedPlanResult(
            action=chosen[0],
            concept=chosen[1],
            root_visits=raw.root_visits,
            root_values=raw.root_values,
            simulations=raw.simulations,
            horizon=raw.horizon,
            assumption_hash=raw.assumption_hash,
            synthetic_only=True,
            policy_id=self.policy_id,
            guard_applied=guarded,
            raw_action=raw.action,
            raw_concept=raw.concept,
            expected_mastery_gain=gain(chosen),
            guard_reason=why,
        )
