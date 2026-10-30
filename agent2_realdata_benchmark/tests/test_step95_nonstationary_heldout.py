"""Development-only properties of the synthetic held-out benchmark."""

import pytest

from scripts.step95_nonstationary_heldout import (
    SCENARIOS, POLICIES, HELDOUT_START, DEV_START,
    choose_action, evaluate, run_episode, scenario, uniform, update_belief,
)
from src.prototype.study_v3_pomcp import CONCEPTS, GenerativeAssumptions


def run(policy="v5", name="slow_forgetting", seed=100017):
    return run_episode(policy, scenario(name), seed, planner_simulations=3,
                       session_lengths=(3, 4))


def test_fixed_seed_is_reproducible():
    for policy in POLICIES:
        assert run(policy) == run(policy)


def test_paired_seeds_are_different_across_splits():
    development = evaluate("development", 2, 2, names=("stationary_nominal",), lengths=(2,))
    assert development["manifest"]["seed_start"] == DEV_START
    assert development["manifest"]["seed_end_inclusive"] < HELDOUT_START
    with pytest.raises(ValueError, match="locked"):
        evaluate("heldout", 2, 2, names=("stationary_nominal",), lengths=(2,))


def test_common_random_numbers_independent_of_policy():
    assert uniform(9876, 1, "Utility", "forget") == uniform(9876, 1, "Utility", "forget")
    assert uniform(9876, 1, "Utility", "forget") != uniform(9877, 1, "Utility", "forget")


def test_no_forgetting_events_in_stationary_model():
    for policy in POLICIES:
        assert run(policy, "stationary_nominal")["latent_forgetting_events"] == 0


def test_budget_is_bounded_for_every_policy():
    for policy in POLICIES:
        result = run(policy)
        assert 0 <= result["resource_actions"] <= 4
        assert result["steps"] == 7
        assert result["synthetic_only"] is True


def test_comparators_without_resources_never_consume_resources():
    assert run("fixed")["resource_actions"] == 0
    assert run("greedy")["resource_actions"] == 0


def test_policy_information_excludes_hidden_truth():
    # The action interface takes beliefs and budgets; it receives no latent state.
    assumptions = GenerativeAssumptions()
    belief = {c: 0.2 for c in CONCEPTS}
    for policy in POLICIES:
        first = choose_action(policy, belief, 2, 0, 71, 3, assumptions)
        second = choose_action(policy, dict(belief), 2, 0, 71, 3, assumptions)
        assert first == second


def test_report_contains_all_comparators_and_intervals():
    report = evaluate("development", 2, 3, names=("weak_learning",), lengths=(2, 2))
    assert set(report["results"]["weak_learning"]["policies"]) == set(POLICIES)
    assert set(report["results"]["weak_learning"]["paired_contrasts"]) == {
        "v5_minus_v3", "v5_minus_greedy", "v5_minus_fixed", "v5_minus_heuristic_recovery"
    }
    assert report["human_evidence"] is False
    assert report["synthetic"] is True


def test_manifest_and_report_are_reproducible():
    assert evaluate("development", 2, 3, names=("rapid_forgetting",), lengths=(2,)) == evaluate(
        "development", 2, 3, names=("rapid_forgetting",), lengths=(2,)
    )


def test_bayesian_observation_update():
    assert update_belief(.5, True, .1, .25) > .5
    assert update_belief(.5, False, .1, .25) < .5
    assert update_belief(0., True, .1, .25) == 0.


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_scenario_definitions_are_immutable(name):
    s = scenario(name)
    with pytest.raises(Exception):
        setattr(s, "forget", .77)


def test_invalid_configuration_rejected():
    with pytest.raises(ValueError):
        evaluate("test", 3, 2)
    with pytest.raises(ValueError):
        evaluate("development", 0, 2)
    with pytest.raises(ValueError):
        evaluate("development", 1, 0)
    with pytest.raises(ValueError):
        run_episode("imaginary", scenario("stationary_nominal"), 71)


def test_negative_results_not_suppressed():
    report = evaluate("development", 2, 2, names=("stationary_nominal",), lengths=(2,))
    compare = report["results"]["stationary_nominal"]["paired_contrasts"]["v5_minus_v3"]
    assert isinstance(compare["paired_mean_difference"], float)
    assert len(compare["descriptive_bootstrap_95pct_interval"]) == 2
