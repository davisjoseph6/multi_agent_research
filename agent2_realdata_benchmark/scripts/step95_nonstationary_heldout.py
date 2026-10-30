"""Paired, synthetic nonstationary policy stress benchmark.

NOT a human study, not a validated learner model, not a novelty claim.
For defensible comparison, report all policies and all prespecified scenarios,
including negative findings. Policies never observe the true latent state.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
import random
from statistics import mean

from src.prototype.study_v3_pomcp import (
    CONCEPTS, PRACTICE, RECOVERY_ACTIONS, EightConceptPOMCP, GenerativeAssumptions,
)
from src.prototype.study_v5_guarded_planner import BeliefSupportGuardedPOMCP

POLICIES = ("fixed", "greedy", "heuristic_recovery", "v3", "v5")
SESSION_LENGTHS = (20, 20, 15)
# All scenarios are *hypothetical* and must remain fixed before examining results.
SCENARIOS = {
    "stationary_nominal": (0.00, 0.10, 1.0),
    "slow_forgetting": (0.02, 0.10, 1.0),
    "rapid_forgetting": (0.08, 0.10, 1.0),
    "noisy_slow_forgetting": (0.02, 0.25, 1.0),
    "weak_learning": (0.02, 0.10, 0.5),
}
DEV_START, HELDOUT_START = 100_000, 200_000


def uniform(seed: int, *parts: object) -> float:
    """Deterministic exogenous draw, independent of Python's hash randomization.

    Identical (seed,time,concept,event) streams for different policies.
    These are synthetic common random numbers, not measured events.
    """
    encoded = json.dumps((seed, *parts), separators=(",", ":")).encode()
    return int.from_bytes(sha256(encoded).digest()[:8], "big") / 2**64


@dataclass(frozen=True)
class Scenario:
    name: str
    forget: float
    slip: float
    scale: float
    guess: float = 0.25

    def __post_init__(self):
        if self.name not in SCENARIOS:
            raise ValueError("Unknown preregistered scenario")
        expected = SCENARIOS[self.name]
        if (self.forget, self.slip, self.scale) != expected or self.guess != 0.25:
            raise ValueError("Scenario must match the fixed evaluation manifest")


def scenario(name: str) -> Scenario:
    return Scenario(name, *SCENARIOS[name])


def choose_action(policy: str, belief: dict, budget: int, step: int,
                  seed: int, planner_simulations: int,
                  assumptions: GenerativeAssumptions):
    """Receive beliefs and budgets, never latent mastery or future answers."""
    if policy not in POLICIES or budget not in (0, 1, 2):
        raise ValueError("Invalid policy or resource budget")
    if policy == "fixed":
        return PRACTICE, CONCEPTS[step % len(CONCEPTS)]
    if policy == "greedy":
        target = max(CONCEPTS, key=lambda c: (1 - belief[c]) * assumptions.rate(PRACTICE))
        return PRACTICE, target
    if policy == "heuristic_recovery":
        target = min(CONCEPTS, key=lambda c: belief[c])
        if budget and belief[target] < .35:
            return "WORKED_EXAMPLE", target
        return PRACTICE, target
    # Planning conditions are intentionally matched between V3 and V5.
    klass = EightConceptPOMCP if policy == "v3" else BeliefSupportGuardedPOMCP
    planner = klass(horizon=3, simulations=planner_simulations, assumptions=assumptions)
    plan = planner.choose(
        belief, practice_concepts=CONCEPTS, resources_left=budget,
        seed=int(uniform(seed, step, "planner") * (2**31)),
    )
    return plan.action, plan.concept


def update_belief(prior: float, correct: bool, slip: float, guess: float) -> float:
    like_master = (1 - slip) if correct else slip
    like_unknown = guess if correct else (1 - guess)
    evidence = prior * like_master + (1 - prior) * like_unknown
    return prior if evidence == 0 else prior * like_master / evidence


def run_episode(policy: str, scenario_def: Scenario, seed: int,
                *, planner_simulations: int = 12,
                session_lengths: tuple[int, ...] = SESSION_LENGTHS) -> dict:
    if policy not in POLICIES or type(seed) is not int or type(planner_simulations) is not int or planner_simulations < 1:
        raise ValueError("Invalid benchmark configuration")
    if not session_lengths or any(type(n) is not int or n < 1 for n in session_lengths):
        raise ValueError("Invalid session lengths")
    assumptions = GenerativeAssumptions()
    latent = {c: uniform(seed, -1, c, "initial") < .25 for c in CONCEPTS}
    belief = {c: .25 for c in CONCEPTS}
    steps, resource_actions, cost, forgetting_events, observed = 0, 0, 0.0, 0, 0
    for session_index, session_length in enumerate(session_lengths):
        resources = 2
        for _ in range(session_length):
            action, target = choose_action(
                policy, belief, resources, steps, seed,
                planner_simulations, assumptions,
            )
            if action not in (PRACTICE, *RECOVERY_ACTIONS) or target not in CONCEPTS:
                raise AssertionError("Illegal action")
            if action != PRACTICE:
                if resources < 1:
                    raise AssertionError("Resource overspend")
                resources -= 1
                resource_actions += 1
            cost += assumptions.cost(action)
            # Observation occurs BEFORE the learning/forgetting transition.
            if action in (PRACTICE, "DROP_2"):
                p_correct = (1 - scenario_def.slip) if latent[target] else scenario_def.guess
                correct = uniform(seed, steps, target, "observation") < p_correct
                belief[target] = update_belief(
                    belief[target], correct, assumptions.slip, assumptions.guess,
                )
                observed += 1
            # The true environment may forget; all policies assume *no forgetting*.
            # Same exogenous draw for each concept/time/seed across policies.
            for concept in CONCEPTS:
                if latent[concept] and uniform(seed, steps, concept, "forget") < scenario_def.forget:
                    latent[concept] = False
                    forgetting_events += 1
            if not latent[target] and uniform(seed, steps, target, "learning", action) < min(1., assumptions.rate(action) * scenario_def.scale):
                latent[target] = True
            # Belief prediction under the original stationary (misspecified) model.
            belief[target] += (1 - belief[target]) * assumptions.rate(action)
            steps += 1
    mastery = sum(latent.values())
    return {
        "policy": policy, "scenario": scenario_def.name, "seed": seed,
        "steps": steps, "final_true_mastered": mastery,
        "final_true_mastery_fraction": mastery / len(CONCEPTS),
        "resource_actions": resource_actions,
        "nominal_action_cost": round(cost, 12),
        "nominal_net_mastery_fraction": round(mastery / len(CONCEPTS) - cost, 12),
        "latent_forgetting_events": forgetting_events,
        "observed_question_responses": observed,
        "synthetic_only": True,
    }


def bootstrap_interval(values: list[float], seed: int, iterations: int = 1000) -> tuple[float, float]:
    """Descriptive paired-seed bootstrap interval; not an efficacy claim."""
    if not values:
        raise ValueError("No paired differences")
    if len(values) == 1:
        return values[0], values[0]
    rng = random.Random(seed)
    n = len(values)
    samples = sorted(mean(values[rng.randrange(n)] for _ in range(n)) for _ in range(iterations))
    return samples[int(.025 * (iterations-1))], samples[int(.975 * (iterations-1))]


def evaluate(split: str, participants_per_scenario: int, simulations: int,
             *, frozen_protocol: bool = False, names: tuple[str, ...] = tuple(SCENARIOS),
             lengths: tuple[int, ...] = SESSION_LENGTHS) -> dict:
    if split == "heldout" and not frozen_protocol:
        raise ValueError("Held-out seeds are locked until the protocol is frozen and recorded")
    if split not in ("development", "heldout") or type(participants_per_scenario) is not int or not 1 <= participants_per_scenario <= 5000:
        raise ValueError("Invalid split/count")
    if type(simulations) is not int or simulations < 1:
        raise ValueError("Invalid simulation count")
    if not names or len(names) != len(set(names)) or any(n not in SCENARIOS for n in names):
        raise ValueError("Invalid scenario names")
    start = DEV_START if split == "development" else HELDOUT_START
    results = {}
    for name in names:
        conditions = scenario(name)
        per_policy = {p: [] for p in POLICIES}
        for seed in range(start, start + participants_per_scenario):
            for policy in POLICIES:
                per_policy[policy].append(run_episode(
                    policy, conditions, seed,
                    planner_simulations=simulations,
                    session_lengths=lengths,
                ))
        measures = {}
        for policy, records in per_policy.items():
            measures[policy] = {
                "mean_final_true_mastery_fraction": mean(r["final_true_mastery_fraction"] for r in records),
                "mean_nominal_net_mastery_fraction": mean(r["nominal_net_mastery_fraction"] for r in records),
                "mean_resource_actions": mean(r["resource_actions"] for r in records),
                "mean_forgetting_events": mean(r["latent_forgetting_events"] for r in records),
            }
        contrasts = {}
        for comparator in ("v3", "greedy", "fixed", "heuristic_recovery"):
            paired = [
                per_policy["v5"][i]["nominal_net_mastery_fraction"] -
                per_policy[comparator][i]["nominal_net_mastery_fraction"]
                for i in range(participants_per_scenario)
            ]
            lo, hi = bootstrap_interval(paired, seed=84531, iterations=1000)
            contrasts[f"v5_minus_{comparator}"] = {
                "paired_mean_difference": mean(paired),
                "descriptive_bootstrap_95pct_interval": [lo, hi],
                "n_paired_synthetic_seeds": participants_per_scenario,
            }
        results[name] = {"policies": measures, "paired_contrasts": contrasts}
    manifest = {
        "fixed_scenarios": {name: list(values) for name, values in SCENARIOS.items()},
        "policies": POLICIES, "session_lengths": lengths,
        "seed_start": start, "seed_end_inclusive": start + participants_per_scenario - 1,
        "split": split, "planner_simulations": simulations,
        "policy_information": "observations and beliefs; latent state inaccessible",
        "note": "Policy-specific learned states affect subsequent observations; same exogenous event keys are shared.",
    }
    return {
        "synthetic": True, "human_evidence": False,
        "research_status": "exploratory model stress test; no IJCAI novelty or efficacy established",
        "manifest_sha256": sha256(json.dumps(manifest, sort_keys=True, default=list).encode()).hexdigest(),
        "manifest": manifest, "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("development", "heldout"), default="development")
    parser.add_argument("--participants", type=int, default=5)
    parser.add_argument("--simulations", type=int, default=12)
    parser.add_argument("--scenario", choices=tuple(SCENARIOS), default=None)
    parser.add_argument("--frozen-protocol-acknowledged", action="store_true",
                        help="Run held-out seeds ONLY after committing the complete evaluation protocol")
    args = parser.parse_args()
    report = evaluate(args.split, args.participants, args.simulations,
                      frozen_protocol=args.frozen_protocol_acknowledged, names=(args.scenario,) if args.scenario else tuple(SCENARIOS))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
