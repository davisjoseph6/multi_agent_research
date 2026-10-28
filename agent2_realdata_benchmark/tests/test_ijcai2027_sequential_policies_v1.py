"""Tests for paired full-episode synthetic planning comparison."""
from collections import defaultdict
import csv
import json

import pytest

from scripts.ijcai2027_sequential_policies_v1 import (
    DISCOUNT, POLICIES, bootstrap_interval, fixed_shock_step,
    generate_rows, planning_seed, save_outputs, scenarios,
    select_action, simulate_episode, summarize,
)


def test_environment_shocks_are_deterministic_and_separate():
    a = planning_seed("baseline", 0.3, 3, 11, 1)
    b = planning_seed("baseline", 0.3, 3, 11, 1)
    c = planning_seed("baseline", 0.3, 3, 11, 2)
    assert a == b and a != c
    model = scenarios()["baseline"]
    s = (0.1, 0.2, 0.3)
    assert fixed_shock_step(model, mastered=False, action="optional_hint", shocks=s) == (
        True, True, True, 1 - model.params.hint_cost,
    )


def test_no_assistance_does_not_consume_uptake_shock():
    model = scenarios()["baseline"]
    a = fixed_shock_step(model, mastered=False, action="no_offer", shocks=(0.0, 0.2, 0.9))
    b = fixed_shock_step(model, mastered=False, action="no_offer", shocks=(0.99, 0.2, 0.9))
    assert a == b
    assert a[1] is False


def test_horizon_one_greedy_is_oracle():
    for name, model in scenarios().items():
        for b in (0.1, 0.3, 0.9):
            kwargs = dict(
                scenario=name, belief=b, remaining=1, episode_seed=11,
                horizon=1, step_index=0, budget=30,
            )
            greedy = select_action(model, policy="greedy_one_step", **kwargs)
            oracle = select_action(model, policy="exact_belief_oracle", **kwargs)
            assert greedy == oracle


def test_no_effect_positive_cost_oracle_never_offers():
    model = scenarios()["no_effect"]
    for b in (0.1, 0.3, 0.9):
        for remaining in (1, 2, 3):
            choice = select_action(
                model, scenario="no_effect", policy="exact_belief_oracle",
                belief=b, remaining=remaining, episode_seed=11,
                horizon=3, step_index=3-remaining, budget=30,
            )
            assert choice == "no_offer"


def test_complete_paired_grid_and_matched_episode_count():
    rows = generate_rows(
        scenario_names=("baseline", "no_effect"),
        beliefs=(0.1, 0.6), horizons=(1, 2),
        episode_seeds=(11, 29), budget=30,
    )
    assert len(rows) == 2 * 2 * 2 * 2 * len(POLICIES)
    groups = defaultdict(set)
    for row in rows:
        key = (
            row["scenario"], row["initial_belief"],
            row["horizon"], row["episode_seed"],
        )
        groups[key].add(row["policy"])
    assert all(policies == set(POLICIES) for policies in groups.values())
    assert all(0 <= row["correct_probes"] <= row["horizon"] for row in rows)
    assert all(0 <= row["assistance_uses"] <= row["n_offers"] for row in rows)


def test_negative_control_zero_effect_zero_cost_is_pathwise_equal():
    rows = generate_rows(
        scenario_names=("zero_effect_zero_cost",), beliefs=(0.1, 0.9),
        horizons=(3,), episode_seeds=(11, 29, 47), budget=30,
    )
    groups = defaultdict(list)
    for row in rows:
        groups[(row["initial_belief"], row["episode_seed"])].append(row)
    for paired in groups.values():
        assert len(paired) == len(POLICIES)
        assert len({row["discounted_return"] for row in paired}) == 1
        assert len({row["observations"] for row in paired}) == 1
    report = summarize(rows)
    assert all(r["paired_delta_vs_no_offer"] == 0 for r in report)
    assert all(r["paired_delta_vs_exact"] == 0 for r in report)


def test_determinism_excluding_wall_clock():
    opts = dict(scenario_names=("baseline",), beliefs=(0.3,),
                horizons=(2,), episode_seeds=(11,), budget=30)
    one = generate_rows(**opts)
    two = generate_rows(**opts)
    for a, b in zip(one, two):
        for field in a:
            if field != "planning_runtime_ms":
                assert a[field] == b[field]


def test_summary_reports_paired_differences_and_counts():
    rows = generate_rows(
        scenario_names=("high_cost",), beliefs=(0.1, 0.6),
        horizons=(2,), episode_seeds=(11, 29), budget=30,
    )
    report = summarize(rows)
    assert len(report) == len(POLICIES)
    assert all(r["n_episodes"] == 4 for r in report)
    assert next(r for r in report if r["policy"] == "fixed_no_offer")[
        "paired_delta_vs_no_offer"
    ] == 0
    assert next(r for r in report if r["policy"] == "exact_belief_oracle")[
        "paired_delta_vs_exact"
    ] == 0


def test_reject_duplicate_episode_and_invalid_grid():
    opts = dict(scenario_names=("baseline",), beliefs=(0.3,),
                horizons=(1,), episode_seeds=(11,), budget=30)
    rows = generate_rows(**opts)
    with pytest.raises(ValueError, match="Duplicate"):
        summarize(rows + [rows[0]])
    with pytest.raises(ValueError, match="Duplicate"):
        generate_rows(**{**opts, "episode_seeds": (11, 11)})
    with pytest.raises(ValueError, match="Unknown scenario"):
        generate_rows(**{**opts, "scenario_names": ("unknown",)})
    with pytest.raises(ValueError, match="Invalid budget"):
        generate_rows(**{**opts, "budget": 1})


def test_exports_and_refuses_overwrite(tmp_path):
    opts = dict(scenario_names=("baseline",), beliefs=(0.3,),
                horizons=(1,), episode_seeds=(11,), budget=30)
    rows = generate_rows(**opts)
    report = summarize(rows)
    folder = tmp_path / "sequential_results"
    save_outputs(folder, rows, report, episode_seeds=(11,), budget=30)
    with (folder / "episodes.csv").open(newline="") as stream:
        assert len(list(csv.DictReader(stream))) == len(POLICIES)
    with (folder / "summary.csv").open(newline="") as stream:
        assert len(list(csv.DictReader(stream))) == len(POLICIES)
    meta = json.loads((folder / "manifest.json").read_text())
    assert meta["status"] == "exploratory_uncalibrated"
    with pytest.raises(FileExistsError):
        save_outputs(folder, rows, report, episode_seeds=(11,), budget=30)


def test_bootstrap_interval_is_deterministic():
    vals = [-0.2, 0.1, 0.4, 0.2]
    assert bootstrap_interval(vals) == bootstrap_interval(vals)
    lo, hi = bootstrap_interval(vals)
    assert min(vals) <= lo <= hi <= max(vals)
