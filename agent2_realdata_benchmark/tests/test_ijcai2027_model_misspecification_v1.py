"""Negative controls and paired-design tests for model mismatch research."""
from collections import defaultdict
import json

import pytest

from scripts.ijcai2027_model_misspecification_v1 import (
    POLICIES, generate_rows, model_pairs, save_outputs,
    simulate_episode, summarize,
)
from scripts.ijcai2027_sequential_policies_v1 import simulate_episode as original_episode


def tiny(**overrides):
    options = dict(
        scenario_names=("high_cost_matched", "high_cost_effect_overestimated"),
        beliefs=(0.1, 0.6), horizons=(1, 2),
        episode_seeds=(11, 29), budget=30,
    )
    options.update(overrides)
    return generate_rows(**options)


def test_scenarios_are_explicit_and_have_distinct_models_when_required():
    pairs = model_pairs()
    assert len(pairs) == 7
    assert pairs["high_cost_matched"][1] is pairs["high_cost_matched"][3]
    assert pairs["high_cost_effect_overestimated"][1].params.hint_increment > 0
    assert pairs["high_cost_effect_overestimated"][3].params.hint_increment == 0
    assert pairs["high_cost_guess_shift"][1].params.guess == 0.2
    assert pairs["high_cost_guess_shift"][3].params.guess == 0.25


def test_complete_grid_has_every_policy_at_every_matched_episode():
    rows = tiny()
    assert len(rows) == 2 * 2 * 2 * 2 * len(POLICIES)
    grouped = defaultdict(set)
    for r in rows:
        key = (r["scenario"], r["initial_belief"], r["horizon"], r["episode_seed"])
        grouped[key].add(r["policy"])
    assert all(x == set(POLICIES) for x in grouped.values())


def test_matched_case_reproduces_existing_sequential_benchmark():
    pairs = model_pairs()
    _, planner, _, environment = pairs["high_cost_matched"]
    new = simulate_episode(
        planner, environment, scenario="high_cost_matched",
        planner_name="high_cost", environment_name="high_cost",
        initial_belief=0.3, horizon=3, episode_seed=11,
        policy="pomcp_style", budget=30,
    )
    old = original_episode(
        environment, scenario="high_cost", initial_belief=0.3,
        horizon=3, episode_seed=11, policy="pomcp_style", budget=30,
    )
    for k in (
        "discounted_return", "correct_probes", "n_offers", "assistance_uses",
        "offer_cost_total", "actions", "observations",
    ):
        assert new[k] == old[k]


def test_environment_effect_zero_does_not_affect_no_offer_path():
    a = tiny(scenario_names=("high_cost_matched",), horizons=(3,))
    b = tiny(scenario_names=("high_cost_effect_overestimated",), horizons=(3,))
    def relevant(rows):
        return {
            (r["initial_belief"], r["episode_seed"]): (r["discounted_return"], r["observations"])
            for r in rows if r["policy"] == "fixed_no_offer"
        }
    assert relevant(a) == relevant(b)


def test_environment_informed_reference_refuses_costly_no_effect_offers():
    rows = tiny(
        scenario_names=("high_cost_effect_overestimated",),
        horizons=(3,), beliefs=(0.1, 0.6, 0.9),
    )
    ref = [r for r in rows if r["policy"] == "environment_informed_exact"]
    assert all(r["n_offers"] == 0 for r in ref)
    assert all(r["actions"] == "no_offer;no_offer;no_offer" for r in ref)


def test_planner_belief_update_uses_planner_not_environment_model():
    _, planner, _, env = model_pairs()["high_cost_guess_shift"]
    b = 0.3
    assert planner.update_belief(b, "no_offer", True) != env.update_belief(
        b, "no_offer", True
    )
    kwargs = dict(
        scenario="high_cost_guess_shift", planner_name="high_cost",
        environment_name="guess_0.25", initial_belief=b, horizon=2,
        episode_seed=17, budget=30,
    )
    assert simulate_episode(planner, env, policy="greedy_one_step", **kwargs)[
        "policy"
    ] == "greedy_one_step"


def test_reproducibility_without_wall_clock_timings():
    x = tiny(scenario_names=("baseline_matched",), horizons=(2,), beliefs=(0.3,))
    y = tiny(scenario_names=("baseline_matched",), horizons=(2,), beliefs=(0.3,))
    for a, b in zip(x, y):
        for key in a:
            if key != "planning_runtime_ms":
                assert a[key] == b[key]


def test_paired_summary_greedy_is_exactly_zero_vs_itself():
    report = summarize(tiny())
    assert all(r["delta_vs_greedy"] == 0 for r in report if r["policy"] == "greedy_one_step")
    assert all(r["delta_vs_no_offer"] == 0 for r in report if r["policy"] == "fixed_no_offer")
    assert all(r["delta_vs_environment_reference"] == 0 for r in report
               if r["policy"] == "environment_informed_exact")


def test_reject_duplicate_and_missing_matched_rows():
    rows = tiny(scenario_names=("high_cost_matched",), horizons=(1,))
    with pytest.raises(ValueError, match="Duplicate"):
        summarize(rows + [rows[0]])
    with pytest.raises(ValueError, match="Missing paired"):
        summarize([r for r in rows if r["policy"] != "greedy_one_step"])


def test_reject_invalid_budgets_and_scenarios():
    with pytest.raises(ValueError, match="Unknown scenario"):
        tiny(scenario_names=("unknown",))
    with pytest.raises(ValueError, match="Duplicate episode"):
        tiny(episode_seeds=(11, 11))
    with pytest.raises(ValueError, match="Invalid POMCP"):
        tiny(budget=2)


def test_export_manifest_and_no_overwrite(tmp_path):
    rows = tiny(scenario_names=("high_cost_matched",), horizons=(1,))
    report = summarize(rows)
    target = tmp_path / "new_results"
    save_outputs(target, rows, report, episode_seeds=(11, 29), budget=30)
    data = json.loads((target / "manifest.json").read_text())
    assert data["status"] == "exploratory_uncalibrated"
    assert "environment_informed_exact" in data["policies"]
    assert (target / "episodes.csv").is_file()
    assert (target / "summary.csv").is_file()
    with pytest.raises(FileExistsError):
        save_outputs(target, rows, report, episode_seeds=(11, 29), budget=30)
