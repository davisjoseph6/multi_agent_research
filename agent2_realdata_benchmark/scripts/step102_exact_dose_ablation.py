"""Step102 exactly-matched 55-question practice-only POMCP ablation.

Original Step100 episode environment copied verbatim except for registering
two NEW policy names and requiring they offer zero resources. Run parity
tests against frozen Step100 before interpreting this exploratory result.
No real learners, no heldout access, no RCT mutation.

See docs/step102_exact_dose_ablation_PLAN.md.
"""
from __future__ import annotations

from hashlib import sha256
import argparse
import json
from pathlib import Path
from statistics import mean

from scripts import step100_inventory_policy_comparison as frozen
from scripts.step100_inventory_policy_comparison import (
    BKT, CONCEPTS, GenerativeAssumptions, HELDOUT_START, HORIZON,
    InventoryProgress, MAX_ACTIONS, OBSERVABLE, POLICIES, POST_ITEMS_PER_CONCEPT,
    PRACTICE, SCENARIOS, SCENARIO_PARAMETERS, SEED_START, SIMULATIONS,
    uniform,
)
from src.prototype.step99_inventory_aware_pomcp import InventoryAwarePOMCP
from src.prototype.study_v3_pomcp import EightConceptPOMCP

NO_RESOURCE_POLICIES = ("step99_practice_only", "v3_practice_only")
ALLOWED_POLICIES = POLICIES + NO_RESOURCE_POLICIES
FULL_COUNT = 30


def policy_action(policy: str, belief: dict[str, float],
                  progress: InventoryProgress, *,
                  sim_count: int, seed: int, scenario: str,
                  step: int) -> tuple[str, str]:
    """Match 55 QUESTION exposures; never call recovery on a new study arm."""
    if policy not in NO_RESOURCE_POLICIES:
        return frozen.policy_action(
            policy, belief, progress, sim_count=sim_count,
            seed=seed, scenario=scenario, step=step,
        )
    legal = progress.legal()
    active = tuple(c for c in CONCEPTS if (PRACTICE, c) in legal)
    if not active:
        raise ValueError("No practice items available")
    if progress.answered_in_session == 0:
        return PRACTICE, min(active, key=lambda c: (belief[c], CONCEPTS.index(c)))
    chooser_seed = frozen.planner_seed("Step100", scenario, seed, step)
    if policy == "v3_practice_only":
        planner = EightConceptPOMCP(horizon=HORIZON, simulations=sim_count)
        choice = planner.choose(
            belief, practice_concepts=active, resources_left=0,
            resource_actions=(), seed=chooser_seed,
        )
    else:
        planner = InventoryAwarePOMCP(horizon=HORIZON, simulations=sim_count)
        # Planner's future action budget is zero throughout; the executed
        # external progress can retain unused resource slots, but neither
        # policy can spend them. All 55 practice opportunities are equal.
        no_resource_progress = InventoryProgress(
            progress.remaining, progress.session,
            progress.answered_in_session, 0,
        )
        choice = planner.choose(belief, no_resource_progress, seed=chooser_seed)
    selected = (choice.action, choice.concept)
    if selected not in legal or choice.action != PRACTICE:
        raise AssertionError("A practice-only controller selected assistance")
    return selected


def episode(policy: str, scenario: str, seed: int, *,
            simulations: int = SIMULATIONS) -> dict:
    """One full fictional learner; 55 practice questions + optional resources.

    The external environment is identical across policies within a scenario
    and learner seed, and is independent of each planner's internal simulator.
    A hidden latent mastery state is never supplied to the policy.
    """
    if policy not in ALLOWED_POLICIES or scenario not in SCENARIOS:
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
    if (policy in NO_RESOURCE_POLICIES or policy.endswith("_no_resource")) and resources:
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



def parity_check(*, simulations: int = 41) -> dict:
    """Check the cloned external evaluator exactly matches frozen Step100."""
    cases = [
        ("step99", "nominal", SEED_START),
        ("v3", "forgetting_shift", SEED_START + 1),
        ("greedy_no_resource", "half_learning", SEED_START + 2),
        ("balanced_fixed_no_resource", "noisy_observations", SEED_START + 3),
    ]
    for policy, scenario, seed in cases:
        actual = episode(policy, scenario, seed, simulations=simulations)
        expected = frozen.episode(policy, scenario, seed, simulations=simulations)
        if actual != expected:
            raise AssertionError(
                f"Simulator parity failure: {policy}/{scenario}/{seed}"
            )
    return {"frozen_step100_environment_parity": True,
            "number_of_parity_cases": len(cases)}


def experiment(*, quick: bool = False) -> dict:
    if type(quick) is not bool:
        raise ValueError("quick must be bool")
    parity = parity_check(simulations=41)
    count = 2 if quick else FULL_COUNT
    simulations = 48 if quick else SIMULATIONS
    rows = [
        episode(policy, scenario, seed, simulations=simulations)
        for scenario in SCENARIOS
        for seed in range(SEED_START, SEED_START + count)
        for policy in NO_RESOURCE_POLICIES
    ]
    contrast = {
        scenario: frozen.paired_contrast(
            rows, "step99_practice_only", "v3_practice_only", scenario
        )
        for scenario in SCENARIOS
    }
    means = {
        scenario: {
            policy: {
                "mean_posttest_accuracy": mean(
                    r["posttest_accuracy"] for r in rows
                    if r["scenario"] == scenario and r["policy"] == policy
                ),
                "mean_latent_mastery_diagnostic": mean(
                    r["final_latent_mastery_fraction"] for r in rows
                    if r["scenario"] == scenario and r["policy"] == policy
                ),
                "mean_resources": mean(
                    r["resource_actions"] for r in rows
                    if r["scenario"] == scenario and r["policy"] == policy
                ),
                "mean_nominal_action_cost": mean(
                    r["nominal_action_cost"] for r in rows
                    if r["scenario"] == scenario and r["policy"] == policy
                ),
            } for policy in NO_RESOURCE_POLICIES
        } for scenario in SCENARIOS
    }
    if any(r["practice_answers"] != 55 or r["resource_actions"] != 0
           or r["total_actions"] != 55 or r["nominal_action_cost"] != .055
           for r in rows):
        raise AssertionError("The matched-dose design was violated")
    return {
        "status": "DEVELOPMENT_ONLY_MATCHED_QUESTION_DOSE_NOT_CONFIRMATORY",
        "quick_smoke_only": quick,
        "human_participants": False,
        "human_recovery_effect_established": False,
        "algorithmic_novelty_established": False,
        "sealed_heldout_accessed": False,
        "frozen_step100_unchanged": True,
        "preexisting_step100_development_seeds_reused": True,
        "parity": parity,
        "manifest": {
            "scenarios": list(SCENARIOS),
            "policies": list(NO_RESOURCE_POLICIES),
            "seeds": list(range(SEED_START, SEED_START + count)),
            "planner_simulations": simulations,
            "horizon": HORIZON,
            "practice_questions_per_arm": 55,
            "additional_resource_actions_per_arm": 0,
            "posttest_questions_per_arm": 16,
        },
        "primary_paired_contrasts": contrast,
        "policy_means": means,
        "episodes": rows,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--out", required=True, type=Path)
    opts = p.parse_args()
    if opts.out.exists():
        raise FileExistsError("Refusing to replace existing evidence")
    result = experiment(quick=opts.quick)
    sources = (
        "scripts/step102_exact_dose_ablation.py",
        "scripts/step100_inventory_policy_comparison.py",
        "src/prototype/step99_inventory_aware_pomcp.py",
        "src/prototype/study_v3_pomcp.py",
        "docs/step102_exact_dose_ablation_PLAN.md",
    )
    result["source_sha256"] = {
        name: sha256(Path(name).read_bytes()).hexdigest() for name in sources
    }
    opts.out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("DEVELOPMENT-ONLY exactly matched practice exposures:", opts.out)
    print("Source evaluator parity:", result["parity"])
    for scenario in SCENARIOS:
        r = result["primary_paired_contrasts"][scenario]
        print(scenario, f"{r['mean_posttest_accuracy_difference']:+.6f}",
              r["descriptive_seed_bootstrap_95pct"])
    print("No interventions, real participants or heldout data accessed.")


if __name__ == "__main__":
    main()
