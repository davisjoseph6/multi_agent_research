"""Reproducible paired synthetic full-episode policy comparison.

Every policy observes only its posterior belief and past probe outcomes.
Latent mastery and environment shocks remain inaccessible to the policy.
All policies share the same exogenous three-shock draws in a paired episode.

SYNTHETIC ONLY: not a real learner model or human-study analysis.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from random import Random
from statistics import mean
from time import perf_counter

from scripts.ijcai2027_planner_comparison_v1 import (
    BELIEFS,
    scenarios,
)
from src.planning.exact_solver import solve_exact_pomdp
from src.planning.pomcp import solve_pomcp
from src.planning.pomdp import ACTIONS, ToySingleSkillPOMDP

POLICIES = (
    "fixed_no_offer",
    "fixed_hint",
    "fixed_scaffold",
    "greedy_one_step",
    "pomcp_style",
    "exact_belief_oracle",
)
HORIZONS = (1, 2, 3)
EPISODE_SEEDS = tuple(range(11001, 11101))
DISCOUNT = 0.95
POMCP_BUDGET = 300
FIELDS = (
    "scenario", "initial_belief", "horizon", "episode_seed", "policy",
    "budget", "discounted_return", "correct_probes", "n_offers",
    "assistance_uses", "offer_cost_total", "planning_runtime_ms",
    "actions", "observations",
)


def fixed_shock_step(
    model: ToySingleSkillPOMDP,
    *,
    mastered: bool,
    action: str,
    shocks: tuple[float, float, float],
) -> tuple[bool, bool, bool, float]:
    """Couple policies by three exogenous uniforms per time step.

    In distribution this is model.step(), but unlike its conditional RNG
    consumption, each decision uses predetermined uptake/learning/probe
    uniforms, including when an action does not use the uptake draw.
    """
    if type(model) is not ToySingleSkillPOMDP:
        raise TypeError("Expected toy model")
    if type(mastered) is not bool:
        raise TypeError("Mastery state must be boolean")
    if type(shocks) is not tuple or len(shocks) != 3:
        raise TypeError("Exactly three uniform shocks required")
    if any(type(u) not in (float, int) or not 0 <= u < 1 for u in shocks):
        raise ValueError("Uniform shocks must be finite in [0,1)")
    # Validates action using the canonical model.
    p_use = model.uptake_probability(action)
    u_use, u_learn, u_probe = shocks
    used = action != "no_offer" and u_use < p_use
    p_learn = model.params.baseline_learning
    if used:
        p_learn += (1 - p_learn) * model.learning_increment(action)
    next_mastered = mastered or u_learn < p_learn
    p_probe = (1 - model.params.slip) if next_mastered else model.params.guess
    correct = u_probe < p_probe
    reward = float(correct) - model.offer_cost(action)
    return next_mastered, used, correct, reward


def planning_seed(
    scenario: str, belief: float, horizon: int,
    episode_seed: int, step_index: int,
) -> int:
    """Stable, separate planner RNG stream: never consumes environment RNG."""
    label = (
        f"ijcai2027|{scenario}|{belief:.12f}|{horizon}|"
        f"{episode_seed}|{step_index}|pomcp"
    )
    return int.from_bytes(
        hashlib.sha256(label.encode("utf-8")).digest()[:8], "big"
    )


def select_action(
    model: ToySingleSkillPOMDP,
    *,
    scenario: str,
    policy: str,
    belief: float,
    remaining: int,
    episode_seed: int,
    horizon: int,
    step_index: int,
    budget: int,
) -> str:
    """Select from the belief only; no latent states or shocks accepted."""
    if policy not in POLICIES:
        raise ValueError("Unknown policy")
    if policy == "fixed_no_offer":
        return "no_offer"
    if policy == "fixed_hint":
        return "optional_hint"
    if policy == "fixed_scaffold":
        return "optional_scaffold"
    if policy == "greedy_one_step":
        return solve_exact_pomdp(model, belief=belief, horizon=1).first_action
    if policy == "exact_belief_oracle":
        return solve_exact_pomdp(
            model, belief=belief, horizon=remaining, discount=DISCOUNT
        ).first_action
    return solve_pomcp(
        model,
        belief=belief,
        horizon=remaining,
        discount=DISCOUNT,
        simulations=budget,
        seed=planning_seed(
            scenario, belief, horizon, episode_seed, step_index
        ),
    ).first_action


def simulate_episode(
    model: ToySingleSkillPOMDP,
    *,
    scenario: str,
    initial_belief: float,
    horizon: int,
    episode_seed: int,
    policy: str,
    budget: int = POMCP_BUDGET,
) -> dict:
    """Fully execute one policy with matched environment draws."""
    if type(horizon) is not int or not 1 <= horizon <= 3:
        raise ValueError("Horizon must be 1, 2 or 3")
    if type(episode_seed) is not int:
        raise TypeError("Episode seed must be integer")
    if type(budget) is not int or not 3 <= budget <= 20000:
        raise ValueError("Invalid POMCP simulation budget")
    model._validate_belief(initial_belief)
    env_rng = Random(episode_seed)
    mastered = env_rng.random() < initial_belief
    shocks_by_step = tuple(
        (env_rng.random(), env_rng.random(), env_rng.random())
        for _ in range(horizon)
    )
    posterior = initial_belief
    total_return = 0.0
    correct_count = 0
    offers = 0
    uses = 0
    total_cost = 0.0
    planning_ms = 0.0
    actions = []
    observations = []

    for t, shocks in enumerate(shocks_by_step):
        start = perf_counter()
        action = select_action(
            model, scenario=scenario, policy=policy,
            belief=posterior, remaining=horizon - t,
            episode_seed=episode_seed, horizon=horizon,
            step_index=t, budget=budget,
        )
        planning_ms += (perf_counter() - start) * 1000
        mastered, used, correct, reward = fixed_shock_step(
            model, mastered=mastered, action=action, shocks=shocks
        )
        total_return += (DISCOUNT ** t) * reward
        correct_count += int(correct)
        offers += int(action != "no_offer")
        uses += int(used)
        total_cost += model.offer_cost(action)
        actions.append(action)
        observations.append("1" if correct else "0")
        posterior = model.update_belief(posterior, action, correct)

    return dict(zip(FIELDS, (
        scenario, initial_belief, horizon, episode_seed, policy,
        budget if policy == "pomcp_style" else 0,
        total_return, correct_count, offers, uses, total_cost,
        planning_ms, ";".join(actions), "".join(observations),
    )))


def generate_rows(
    *,
    scenario_names: tuple[str, ...] = tuple(scenarios()),
    beliefs: tuple[float, ...] = BELIEFS,
    horizons: tuple[int, ...] = HORIZONS,
    episode_seeds: tuple[int, ...] = EPISODE_SEEDS,
    budget: int = POMCP_BUDGET,
) -> list[dict]:
    available = scenarios()
    if not scenario_names or len(set(scenario_names)) != len(scenario_names):
        raise ValueError("Need unique scenario names")
    if any(name not in available for name in scenario_names):
        raise ValueError("Unknown scenario")
    if not beliefs or any(type(b) not in (int, float) or not 0 <= b <= 1
                          for b in beliefs):
        raise ValueError("Invalid belief grid")
    if len(set(beliefs)) != len(beliefs):
        raise ValueError("Duplicate initial beliefs")
    if not horizons or any(type(h) is not int or h not in HORIZONS
                           for h in horizons):
        raise ValueError("Invalid horizons")
    if len(set(horizons)) != len(horizons):
        raise ValueError("Duplicate horizons")
    if not episode_seeds or any(type(s) is not int for s in episode_seeds):
        raise ValueError("Invalid episode seeds")
    if len(set(episode_seeds)) != len(episode_seeds):
        raise ValueError("Duplicate episode seeds")
    if type(budget) is not int or not 3 <= budget <= 20000:
        raise ValueError("Invalid budget")

    rows = []
    for scenario in scenario_names:
        model = available[scenario]
        for belief in beliefs:
            for horizon in horizons:
                for seed in episode_seeds:
                    for policy in POLICIES:
                        rows.append(simulate_episode(
                            model, scenario=scenario, initial_belief=belief,
                            horizon=horizon, episode_seed=seed,
                            policy=policy, budget=budget,
                        ))
    return rows


def bootstrap_interval(
    values: list[float], *, draws: int = 1000, seed: int = 2027,
) -> tuple[float, float]:
    """Bootstrap episode-seed clusters, conditional on chosen belief grid."""
    if not values:
        raise ValueError("At least one seed-cluster statistic required")
    if len(values) == 1:
        return values[0], values[0]
    rng = Random(seed)
    n = len(values)
    draws_values = sorted(
        mean(values[rng.randrange(n)] for _ in range(n))
        for _ in range(draws)
    )
    return draws_values[int(0.025 * draws)], draws_values[int(0.975 * draws)]


def summarize(rows: list[dict]) -> list[dict]:
    """Paired comparisons use exactly matched scenario/belief/H/seed rows."""
    index = {}
    groups = defaultdict(list)
    for row in rows:
        key = (
            row["scenario"], row["initial_belief"],
            row["horizon"], row["episode_seed"],
        )
        pair = (*key, row["policy"])
        if pair in index:
            raise ValueError("Duplicate policy episode")
        index[pair] = row
        groups[(row["scenario"], row["horizon"], row["policy"])].append(row)

    reports = []
    for (scenario, horizon, policy), group in sorted(groups.items()):
        deltas_no = defaultdict(list)
        deltas_exact = defaultdict(list)
        for row in group:
            key = (
                row["scenario"], row["initial_belief"],
                row["horizon"], row["episode_seed"],
            )
            baseline = index.get((*key, "fixed_no_offer"))
            oracle = index.get((*key, "exact_belief_oracle"))
            if baseline is None or oracle is None:
                raise ValueError("Missing matched baseline or exact-policy episode")
            seed = row["episode_seed"]
            deltas_no[seed].append(
                row["discounted_return"] - baseline["discounted_return"]
            )
            deltas_exact[seed].append(
                row["discounted_return"] - oracle["discounted_return"]
            )
        # Seed-cluster means, retaining the fixed belief grid within each seed.
        seed_no = [mean(deltas_no[k]) for k in sorted(deltas_no)]
        seed_exact = [mean(deltas_exact[k]) for k in sorted(deltas_exact)]
        lo_no, hi_no = bootstrap_interval(seed_no)
        lo_exact, hi_exact = bootstrap_interval(seed_exact)
        reports.append({
            "scenario": scenario,
            "horizon": horizon,
            "policy": policy,
            "budget": max(r["budget"] for r in group),
            "n_episodes": len(group),
            "mean_discounted_return": mean(r["discounted_return"] for r in group),
            "mean_correct_rate": mean(r["correct_probes"] / horizon for r in group),
            "mean_offers_per_episode": mean(r["n_offers"] for r in group),
            "mean_uptakes_per_episode": mean(r["assistance_uses"] for r in group),
            "mean_total_offer_cost": mean(r["offer_cost_total"] for r in group),
            "mean_planning_ms": mean(r["planning_runtime_ms"] for r in group),
            "paired_delta_vs_no_offer": mean(seed_no),
            "paired_vs_no_offer_ci_lo": lo_no,
            "paired_vs_no_offer_ci_hi": hi_no,
            "paired_delta_vs_exact": mean(seed_exact),
            "paired_vs_exact_ci_lo": lo_exact,
            "paired_vs_exact_ci_hi": hi_exact,
        })
    return reports


def save_outputs(
    output: Path, rows: list[dict], reports: list[dict],
    *, episode_seeds: tuple[int, ...], budget: int,
) -> None:
    """Refuse overwrite; all raw synthetic outputs stay outside the repo."""
    if not rows or not reports:
        raise ValueError("Refuse empty experimental output")
    output.mkdir(parents=True, exist_ok=False)
    for name, data in (("episodes.csv", rows), ("summary.csv", reports)):
        with (output / name).open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    metadata = {
        "version": "synthetic_sequential_policies_v1",
        "status": "exploratory_uncalibrated",
        "python_version": sys.version.split()[0],
        "policies": POLICIES,
        "actions": ACTIONS,
        "discount": DISCOUNT,
        "pomcp_budget": budget,
        "episode_seeds": episode_seeds,
        "initial_beliefs": sorted(set(r["initial_belief"] for r in rows)),
        "horizons": sorted(set(r["horizon"] for r in rows)),
        "scenarios": {n: asdict(m.params) for n, m in scenarios().items()},
        "randomness": (
            "All policies share initial-mastery, uptake, transition and "
            "probe uniforms for each matched scenario/belief/H/seed. "
            "Planner RNG uses independent SHA256-derived seeds."
        ),
        "intervals": (
            "Seed-cluster bootstrap of paired episode differences, "
            "conditional on synthetic dynamics and fixed belief grid; "
            "NOT a confidence interval for human learning."
        ),
        "limitations": [
            "Synthetic action/observation cycle is not real browser schedule",
            "POMCP planner is history-indexed MCTS, not persistent particle POMCP",
            "POMDP observation guess differs from browser BKT",
            "No concept_summary planning action",
            "Effects and uptake are hypothetical, not estimated",
            "Exact policy is optimal only under the assumed known model",
            "Paired Monte Carlo samples can favor a suboptimal policy by chance",
            "Do not use held-out test or real student data",
        ],
    }
    (output / "manifest.json").write_text(
        json.dumps(metadata, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--budget", type=int, default=POMCP_BUDGET)
    args = parser.parse_args()
    seeds = EPISODE_SEEDS[:5] if args.quick else EPISODE_SEEDS
    rows = generate_rows(episode_seeds=seeds, budget=args.budget)
    reports = summarize(rows)
    save_outputs(args.output, rows, reports,
                 episode_seeds=seeds, budget=args.budget)
    print(f"Wrote {len(rows)} paired policy episodes to {args.output}")
    print("scenario                  H policy                return   delta_no    CI_lo    CI_hi")
    for r in reports:
        if r["policy"] in (
            "fixed_no_offer", "greedy_one_step",
            "pomcp_style", "exact_belief_oracle",
        ):
            print(
                f"{r['scenario']:<25} {r['horizon']} "
                f"{r['policy']:<21} {r['mean_discounted_return']:>6.3f} "
                f"{r['paired_delta_vs_no_offer']:>10.3f} "
                f"{r['paired_vs_no_offer_ci_lo']:>8.3f} "
                f"{r['paired_vs_no_offer_ci_hi']:>8.3f}"
            )


if __name__ == "__main__":
    main()
