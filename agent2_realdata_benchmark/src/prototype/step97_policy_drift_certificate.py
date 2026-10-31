"""Exact, finite-state *research-only* drift certificate for action mixtures.

This module DOES NOT modify or validate the operational V3/V5/V6 controller.
The environment is an explicitly hypothetical binary-mastery model:
- one action targets exactly one of eight concepts each step;
- an unmastered target learns with the assumed action-specific probability;
- a mastered concept independently forgets with its supplied probability;
- other unmastered concepts cannot learn from that action;
- action randomization, if present, is independent of latent state
  conditional on the observable history.

All arithmetic is exact rational arithmetic on supplied decimal parameters.
The certificate is for the supplied conditional action DISTRIBUTION, not for
a single realized choice and not for real learner intervention effects.
"""
from __future__ import annotations

from fractions import Fraction
import math
from typing import Mapping

from .study_v3_pomcp import ACTIONS, CONCEPTS, PRACTICE, GenerativeAssumptions

N = len(CONCEPTS)


def probability(value: object) -> Fraction:
    if type(value) is bool or not isinstance(value, (int, float, str, Fraction)):
        raise ValueError("Expected rational-compatible probability")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Expected finite probability")
    try:
        result = Fraction(str(value)) if not isinstance(value, Fraction) else value
    except (ValueError, ZeroDivisionError, TypeError) as exc:
        raise ValueError("Invalid probability") from exc
    if not 0 <= result <= 1:
        raise ValueError("Probability must be within [0,1]")
    return result


def checked_distribution(weights: Mapping[tuple[str, str], object]) -> dict[tuple[str, str], Fraction]:
    if not isinstance(weights, Mapping) or not weights:
        raise ValueError("Nonempty action distribution required")
    parsed = {}
    for action, weight in weights.items():
        if (not isinstance(action, tuple) or len(action) != 2
                or action[0] not in ACTIONS or action[1] not in CONCEPTS):
            raise ValueError("Invalid action or concept")
        parsed[action] = probability(weight)
    if sum(parsed.values(), Fraction(0)) != 1:
        raise ValueError("Action weights must sum to exactly one")
    return parsed


def coverage_mixture(
    primary: tuple[str, str], exploration_probability: object
) -> dict[tuple[str, str], Fraction]:
    """Hypothetical full-concept randomized practice support, not a deployed policy.

    This mathematical construction requires a practice item to be available
    for EVERY concept at EVERY decision at which the guarantee is invoked.
    The finite 55-item quiz does not establish this condition.
    """
    if (not isinstance(primary, tuple) or len(primary) != 2
            or primary[0] not in ACTIONS or primary[1] not in CONCEPTS):
        raise ValueError("Invalid primary action")
    epsilon = probability(exploration_probability)
    weights = {primary: 1 - epsilon}
    for concept in CONCEPTS:
        action = (PRACTICE, concept)
        weights[action] = weights.get(action, Fraction(0)) + epsilon / N
    return checked_distribution(weights)


def expected_state_drift(
    mastered: tuple[bool, ...],
    effective_learning: tuple[Fraction, ...],
    forgetting: tuple[Fraction, ...],
) -> Fraction:
    """Exact E[D(next)-D(now) | true state, observable-history action mixture]."""
    if (len(mastered) != N or any(type(x) is not bool for x in mastered)
            or len(effective_learning) != N or len(forgetting) != N):
        raise ValueError("Expected eight Boolean mastery states and rates")
    for rate in effective_learning + forgetting:
        probability(rate)
    gained = sum((effective_learning[i] for i in range(N) if not mastered[i]),
                 Fraction(0))
    lost = sum((forgetting[i] for i in range(N) if mastered[i]),
               Fraction(0))
    return (lost - gained) / N


def certify_distribution(
    weights: Mapping[tuple[str, str], object],
    *, assumptions: GenerativeAssumptions | None = None,
    forgetting: Mapping[str, object] | None = None,
) -> dict:
    """Sharp worst-state expected drift over all 255 non-mastered latent states.

    This is a *statewise*, not Bayesian-average, result. For rate vector r,
    forgetting vector f and binary mastery state s:

        E[Delta D | s] = (sum_{i:s_i=1} f_i - sum_{i:s_i=0} r_i) / N.

    Over D(s)>0, the largest drift occurs with exactly one unmastered
    concept j minimizing f_j+r_j; the maximum is
        (sum_i f_i - min_j(f_j+r_j)) / N.

    Strict uniform negative drift holds iff for every j,
        r_j > sum_{i != j} f_i.

    The formula is confirmed by exhaustive enumeration (2^8 - 1 states).
    """
    distribution = checked_distribution(weights)
    model = assumptions or GenerativeAssumptions()
    if forgetting is None:
        forgetting_rates = (Fraction(0),) * N
    else:
        if not isinstance(forgetting, Mapping) or set(forgetting) != set(CONCEPTS):
            raise ValueError("Forgetting must specify all eight concepts")
        forgetting_rates = tuple(probability(forgetting[c]) for c in CONCEPTS)
    effective = tuple(
        sum((weight * probability(model.rate(kind))
             for (kind, concept), weight in distribution.items() if concept == c),
            Fraction(0))
        for c in CONCEPTS
    )
    total_forgetting = sum(forgetting_rates, Fraction(0))
    index = min(range(N), key=lambda j: forgetting_rates[j] + effective[j])
    worst_state = tuple(i != index for i in range(N))
    worst_drift = (total_forgetting - forgetting_rates[index] - effective[index]) / N

    enumerated = [
        expected_state_drift(tuple(bool(mask & (1 << i)) for i in range(N)),
                             effective, forgetting_rates)
        for mask in range((1 << N) - 1)  # excludes the all-mastered state
    ]
    if max(enumerated) != worst_drift:
        raise AssertionError("Exact enumeration disagrees with closed-form bound")

    strict = worst_drift < 0
    return {
        "scope": "HYPOTHETICAL_8_CONCEPT_SINGLE_TARGET_ACTION_DISTRIBUTION_ONLY",
        "real_human_validity": False,
        "deployed_v3_or_rct_policy_certified": False,
        "forgetting_model": "mastered->unmastered per concept; unmastered targeted->mastered",
        "conditional_independence": "actions randomized from observable history, not latent truth",
        "requires_all_specified_actions_always_feasible": True,
        "effective_learning_by_concept": {c: str(effective[i]) for i, c in enumerate(CONCEPTS)},
        "forgetting_by_concept": {c: str(forgetting_rates[i]) for i, c in enumerate(CONCEPTS)},
        "worst_case_latent_unmastered_concept": CONCEPTS[index],
        "worst_case_state_deficit": str(Fraction(1, N)),
        "worst_case_expected_drift": str(worst_drift),
        "strict_uniform_negative_drift": strict,
        "certified_uniform_margin": str(-worst_drift if strict else Fraction(0)),
        "exhaustively_checked_positive_deficit_states": len(enumerated),
        "action_weights": {f"{kind}::{concept}": str(weight)
                           for (kind, concept), weight in sorted(distribution.items())},
    }


def capped_drift_bound(initial_deficit: object, margin: object, steps: int) -> dict:
    """Standard additive-drift hitting-time bound, conditional on applicability.

    A strictly positive margin must hold at EVERY reachable pre-hitting state
    and time until the specified horizon, despite resource/item exhaustion.
    A finite cap does not imply recovery with probability 1.
    """
    deficit = probability(initial_deficit)
    delta = probability(margin)
    if delta <= 0 or type(steps) is not int or steps <= 0:
        raise ValueError("Positive drift margin and integer steps required")
    upper = min(Fraction(1), deficit / (delta * steps))
    return {"steps": steps, "upper_bound_probability_not_recovered": str(upper),
            "nontrivial": upper < 1,
            "conditions": "Uniform statewise stopped drift across all eligible pre-target decisions; not established for the 55-item protocol"}


if __name__ == "__main__":
    import json
    base = (PRACTICE, CONCEPTS[0])
    report = {
        "deterministic": certify_distribution({base: Fraction(1)}),
        "uniform_practice": certify_distribution(coverage_mixture(base, 1)),
        "ten_percent_exploration": certify_distribution(coverage_mixture(base, "0.1")),
    }
    print(json.dumps(report, indent=2))
