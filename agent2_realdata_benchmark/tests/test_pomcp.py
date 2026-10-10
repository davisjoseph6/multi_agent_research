"""Synthetic tests for POMCP-style belief-space planning."""

from dataclasses import FrozenInstanceError

import pytest

from src.planning.exact_solver import solve_exact_pomdp
from src.planning.pomcp import MonteCarloPlan, solve_pomcp
from src.planning.pomdp import (
    ToyPOMDPParameters,
    ToySingleSkillPOMDP,
)


@pytest.fixture
def model():
    return ToySingleSkillPOMDP(
        ToyPOMDPParameters(
            baseline_learning=0.1,
            hint_increment=0.5,
            scaffold_increment=0.7,
            hint_uptake=0.8,
            scaffold_uptake=0.5,
            slip=0.1,
            guess=0.2,
            hint_cost=0.04,
            scaffold_cost=0.12,
        )
    )


def test_approximate_one_step_optimum(model):
    exact = solve_exact_pomdp(
        model, belief=0.2, horizon=1
    )

    approximate = solve_pomcp(
        model,
        belief=0.2,
        horizon=1,
        simulations=4000,
        seed=42,
    )

    assert approximate.first_action == exact.first_action
    assert approximate.first_action == "optional_hint"

    assert approximate.estimated_return == pytest.approx(
        exact.expected_return,
        abs=0.08,
    )


def test_longer_horizon_returns_valid_action(model):
    result = solve_pomcp(
        model,
        belief=0.2,
        horizon=3,
        simulations=3000,
        seed=42,
    )

    assert result.first_action in (
        "no_offer",
        "optional_hint",
        "optional_scaffold",
    )

    assert result.simulations == 3000

    assert sum(
        count for _, _, count in result.action_values
    ) == 3000


def test_all_root_actions_are_explored(model):
    result = solve_pomcp(
        model,
        belief=0.2,
        horizon=2,
        simulations=300,
    )

    assert len(result.action_values) == 3
    assert all(
        count > 0
        for _, _, count in result.action_values
    )


def test_deterministic_repeated_runs(model):
    kwargs = dict(
        belief=0.3,
        horizon=3,
        simulations=500,
        seed=2027,
    )

    first = solve_pomcp(model, **kwargs)
    second = solve_pomcp(model, **kwargs)

    assert first == second


def test_no_offer_only_policy(model):
    result = solve_pomcp(
        model,
        belief=0.2,
        horizon=3,
        simulations=500,
        allowed_actions=("no_offer",),
    )

    assert result.first_action == "no_offer"
    assert len(result.action_values) == 1


def test_disallowed_action_never_selected(model):
    result = solve_pomcp(
        model,
        belief=0.0,
        horizon=2,
        simulations=500,
        allowed_actions=(
            "no_offer",
            "optional_scaffold",
        ),
    )

    assert result.first_action != "optional_hint"
    assert "optional_hint" not in [
        action for action, _, _ in result.action_values
    ]


def test_deterministic_zero_reward_world():
    world = ToySingleSkillPOMDP(
        ToyPOMDPParameters(
            baseline_learning=0.0,
            hint_increment=0.0,
            scaffold_increment=0.0,
            hint_uptake=0.0,
            scaffold_uptake=0.0,
            slip=0.0,
            guess=0.0,
            hint_cost=0.1,
            scaffold_cost=0.2,
        )
    )

    result = solve_pomcp(
        world,
        belief=0.0,
        horizon=3,
        simulations=500,
    )

    assert result.first_action == "no_offer"

    # The exact optimal policy never offers assistance.
    exact = solve_exact_pomdp(
        world,
        belief=0.0,
        horizon=3,
    )

    assert exact.first_action == "no_offer"
    assert exact.expected_return == pytest.approx(0.0)

    # A finite-budget MCTS estimate includes exploratory
    # future actions that can incur unnecessary costs.
    # With no_offer selected at the root, only the next
    # two steps can incur assistance costs.
    worst_exploratory_return = (
        -0.2 * (0.95 + 0.95 ** 2)
    )

    assert (
        worst_exploratory_return - 1e-12
        <= result.estimated_return
        <= 0.0
    )

    # Restrict all planning steps to no_offer.
    # Every simulated reward must then equal zero.
    restricted = solve_pomcp(
        world,
        belief=0.0,
        horizon=3,
        simulations=500,
        allowed_actions=("no_offer",),
    )

    assert restricted.first_action == "no_offer"
    assert restricted.estimated_return == pytest.approx(0.0)


@pytest.mark.parametrize(
    "belief,error",
    [
        (-0.1, ValueError),
        (1.1, ValueError),
        (float("nan"), ValueError),
        (float("inf"), ValueError),
        (True, TypeError),
    ],
)
def test_invalid_beliefs(model, belief, error):
    with pytest.raises(error):
        solve_pomcp(
            model,
            belief=belief,
            horizon=1,
        )


@pytest.mark.parametrize(
    "horizon,error",
    [
        (0, ValueError),
        (6, ValueError),
        (True, TypeError),
        (1.5, TypeError),
    ],
)
def test_invalid_horizons(model, horizon, error):
    with pytest.raises(error):
        solve_pomcp(
            model,
            belief=0.5,
            horizon=horizon,
        )


@pytest.mark.parametrize(
    "simulations,error",
    [
        (0, ValueError),
        (2, ValueError),
        (20001, ValueError),
        (True, TypeError),
        (10.5, TypeError),
    ],
)
def test_invalid_simulation_budgets(
    model, simulations, error
):
    with pytest.raises(error):
        solve_pomcp(
            model,
            belief=0.5,
            horizon=1,
            simulations=simulations,
        )


@pytest.mark.parametrize(
    "actions,error",
    [
        (["no_offer"], TypeError),
        (("optional_hint",), ValueError),
        (("no_offer", "no_offer"), ValueError),
        (("no_offer", "unknown"), ValueError),
        (("no_offer", 2), TypeError),
    ],
)
def test_invalid_actions(model, actions, error):
    with pytest.raises(error):
        solve_pomcp(
            model,
            belief=0.5,
            horizon=1,
            allowed_actions=actions,
        )


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"discount": -0.1}, ValueError),
        ({"discount": 1.1}, ValueError),
        ({"discount": float("nan")}, ValueError),
        ({"exploration": -0.1}, ValueError),
        ({"exploration": float("inf")}, ValueError),
        ({"seed": True}, TypeError),
    ],
)
def test_invalid_planning_configuration(
    model, kwargs, error
):
    with pytest.raises(error):
        solve_pomcp(
            model,
            belief=0.5,
            horizon=1,
            **kwargs,
        )


def test_result_is_immutable(model):
    result = solve_pomcp(
        model,
        belief=0.2,
        horizon=1,
        simulations=20,
    )

    assert type(result) is MonteCarloPlan

    with pytest.raises(FrozenInstanceError):
        result.first_action = "unknown"
