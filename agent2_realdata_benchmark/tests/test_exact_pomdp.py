"""Exact POMDP solver tests using synthetic assumptions only."""

from dataclasses import FrozenInstanceError, replace

import pytest

from src.planning.exact_solver import (
    ExactPlan,
    available_actions_from_plan,
    solve_exact_pomdp,
)
from src.planning.pomdp import (
    ToyPOMDPParameters,
    ToySingleSkillPOMDP,
)
from src.recovery.controller import RecoveryContext, plan_recovery
from src.uncertainty.bridge import signal_record
from src.uncertainty.event_detector import (
    TriggerConfig,
    detect_event,
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


def make_recovery_plan(
    *,
    probability=0.1,
    permission=True,
    hint=True,
    scaffold=True,
):
    signal = signal_record(
        source_row=12,
        student_id="synthetic-student",
        model="neuralcd_v1",
        supported=True,
        probability=probability,
    )

    decision = detect_event(
        signal,
        TriggerConfig(
            policy="risk_only",
            risk_threshold=0.7,
            entropy_threshold=0.8,
        ),
    )

    return plan_recovery(
        decision,
        context=RecoveryContext(
            permission_to_offer=permission,
            hint_available=hint,
            scaffold_available=scaffold,
        ),
    )


def test_exact_one_step_action_values(model):
    result = solve_exact_pomdp(
        model, belief=0.0, horizon=1
    )

    values = dict(result.action_values)

    assert values["no_offer"] == pytest.approx(0.27)
    assert values["optional_hint"] == pytest.approx(0.482)
    assert values["optional_scaffold"] == pytest.approx(0.3705)

    assert result.first_action == "optional_hint"
    assert result.expected_return == pytest.approx(0.482)


def test_exact_solver_accounts_for_future_observations(model):
    belief = 0.2
    discount = 0.9

    result = solve_exact_pomdp(
        model,
        belief=belief,
        horizon=2,
        discount=discount,
    )

    # Independently expand the two possible observations.
    for action, computed_q in result.action_values:
        predicted = model.predict_belief(belief, action)

        p_correct = (
            predicted * 0.9 + (1 - predicted) * 0.2
        )

        future_correct = solve_exact_pomdp(
            model,
            belief=model.update_belief(belief, action, True),
            horizon=1,
            discount=discount,
        ).expected_return

        future_incorrect = solve_exact_pomdp(
            model,
            belief=model.update_belief(belief, action, False),
            horizon=1,
            discount=discount,
        ).expected_return

        expected_q = (
            p_correct
            - model.offer_cost(action)
            + discount * (
                p_correct * future_correct
                + (1 - p_correct) * future_incorrect
            )
        )

        assert computed_q == pytest.approx(expected_q)

    assert result.expected_return == pytest.approx(
        max(value for _, value in result.action_values)
    )


def test_mastered_student_prefers_no_offer(model):
    result = solve_exact_pomdp(
        model, belief=1.0, horizon=1
    )

    assert result.first_action == "no_offer"
    assert result.expected_return == pytest.approx(0.9)


def test_no_offer_only_respects_feasibility(model):
    result = solve_exact_pomdp(
        model,
        belief=0.0,
        horizon=3,
        allowed_actions=("no_offer",),
    )

    assert result.first_action == "no_offer"
    assert len(result.action_values) == 1


def test_no_offer_two_step_value(model):
    result = solve_exact_pomdp(
        model,
        belief=1.0,
        horizon=2,
        discount=0.9,
        allowed_actions=("no_offer",),
    )

    assert result.expected_return == pytest.approx(
        0.9 + 0.9 * 0.9
    )


def test_deterministic_repeated_calls(model):
    first = solve_exact_pomdp(
        model, belief=0.25, horizon=3
    )

    second = solve_exact_pomdp(
        model, belief=0.25, horizon=3
    )

    assert first == second


def test_order_of_actions_does_not_change_ties(model):
    left = solve_exact_pomdp(
        model,
        belief=0.0,
        horizon=2,
        allowed_actions=(
            "optional_scaffold",
            "no_offer",
            "optional_hint",
        ),
    )

    right = solve_exact_pomdp(
        model,
        belief=0.0,
        horizon=2,
    )

    assert left == right


def test_permission_and_resources_restrict_actions():
    all_actions = available_actions_from_plan(
        make_recovery_plan()
    )

    hint_only = available_actions_from_plan(
        make_recovery_plan(scaffold=False)
    )

    blocked = available_actions_from_plan(
        make_recovery_plan(permission=False)
    )

    not_flagged = available_actions_from_plan(
        make_recovery_plan(probability=0.9)
    )

    assert all_actions == (
        "no_offer",
        "optional_hint",
        "optional_scaffold",
    )

    assert hint_only == (
        "no_offer",
        "optional_hint",
    )

    assert blocked == ("no_offer",)
    assert not_flagged == ("no_offer",)


def test_rejects_inconsistent_recovery_plan():
    altered = replace(
        make_recovery_plan(),
        detector_status="no_flag",
    )

    with pytest.raises(ValueError, match="Inconsistent"):
        available_actions_from_plan(altered)


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
        solve_exact_pomdp(
            model, belief=0.5, horizon=horizon
        )


@pytest.mark.parametrize(
    "discount,error",
    [
        (-0.1, ValueError),
        (1.1, ValueError),
        (float("nan"), ValueError),
        (float("inf"), ValueError),
        (True, TypeError),
        ("0.95", TypeError),
    ],
)
def test_invalid_discounts(model, discount, error):
    with pytest.raises(error):
        solve_exact_pomdp(
            model,
            belief=0.5,
            horizon=2,
            discount=discount,
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
def test_invalid_action_catalogues(model, actions, error):
    with pytest.raises(error):
        solve_exact_pomdp(
            model,
            belief=0.5,
            horizon=2,
            allowed_actions=actions,
        )


def test_perfect_observation_boundary():
    params = ToyPOMDPParameters(
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

    model = ToySingleSkillPOMDP(params)

    # Correct answers are impossible when mastery is zero.
    # The solver must skip that impossible observation.
    result = solve_exact_pomdp(
        model, belief=0.0, horizon=3
    )

    assert result.first_action == "no_offer"
    assert result.expected_return == 0.0


def test_exact_plan_is_immutable(model):
    result = solve_exact_pomdp(
        model, belief=0.3, horizon=1
    )

    assert type(result) is ExactPlan

    with pytest.raises(FrozenInstanceError):
        result.first_action = "unknown"
