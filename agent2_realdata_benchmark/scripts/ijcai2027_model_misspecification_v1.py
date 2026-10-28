"""Paired synthetic full-episode evaluation under learner-model misspecification.

The planner model selects actions and performs Bayesian belief updates.
The distinct environment model generates latent transitions, uptake, responses
and realized utility. Neither true mastery nor the environment's hidden shocks
are given to the planner. An environment-informed exact reference is explicitly
an idealized diagnostic, NOT a fair deployable policy or true-state oracle.

Exploratory and uncalibrated; NOT real student learning evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import asdict, replace
from pathlib import Path
from random import Random
from statistics import mean
from time import perf_counter

from scripts.ijcai2027_planner_comparison_v1 import BELIEFS, scenarios
from scripts.ijcai2027_sequential_policies_v1 import (
    DISCOUNT,
    POMCP_BUDGET,
    bootstrap_interval,
    fixed_shock_step,
    select_action,
)
from src.planning.pomdp import ToySingleSkillPOMDP

POLICIES = (
    "fixed_no_offer",
    "fixed_hint",
    "fixed_scaffold",
    "greedy_one_step",
    "pomcp_style",
    "exact_belief_oracle",
    "environment_informed_exact",
)
HORIZONS = (1, 2, 3)
EPISODE_SEEDS = tuple(range(22001, 22061))
FIELDS = (
    "scenario", "planner_model", "environment_model", "initial_belief",
    "horizon", "episode_seed", "policy", "budget", "discounted_return",
    "correct_probes", "n_offers", "assistance_uses", "offer_cost_total",
    "planning_runtime_ms", "actions", "observations",
)


def model_pairs() -> dict[str, tuple[str, ToySingleSkillPOMDP, str, ToySingleSkillPOMDP]]:
    """Predeclared scenarios; do not select variants based on test results."""
    base = scenarios()["baseline"]
    costly = scenarios()["high_cost"]

    def make(original: ToySingleSkillPOMDP, **changes):
        return ToySingleSkillPOMDP(replace(original.params, **changes))

    return {
        "baseline_matched": ("baseline", base, "baseline", base),
        "baseline_effect_overestimated": (
            "baseline", base, "zero_effect", make(
                base, hint_increment=0.0, scaffold_increment=0.0,
            ),
        ),
        "high_cost_matched": ("high_cost", costly, "high_cost", costly),
        "high_cost_effect_overestimated": (
            "high_cost", costly, "zero_effect", make(
                costly, hint_increment=0.0, scaffold_increment=0.0,
            ),
        ),
        "high_cost_low_uptake": (
            "high_cost", costly, "low_uptake", make(
                costly, hint_uptake=0.2, scaffold_uptake=0.1,
            ),
        ),
        "high_cost_guess_shift": (
            "high_cost", costly, "guess_0.25", make(
                costly, guess=0.25,
            ),
        ),
        "high_cost_combined_adverse": (
            "high_cost", costly, "combined_adverse", make(
                costly, hint_increment=0.1, scaffold_increment=0.1,
                hint_uptake=0.2, scaffold_uptake=0.1, guess=0.25,
            ),
        ),
    }


def simulate_episode(
    planner: ToySingleSkillPOMDP,
    environment: ToySingleSkillPOMDP,
    *,
    scenario: str,
    planner_name: str,
    environment_name: str,
    initial_belief: float,
    horizon: int,
    episode_seed: int,
    policy: str,
    budget: int = POMCP_BUDGET,
) -> dict:
    """Execute one synthetic episode under a possibly wrong planner model.

    The idealized environment-informed reference uses the environment model
    for decisions AND Bayesian updating; other policies use the planner model.
    Every policy sees only its own posterior and realized probe correctness.
    """
    if type(planner) is not ToySingleSkillPOMDP or type(environment) is not ToySingleSkillPOMDP:
        raise TypeError("Expected two explicit toy models")
    if policy not in POLICIES:
        raise ValueError("Unknown policy")
    if type(horizon) is not int or horizon not in HORIZONS:
        raise ValueError("Invalid horizon")
    if type(episode_seed) is not int:
        raise TypeError("Episode seed must be integer")
    if type(budget) is not int or not 3 <= budget <= 20000:
        raise ValueError("Invalid POMCP budget")
    planner._validate_belief(initial_belief)
    if not scenario or not planner_name or not environment_name:
        raise ValueError("Scenario and model identifiers must be nonempty")

    env_rng = Random(episode_seed)
    mastered = env_rng.random() < initial_belief
    shocks = tuple(
        (env_rng.random(), env_rng.random(), env_rng.random())
        for _ in range(horizon)
    )
    belief = initial_belief
    total_return = 0.0
    offers = 0
    uses = 0
    correct_count = 0
    cost = 0.0
    planning_ms = 0.0
    actions = []
    observations = []
    reference = policy == "environment_informed_exact"
    decision_model = environment if reference else planner
    actual_policy = "exact_belief_oracle" if reference else policy

    for t, shock in enumerate(shocks):
        start = perf_counter()
        action = select_action(
            decision_model,
            scenario=planner_name,  # Keep planner RNG matched across scenario variants.
            policy=actual_policy,
            belief=belief,
            remaining=horizon-t,
            episode_seed=episode_seed,
            horizon=horizon,
            step_index=t,
            budget=budget,
        )
        planning_ms += (perf_counter() - start) * 1000.0
        mastered, used, correct, reward = fixed_shock_step(
            environment, mastered=mastered, action=action, shocks=shock,
        )
        total_return += (DISCOUNT ** t) * reward
        correct_count += int(correct)
        offers += int(action != "no_offer")
        uses += int(used)
        cost += environment.offer_cost(action)
        actions.append(action)
        observations.append("1" if correct else "0")
        # A misspecified policy must not borrow the environment's posterior.
        belief = decision_model.update_belief(belief, action, correct)

    return dict(zip(FIELDS, (
        scenario, planner_name, environment_name, initial_belief, horizon,
        episode_seed, policy, budget if policy == "pomcp_style" else 0,
        total_return, correct_count, offers, uses, cost, planning_ms,
        ";".join(actions), "".join(observations),
    )))


def generate_rows(
    *,
    scenario_names: tuple[str, ...] = tuple(model_pairs()),
    beliefs: tuple[float, ...] = BELIEFS,
    horizons: tuple[int, ...] = HORIZONS,
    episode_seeds: tuple[int, ...] = EPISODE_SEEDS,
    budget: int = POMCP_BUDGET,
) -> list[dict]:
    available = model_pairs()
    if not scenario_names or len(set(scenario_names)) != len(scenario_names):
        raise ValueError("Scenario names must be nonempty and unique")
    if any(s not in available for s in scenario_names):
        raise ValueError("Unknown scenario")
    if not beliefs or any(type(b) not in (int, float) or not 0 <= b <= 1 for b in beliefs):
        raise ValueError("Invalid initial beliefs")
    if len(set(beliefs)) != len(beliefs):
        raise ValueError("Duplicate beliefs")
    if not horizons or any(type(h) is not int or h not in HORIZONS for h in horizons):
        raise ValueError("Invalid horizons")
    if len(set(horizons)) != len(horizons):
        raise ValueError("Duplicate horizons")
    if not episode_seeds or any(type(s) is not int for s in episode_seeds):
        raise ValueError("Invalid episode seeds")
    if len(set(episode_seeds)) != len(episode_seeds):
        raise ValueError("Duplicate episode seeds")
    if type(budget) is not int or not 3 <= budget <= 20000:
        raise ValueError("Invalid POMCP budget")

    rows = []
    for scenario in scenario_names:
        plan_name, planner, env_name, environment = available[scenario]
        for belief in beliefs:
            for horizon in horizons:
                for seed in episode_seeds:
                    for policy in POLICIES:
                        rows.append(simulate_episode(
                            planner, environment, scenario=scenario,
                            planner_name=plan_name, environment_name=env_name,
                            initial_belief=belief, horizon=horizon,
                            episode_seed=seed, policy=policy, budget=budget,
                        ))
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    if not rows:
        raise ValueError("No episodes to summarize")
    episodes = {}
    groups = defaultdict(list)
    for row in rows:
        key = (
            row["scenario"], row["initial_belief"], row["horizon"],
            row["episode_seed"],
        )
        full_key = (*key, row["policy"])
        if full_key in episodes:
            raise ValueError("Duplicate policy episode")
        episodes[full_key] = row
        groups[(row["scenario"], row["horizon"], row["policy"])].append(row)

    summaries = []
    for (scenario, horizon, policy), group in sorted(groups.items()):
        differences_greedy = defaultdict(list)
        differences_no = defaultdict(list)
        differences_ref = defaultdict(list)
        for row in group:
            k = (
                row["scenario"], row["initial_belief"],
                row["horizon"], row["episode_seed"],
            )
            greedy = episodes.get((*k, "greedy_one_step"))
            no = episodes.get((*k, "fixed_no_offer"))
            ref = episodes.get((*k, "environment_informed_exact"))
            if greedy is None or no is None or ref is None:
                raise ValueError("Missing paired comparison policy")
            differences_greedy[row["episode_seed"]].append(
                row["discounted_return"]-greedy["discounted_return"]
            )
            differences_no[row["episode_seed"]].append(
                row["discounted_return"]-no["discounted_return"]
            )
            differences_ref[row["episode_seed"]].append(
                row["discounted_return"]-ref["discounted_return"]
            )

        def cluster_summary(clusters):
            vals = [mean(clusters[k]) for k in sorted(clusters)]
            lo, hi = bootstrap_interval(vals)
            return mean(vals), lo, hi

        d_greedy, greedy_lo, greedy_hi = cluster_summary(differences_greedy)
        d_no, no_lo, no_hi = cluster_summary(differences_no)
        d_ref, ref_lo, ref_hi = cluster_summary(differences_ref)
        summaries.append({
            "scenario": scenario, "horizon": horizon, "policy": policy,
            "n_episodes": len(group),
            "budget": max(r["budget"] for r in group),
            "mean_discounted_return": mean(r["discounted_return"] for r in group),
            "mean_correct_rate": mean(r["correct_probes"]/horizon for r in group),
            "mean_offers_per_episode": mean(r["n_offers"] for r in group),
            "mean_uses_per_episode": mean(r["assistance_uses"] for r in group),
            "mean_total_offer_cost": mean(r["offer_cost_total"] for r in group),
            "mean_planning_ms": mean(r["planning_runtime_ms"] for r in group),
            "delta_vs_greedy": d_greedy,
            "delta_vs_greedy_ci_lo": greedy_lo,
            "delta_vs_greedy_ci_hi": greedy_hi,
            "delta_vs_no_offer": d_no,
            "delta_vs_no_offer_ci_lo": no_lo,
            "delta_vs_no_offer_ci_hi": no_hi,
            "delta_vs_environment_reference": d_ref,
            "delta_vs_environment_reference_ci_lo": ref_lo,
            "delta_vs_environment_reference_ci_hi": ref_hi,
        })
    return summaries


def save_outputs(
    output: Path,
    rows: list[dict],
    summary: list[dict],
    *,
    episode_seeds: tuple[int, ...],
    budget: int,
) -> None:
    if not rows or not summary:
        raise ValueError("No data to save")
    output.mkdir(parents=True, exist_ok=False)
    for filename, data in (("episodes.csv", rows), ("summary.csv", summary)):
        with (output / filename).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    configuration = {
        "version": "synthetic_misspecification_v1",
        "status": "exploratory_uncalibrated",
        "python_version": sys.version.split()[0],
        "episode_seeds": episode_seeds,
        "belief_grid": sorted(set(r["initial_belief"] for r in rows)),
        "horizons": sorted(set(r["horizon"] for r in rows)),
        "policies": POLICIES,
        "pomcp_budget": budget,
        "discount": DISCOUNT,
        "model_pairs": {
            name: {
                "planner_name": p_name,
                "planner_params": asdict(planner.params),
                "environment_name": e_name,
                "environment_params": asdict(env.params),
            }
            for name, (p_name, planner, e_name, env) in model_pairs().items()
        },
        "randomness": (
            "Matched initial mastery and independent fixed uptake, transition and "
            "probe uniform shocks; separate POMCP planning RNG; identical planner "
            "RNG labels for variants sharing a planner model."
        ),
        "reference_policy": (
            "environment_informed_exact assumes knowledge of environment model "
            "parameters but NOT true mastery, hidden shocks or future outcomes. "
            "It is an idealized information-advantaged diagnostic, not a fair baseline."
        ),
        "uncertainty": (
            "Episode-seed-cluster bootstrap conditional on hypothetical synthetic "
            "models and chosen belief grid, not human learning uncertainty."
        ),
        "limitations": [
            "No calibrated learner or causal intervention model",
            "Synthetic independent probe after each action differs from browser schedule",
            "Action catalogue has hint/scaffold, not browser concept_summary",
            "Assistance use is sampled, not measured reading or learning",
            "Environment informed reference has extra model information",
            "Exact planning is optimal only for its own assumed dynamics",
            "Negative controls and scenario values are synthetic illustrative choices",
            "Held-out test gate remains closed; no participant records",
        ],
    }
    (output / "manifest.json").write_text(
        json.dumps(configuration, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--budget", type=int, default=POMCP_BUDGET)
    args = parser.parse_args()
    seeds = EPISODE_SEEDS[:3] if args.quick else EPISODE_SEEDS
    rows = generate_rows(episode_seeds=seeds, budget=args.budget)
    summary = summarize(rows)
    save_outputs(args.output, rows, summary, episode_seeds=seeds, budget=args.budget)
    print(f"Wrote {len(rows)} paired misspecification episodes to {args.output}")
    print("scenario                         H policy                   delta_greedy  CI_lo   CI_hi   offers")
    for r in summary:
        if r["horizon"] == 3 and r["policy"] in (
            "greedy_one_step", "pomcp_style", "exact_belief_oracle",
            "environment_informed_exact",
        ):
            print(
                f"{r['scenario']:<32} {r['horizon']} "
                f"{r['policy']:<24} {r['delta_vs_greedy']:>10.4f} "
                f"{r['delta_vs_greedy_ci_lo']:>7.4f} "
                f"{r['delta_vs_greedy_ci_hi']:>7.4f} "
                f"{r['mean_offers_per_episode']:>7.3f}"
            )


if __name__ == "__main__":
    main()
