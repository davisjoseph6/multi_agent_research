"""Step100: fixed development-only paired synthetic comparison (NO human data).

See docs/step100_inventory_policy_comparison_PLAN.md. This is NOT a
confirmatory study, and it cannot access the sealed Step95 seed range.
Original V3, Step99 and RCT implementations remain completely unchanged.

From agent2_realdata_benchmark:
python -m scripts.step100_inventory_policy_comparison --quick --out /tmp/ijcai_step100_quick.json
python -m scripts.step100_inventory_policy_comparison --out /tmp/ijcai_step100_full.json
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import random
from statistics import mean

from src.prototype.step99_inventory_aware_pomcp import (
    DRAFT_COUNTS, InventoryAwarePOMCP, InventoryProgress,
)
from src.prototype.study_v2 import BKT, CONCEPTS, RECOVERY_ACTIONS
from src.prototype.study_v3_pomcp import (
    EightConceptPOMCP, GenerativeAssumptions, OBSERVABLE, PRACTICE,
)

SEED_START = 150000
FULL_COUNT = 30
HELDOUT_START = 200000
SCENARIOS = ("nominal", "half_learning", "noisy_observations", "forgetting_shift")
POLICIES = ("step99", "v3", "greedy_no_resource", "balanced_fixed_no_resource")
SIMULATIONS = 240
HORIZON = 3
POST_ITEMS_PER_CONCEPT = 2
MAX_ACTIONS = 61  # 55 practice questions plus at most two resources/session
SCENARIO_PARAMETERS = {
    "nominal": (1.0, .10, .25, .0),
    "half_learning": (.5, .10, .25, .0),
    "noisy_observations": (1.0, .25, .35, .0),
    "forgetting_shift": (1.0, .10, .25, .005),
}
FIXED_SCHEDULE = tuple(
    concept for offset in range(max(DRAFT_COUNTS))
    for concept, count in zip(CONCEPTS, DRAFT_COUNTS) if offset < count
)
assert len(FIXED_SCHEDULE) == 55


def uniform(*keys: object) -> float:
    """Stable common exogenous randomness; no policy-specific key."""
    digest = sha256(json.dumps(keys, separators=(",", ":")).encode()).digest()
    return int.from_bytes(digest[:8], "big") / (1 << 64)


def planner_seed(*keys: object) -> int:
    return int.from_bytes(
        sha256(json.dumps(keys, separators=(",", ":")).encode()).digest()[:8],
        "big",
    )


def policy_action(policy: str, belief: dict[str, float],
                  progress: InventoryProgress, *,
                  sim_count: int, seed: int, scenario: str,
                  step: int) -> tuple[str, str]:
    """Policy sees only inferred belief and publicly observable inventory."""
    if policy not in POLICIES or progress.done:
        raise ValueError("Invalid policy or terminal state")
    legal = progress.legal()
    active = tuple(c for c in CONCEPTS if (PRACTICE, c) in legal)
    if not active:
        raise AssertionError("Nonterminal state without questions")

    # The original V3 online runtime always uses a GreedyPolicy QUESTION
    # warmup for arm A. This concept-only model cannot resolve item_id and
    # difficulty ties, so the common approximation is minimum BKT mastery.
    if policy == "balanced_fixed_no_resource":
        n_answered = 55 - sum(progress.remaining)
        return PRACTICE, FIXED_SCHEDULE[n_answered]
    if policy == "greedy_no_resource" or progress.answered_in_session == 0:
        return PRACTICE, min(active, key=lambda c: (belief[c], CONCEPTS.index(c)))

    key = planner_seed("Step100", scenario, seed, step)
    if policy == "v3":
        p = EightConceptPOMCP(horizon=HORIZON, simulations=sim_count)
        plan = p.choose(
            belief, practice_concepts=active,
            resource_actions=RECOVERY_ACTIONS if progress.resources_left else (),
            resources_left=progress.resources_left, seed=key,
        )
        selected = (plan.action, plan.concept)
    elif policy == "step99":
        p = InventoryAwarePOMCP(horizon=HORIZON, simulations=sim_count)
        plan = p.choose(belief, progress, seed=key)
        selected = (plan.action, plan.concept)
    else:
        raise AssertionError("Unreachable policy")
    if selected not in legal:
        raise AssertionError("Planner produced unavailable real action")
    return selected


def episode(policy: str, scenario: str, seed: int, *,
            simulations: int = SIMULATIONS) -> dict:
    """One full fictional learner; 55 practice questions + optional resources.

    The external environment is identical across policies within a scenario
    and learner seed, and is independent of each planner's internal simulator.
    A hidden latent mastery state is never supplied to the policy.
    """
    if policy not in POLICIES or scenario not in SCENARIOS:
        raise ValueError("Unknown policy or development scenario")
    if type(seed) is not int or not SEED_START <= seed < HELDOUT_START:
        raise ValueError("Only Step100 development learner seeds are allowed")
    if type(simulations) is not int or not 1 <= simulations <= 100000:
        raise ValueError("Invalid simulation count")

    learn_factor, slip, guess, forget = SCENARIO_PARAMETERS[scenario]
    model = GenerativeAssumptions()
    bkt = BKT()
    mastery = {c: uniform("step100", scenario, seed, "initial", c) < .2
               for c in CONCEPTS}
    belief = {c: .2 for c in CONCEPTS}

    # Pretest is observed but does not teach: 16 independent responses.
    for concept in CONCEPTS:
        for item in range(POST_ITEMS_PER_CONCEPT):
            p_correct = (1 - slip) if mastery[concept] else guess
            correct = uniform("step100", scenario, seed, "pretest",
                              concept, item) < p_correct
            belief[concept] = bkt.posterior(belief[concept], correct)

    progress = InventoryProgress()
    resources_by_kind: Counter[str] = Counter()
    n_practice = 0
    cost = 0.0
    action_step = 0
    while not progress.done:
        if action_step >= MAX_ACTIONS:
            raise AssertionError("Resource/practice budget exceeded")
        action, concept = policy_action(
            policy, belief, progress, sim_count=simulations, seed=seed,
            scenario=scenario, step=action_step,
        )
        # Enforce exactly the same finite protocol constraints for every arm.
        next_progress = progress.after((action, concept))
        if action in OBSERVABLE:
            p_correct = (1 - slip) if mastery[concept] else guess
            correct = uniform("step100", scenario, seed, action_step,
                              "response", concept) < p_correct
            belief[concept] = bkt.update(belief[concept], correct)

        if action == PRACTICE:
            n_practice += 1
        else:
            resources_by_kind[action] += 1
        cost += model.cost(action)
        if not mastery[concept]:
            learned = uniform("step100", scenario, seed, action_step,
                              "learn", concept) < model.rate(action) * learn_factor
            if learned:
                mastery[concept] = True
        if forget:
            for c in CONCEPTS:
                if mastery[c] and uniform("step100", scenario, seed, action_step,
                                          "forget", c) < forget:
                    mastery[c] = False
        progress = next_progress
        action_step += 1

    # Independent synthetic held-aside posttest observations are generated
    # only after all policies have completed their practice/recovery histories.
    posttest_correct = 0
    for concept in CONCEPTS:
        for item in range(POST_ITEMS_PER_CONCEPT):
            p_correct = (1 - slip) if mastery[concept] else guess
            posttest_correct += int(
                uniform("step100", scenario, seed, "posttest", concept, item)
                < p_correct
            )
    resources = sum(resources_by_kind.values())
    if (n_practice != 55 or resources > 6
            or action_step != 55 + resources
            or not 0 <= posttest_correct <= 16):
        raise AssertionError("Impossible experimental accounting")
    if policy.endswith("_no_resource") and resources:
        raise AssertionError("No-resource policy offered a recovery resource")
    return {
        "scenario": scenario, "seed": seed, "policy": policy,
        "synthetic_only": True, "practice_answers": n_practice,
        "resource_actions": resources,
        "resources_by_kind": dict(sorted(resources_by_kind.items())),
        "total_actions": action_step, "nominal_action_cost": round(cost, 8),
        "posttest_correct_of_16": posttest_correct,
        "posttest_accuracy": posttest_correct / 16,
        "final_latent_mastery_fraction": sum(mastery.values()) / len(CONCEPTS),
    }


def paired_contrast(rows: list[dict], first: str, second: str,
                    scenario: str) -> dict:
    lookup = {(row["policy"], row["seed"]): row for row in rows
              if row["scenario"] == scenario}
    seeds = sorted({seed for (policy, seed) in lookup if policy == first})
    if not seeds or any((second, seed) not in lookup for seed in seeds):
        raise ValueError("Missing paired development outputs")
    diffs = [
        lookup[first, seed]["posttest_accuracy"]
        - lookup[second, seed]["posttest_accuracy"] for seed in seeds
    ]
    rng = random.Random(planner_seed("step100-bootstrap", scenario, first, second))
    means = sorted(
        mean(rng.choice(diffs) for _ in range(len(diffs)))
        for _ in range(1000)
    )
    return {
        "contrast": f"{first}_minus_{second}",
        "paired_development_seeds": len(seeds),
        "mean_posttest_accuracy_difference": mean(diffs),
        "descriptive_seed_bootstrap_95pct": [
            means[24], means[975],
        ],
        "wins_ties_losses": [
            sum(x > 0 for x in diffs),
            sum(x == 0 for x in diffs),
            sum(x < 0 for x in diffs),
        ],
        "interpretation": "development-only fictional learners; not confirmatory",
    }


def experiment(*, quick: bool = False) -> dict:
    """Execute all registered policies and stress scenarios; no model search."""
    if type(quick) is not bool:
        raise ValueError("quick must be bool")
    n = 2 if quick else FULL_COUNT
    sims = 48 if quick else SIMULATIONS
    rows = [
        episode(policy, scenario, seed, simulations=sims)
        for scenario in SCENARIOS
        for seed in range(SEED_START, SEED_START + n)
        for policy in POLICIES
    ]
    contrasts = {
        scenario: {
            name: paired_contrast(rows, *policies, scenario)
            for name, policies in {
                "primary_step99_vs_v3": ("step99", "v3"),
                "exploratory_step99_vs_greedy": ("step99", "greedy_no_resource"),
                "exploratory_step99_vs_fixed": ("step99", "balanced_fixed_no_resource"),
            }.items()
        }
        for scenario in SCENARIOS
    }
    means = {
        scenario: {
            policy: {
                "mean_posttest_accuracy": mean(
                    row["posttest_accuracy"] for row in rows
                    if row["scenario"] == scenario and row["policy"] == policy
                ),
                "mean_latent_mastery_diagnostic": mean(
                    row["final_latent_mastery_fraction"] for row in rows
                    if row["scenario"] == scenario and row["policy"] == policy
                ),
                "mean_resource_actions": mean(
                    row["resource_actions"] for row in rows
                    if row["scenario"] == scenario and row["policy"] == policy
                ),
                "mean_nominal_cost": mean(
                    row["nominal_action_cost"] for row in rows
                    if row["scenario"] == scenario and row["policy"] == policy
                ),
            }
            for policy in POLICIES
        } for scenario in SCENARIOS
    }
    return {
        "status": "EXPLORATORY_DEVELOPMENT_ONLY; NO_STUDENT_EFFICACY",
        "quick_smoke_only": quick,
        "can_establish_ai_novelty": False,
        "human_participants": False,
        "heldout_data_accessed": False,
        "original_ijcai_rct_unchanged": True,
        "model_parameters": {
            "nominal_practice_learning": .05,
            "nominal_best_resource_learning": .14,
            "scenarios": {k: dict(zip(
                ("learning_multiplier", "slip", "guess", "forget_per_action"),
                SCENARIO_PARAMETERS[k])) for k in SCENARIOS},
        },
        "manifest": {
            "study": "step100_paired_finite_inventory_dev_v1",
            "seeds": list(range(SEED_START, SEED_START + n)),
            "planner_simulations": sims, "horizon": HORIZON,
            "practice_session_quotas": [20, 20, 15],
            "resource_slots_per_session": 2,
            "policies": list(POLICIES),
            "scenarios": list(SCENARIOS),
        },
        "policy_means": means, "contrasts": contrasts, "episodes": rows,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    if args.out.exists():
        raise FileExistsError("Refusing to overwrite prior development output")
    result = experiment(quick=args.quick)
    sources = (
        "scripts/step100_inventory_policy_comparison.py",
        "src/prototype/step99_inventory_aware_pomcp.py",
        "src/prototype/study_v3_pomcp.py",
        "src/prototype/study_v2.py",
        "docs/step100_inventory_policy_comparison_PLAN.md",
    )
    digests = {
        s: sha256(Path(s).read_bytes()).hexdigest() for s in sources
    }
    result["source_sha256"] = digests
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print("DEVELOPMENT-ONLY paired policy experiment written:", args.out)
    print("Quick smoke (not scientific comparison):", args.quick)
    for name in SCENARIOS:
        contrast = result["contrasts"][name]["primary_step99_vs_v3"]
        print(name, "Step99-V3:",
              f"{contrast['mean_posttest_accuracy_difference']:+.6f}",
              "descriptive CI:", contrast["descriptive_seed_bootstrap_95pct"])
    print("No student outcomes, sealed seeds, or RCT source modified.")


if __name__ == "__main__":
    main()
