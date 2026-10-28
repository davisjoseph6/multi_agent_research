"""Unit and negative-control tests for synthetic first-action benchmarking."""

import json

from src.planning.exact_solver import solve_exact_pomdp
from src.planning.pomdp import ACTIONS
from scripts.ijcai2027_planner_comparison_v1 import (
    BELIEFS, HORIZONS, TOL, _interval, exact_first_action_regret,
    generate_rows, save_outputs, scenarios, summarize,
)


def test_no_effect_makes_no_offer_optimal():
    model = scenarios()["no_effect"]
    for belief in BELIEFS:
        for horizon in HORIZONS:
            exact = solve_exact_pomdp(model, belief=belief, horizon=horizon)
            assert exact.first_action == "no_offer"
            assert exact_first_action_regret(exact, "no_offer") <= TOL
            for action in ACTIONS[1:]:
                assert exact_first_action_regret(exact, action) > 0


def test_zero_effect_and_zero_cost_make_all_actions_equivalent():
    model = scenarios()["zero_effect_zero_cost"]
    for belief in BELIEFS:
        for horizon in HORIZONS:
            exact = solve_exact_pomdp(model, belief=belief, horizon=horizon)
            for action in ACTIONS:
                assert exact_first_action_regret(exact, action) <= TOL


def test_grid_size_and_baselines():
    rows = generate_rows(seeds=(11,), budgets=(30,))
    assert len(rows) == 4 * len(BELIEFS) * len(HORIZONS) * (4 + 1)
    assert set(r["policy"] for r in rows) == {
        "fixed_no_offer", "fixed_hint", "fixed_scaffold",
        "greedy_one_step", "pomcp_style",
    }
    assert all(r["first_action_regret"] >= 0 for r in rows)
    no_effect = [r for r in rows if r["scenario"] == "no_effect"]
    assert all(r["chosen_action"] == "no_offer"
               for r in no_effect if r["policy"] in (
                   "fixed_no_offer", "greedy_one_step"))


def test_summarize_never_reports_negative_regret():
    rows = generate_rows(seeds=(11, 29), budgets=(30,))
    report = summarize(rows)
    assert all(r["mean_first_action_regret"] >= 0 for r in report)
    assert all(0 <= r["optimal_equivalent_rate"] <= 1 for r in report)
    no_effect = [r for r in report if r["scenario"] == "no_effect"
                 and r["policy"] == "fixed_no_offer"]
    assert len(no_effect) == 1
    assert no_effect[0]["mean_first_action_regret"] <= TOL


def test_myopic_is_exact_on_one_step_horizon():
    rows = generate_rows(seeds=(11,), budgets=(30,))
    for row in rows:
        if row["policy"] == "greedy_one_step" and row["horizon"] == 1:
            assert row["first_action_regret"] <= TOL
            assert row["optimal_equivalent"] == 1


def test_export_writes_manifest_and_rejects_overwrite(tmp_path):
    rows = generate_rows(seeds=(11,), budgets=(30,))
    report = summarize(rows)
    output = tmp_path / "new_results"
    save_outputs(output, rows, report, seeds=(11,), budgets=(30,))
    assert (output / "decisions.csv").exists()
    assert (output / "summary.csv").exists()
    metadata = json.loads((output / "manifest.json").read_text())
    assert metadata["status"] == "exploratory_uncalibrated"
    assert tuple(metadata["pomcp_seeds"]) == (11,)
    import pytest
    with pytest.raises(FileExistsError):
        save_outputs(output, rows, report, seeds=(11,), budgets=(30,))


def test_interval_is_deterministic():
    values = [0.0, 0.02, 0.05, 0.03]
    assert _interval(values) == _interval(values)
    lo, hi = _interval(values)
    assert 0 <= lo <= hi <= max(values)
