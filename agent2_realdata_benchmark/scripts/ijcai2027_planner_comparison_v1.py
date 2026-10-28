"""Reproducible synthetic first-decision planner benchmark (IJCAI 2027).

NOT a participant study, calibrated learner model, or full-episode policy comparison.
Outputs belong outside the source repository by default.
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

from src.planning.exact_solver import solve_exact_pomdp
from src.planning.pomcp import solve_pomcp
from src.planning.pomdp import ACTIONS, ToySingleSkillPOMDP
from src.prototype.shadow_planner import _illustrative_model

BELIEFS = (0.10, 0.30, 0.60, 0.90)
HORIZONS = (1, 2, 3)
BUDGETS = (30, 100, 300, 1000)
SEEDS = (11, 29, 47, 71, 89, 107, 131, 149, 173, 191,
         211, 229, 251, 269, 293, 311, 337, 359, 379, 401)
TOL = 1e-9
FIELDS = (
    "scenario", "belief", "horizon", "policy", "budget", "seed",
    "exact_action", "chosen_action", "exact_value", "chosen_exact_q",
    "first_action_regret", "same_action", "optimal_equivalent",
    "assistance_offer", "runtime_ms",
)


def scenarios() -> dict[str, ToySingleSkillPOMDP]:
    base = _illustrative_model()
    return {
        "baseline": base,
        "high_cost": ToySingleSkillPOMDP(replace(
            base.params, hint_cost=0.35, scaffold_cost=0.40,
        )),
        "no_effect": ToySingleSkillPOMDP(replace(
            base.params, hint_increment=0.0, scaffold_increment=0.0,
        )),
        "zero_effect_zero_cost": ToySingleSkillPOMDP(replace(
            base.params, hint_increment=0.0, scaffold_increment=0.0,
            hint_cost=0.0, scaffold_cost=0.0,
        )),
    }


def exact_first_action_regret(exact, chosen: str) -> float:
    """Use the oracle Q*(belief, first_action), not POMCP's noisy estimate."""
    values = dict(exact.action_values)
    if chosen not in values:
        raise ValueError("Unknown chosen action")
    difference = exact.expected_return - values[chosen]
    if difference < -TOL:
        raise AssertionError("Oracle values are inconsistent")
    return max(0.0, difference)


def observation(exact, *, scenario, belief, horizon, policy,
                budget, seed, chosen, runtime_ms) -> dict:
    values = dict(exact.action_values)
    regret = exact_first_action_regret(exact, chosen)
    return dict(zip(FIELDS, (
        scenario, belief, horizon, policy, budget, seed,
        exact.first_action, chosen, exact.expected_return, values[chosen],
        regret, int(chosen == exact.first_action), int(regret <= TOL),
        int(chosen != "no_offer"), runtime_ms,
    )))


def generate_rows(*, seeds=SEEDS, budgets=BUDGETS) -> list[dict]:
    if not seeds or any(type(s) is not int for s in seeds):
        raise ValueError("Expected nonempty integer seeds")
    if len(seeds) != len(set(seeds)):
        raise ValueError("Seed identifiers must be distinct")
    if not budgets or any(type(b) is not int or b < len(ACTIONS)
                          or b > 20000 for b in budgets):
        raise ValueError("Invalid POMCP simulation budgets")

    rows = []
    for scenario_name, model in scenarios().items():
        for belief in BELIEFS:
            for horizon in HORIZONS:
                exact = solve_exact_pomdp(
                    model, belief=belief, horizon=horizon,
                )
                myopic = solve_exact_pomdp(
                    model, belief=belief, horizon=1,
                ).first_action

                for policy, action in (
                    ("fixed_no_offer", "no_offer"),
                    ("fixed_hint", "optional_hint"),
                    ("fixed_scaffold", "optional_scaffold"),
                    ("greedy_one_step", myopic),
                ):
                    rows.append(observation(
                        exact, scenario=scenario_name,
                        belief=belief, horizon=horizon, policy=policy,
                        budget=0, seed="", chosen=action, runtime_ms="",
                    ))

                for budget in budgets:
                    for seed in seeds:
                        start = perf_counter()
                        result = solve_pomcp(
                            model, belief=belief, horizon=horizon,
                            simulations=budget, seed=seed,
                        )
                        elapsed_ms = (perf_counter() - start) * 1000.0
                        rows.append(observation(
                            exact, scenario=scenario_name,
                            belief=belief, horizon=horizon,
                            policy="pomcp_style", budget=budget, seed=seed,
                            chosen=result.first_action, runtime_ms=elapsed_ms,
                        ))
    return rows


def _interval(values: list[float], *, seed: int = 2027,
              draws: int = 1000) -> tuple[float, float]:
    """Resample planner RNG seeds, conditional on the fixed state grid."""
    if len(values) < 2:
        return (values[0], values[0])
    rng = Random(seed)
    n = len(values)
    samples = sorted(
        mean(values[rng.randrange(n)] for _ in range(n))
        for _ in range(draws)
    )
    return samples[int(0.025 * draws)], samples[int(0.975 * draws)]


def summarize(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[(row["scenario"], row["policy"], row["budget"])].append(row)

    summary = []
    for (scenario, policy, budget), group in sorted(groups.items()):
        regrets = [r["first_action_regret"] for r in group]
        seed_interval = ("", "")
        if policy == "pomcp_style":
            grouped_seeds = defaultdict(list)
            for row in group:
                grouped_seeds[row["seed"]].append(row["first_action_regret"])
            seed_means = [mean(v) for _, v in sorted(grouped_seeds.items())]
            seed_interval = _interval(seed_means)
        runtimes = [r["runtime_ms"] for r in group if r["runtime_ms"] != ""]
        summary.append({
            "scenario": scenario, "policy": policy,
            "budget": budget, "n_decisions": len(group),
            "mean_first_action_regret": mean(regrets),
            "seed_bootstrap_regret_lo": seed_interval[0],
            "seed_bootstrap_regret_hi": seed_interval[1],
            "exact_action_agreement": mean(r["same_action"] for r in group),
            "optimal_equivalent_rate": mean(r["optimal_equivalent"] for r in group),
            "assistance_offer_rate": mean(r["assistance_offer"] for r in group),
            "mean_runtime_ms": mean(runtimes) if runtimes else "",
        })
    return summary


def save_outputs(output: Path, rows: list[dict], summary: list[dict],
                 *, seeds, budgets) -> None:
    # Refuse accidental overwrites. Generate outside the repository.
    output.mkdir(parents=True, exist_ok=False)
    for filename, data in (("decisions.csv", rows),
                           ("summary.csv", summary)):
        path = output / filename
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)

    metadata = {
        "version": "synthetic_first_action_v1",
        "status": "exploratory_uncalibrated",
        "python_version": sys.version.split()[0],
        "initial_beliefs": BELIEFS,
        "horizons": HORIZONS,
        "pomcp_budgets": budgets,
        "pomcp_seeds": seeds,
        "actions": ACTIONS,
        "model_parameters": {
            name: asdict(model.params)
            for name, model in scenarios().items()
        },
        "regret_definition": "Q*(b,a*) - Q*(b,chosen), with optimal later decisions",
        "limitations": [
            "Not a sequential rollout policy comparison",
            "Not a human-learning outcome estimate",
            "Synthetic effects and costs are assumptions",
            "BKT and POMDP observation parameters do not agree",
            "Current real browser action is concept_summary, not modelled here",
            "Bootstrap interval resamples planner RNG seeds, not students",
            "Wall-clock timing is hardware- and load-dependent",
        ],
    }
    (output / "manifest.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path,
                        help="New directory for CSV and manifest outputs")
    parser.add_argument("--quick", action="store_true",
                        help="Use only the first three seeds for a smoke run")
    args = parser.parse_args()
    seeds = SEEDS[:3] if args.quick else SEEDS
    rows = generate_rows(seeds=seeds)
    summary = summarize(rows)
    save_outputs(args.output, rows, summary, seeds=seeds, budgets=BUDGETS)
    print(f"Wrote {len(rows)} first-decision records to {args.output}")
    print("scenario                policy            budget    regret  optimal  offer")
    for r in summary:
        if r["policy"] in ("fixed_no_offer", "greedy_one_step") or (
            r["policy"] == "pomcp_style" and r["budget"] == max(BUDGETS)
        ):
            print(f"{r['scenario']:<23} {r['policy']:<18} "
                  f"{r['budget']:>5}  {r['mean_first_action_regret']:>8.5f}  "
                  f"{r['optimal_equivalent_rate']:>6.1%}  "
                  f"{r['assistance_offer_rate']:>5.1%}")


if __name__ == "__main__":
    main()
