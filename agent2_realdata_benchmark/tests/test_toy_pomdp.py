"""Synthetic tests for the single-skill POMDP model."""

from dataclasses import FrozenInstanceError, replace
from random import Random

import pytest

from src.planning.pomdp import (
    ACTIONS,
    ToyPOMDPParameters,
    ToySingleSkillPOMDP,
)


@pytest.fixture
def params():
    return ToyPOMDPParameters(
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


@pytest.fixture
def model(params):
    return ToySingleSkillPOMDP(params)


def test_action_catalogue():
    assert ACTIONS == (
        "no_offer",
        "optional_hint",
        "optional_scaffold",
    )


def test_learning_probabilities(model):
    assert model.expected_learning_probability(
        "no_offer"
    ) == pytest.approx(0.1)

    assert model.expected_learning_probability(
        "optional_hint"
    ) == pytest.approx(0.46)

    assert model.expected_learning_probability(
        "optional_scaffold"
    ) == pytest.approx(0.415)


def test_action_properties(model):
    assert model.uptake_probability("no_offer") == 0.0
    assert model.uptake_probability("optional_hint") == 0.8
    assert model.learning_increment("optional_scaffold") == 0.7
    assert model.offer_cost("no_offer") == 0.0
    assert model.offer_cost("optional_hint") == 0.04


def test_predicted_belief(model):
    # 0.2 + (1 - 0.2) * 0.46
    assert model.predict_belief(
        0.2, "optional_hint"
    ) == pytest.approx(0.568)


def test_bayesian_update_correct_and_incorrect(model):
    prior = model.predict_belief(
        0.2, "optional_hint"
    )

    correct = model.update_belief(
        0.2, "optional_hint", True
    )

    incorrect = model.update_belief(
        0.2, "optional_hint", False
    )

    expected_correct = (
        prior * 0.9
        / (prior * 0.9 + (1 - prior) * 0.2)
    )

    expected_incorrect = (
        prior * 0.1
        / (prior * 0.1 + (1 - prior) * 0.8)
    )

    assert correct == pytest.approx(expected_correct)
    assert incorrect == pytest.approx(expected_incorrect)
    assert correct > prior > incorrect


def test_no_offer_never_has_assistance_uptake(model):
    rng = Random(123)

    for _ in range(100):
        result = model.step(False, "no_offer", rng)
        assert result.assistance_used is False


def test_mastery_is_absorbing(model):
    rng = Random(456)

    for action in ACTIONS:
        for _ in range(100):
            result = model.step(True, action, rng)
            assert result.next_mastered is True


def test_deterministic_success_under_perfect_conditions(params):
    perfect = replace(
        params,
        baseline_learning=0.0,
        hint_increment=1.0,
        hint_uptake=1.0,
        slip=0.0,
        guess=0.0,
    )

    model = ToySingleSkillPOMDP(perfect)

    result = model.step(
        False, "optional_hint", Random(1)
    )

    assert result.assistance_used is True
    assert result.next_mastered is True
    assert result.probe_correct is True
    assert result.reward == pytest.approx(0.96)

    baseline = model.step(
        False, "no_offer", Random(1)
    )

    assert baseline.next_mastered is False
    assert baseline.probe_correct is False
    assert baseline.reward == 0.0


def test_offer_cost_applies_even_without_uptake(params):
    no_uptake = replace(
        params,
        baseline_learning=0.0,
        hint_uptake=0.0,
        slip=0.0,
        guess=0.0,
    )

    model = ToySingleSkillPOMDP(no_uptake)

    result = model.step(
        False, "optional_hint", Random(7)
    )

    assert result.assistance_used is False
    assert result.next_mastered is False
    assert result.probe_correct is False
    assert result.reward == pytest.approx(-0.04)


def test_reproducible_simulation(model):
    first_rng = Random(2027)
    second_rng = Random(2027)

    first = [
        model.step(False, "optional_hint", first_rng)
        for _ in range(100)
    ]

    second = [
        model.step(False, "optional_hint", second_rng)
        for _ in range(100)
    ]

    assert first == second


def test_simulation_matches_analytical_probabilities(model):
    rng = Random(2027)
    count = 30000

    outcomes = [
        model.step(False, "optional_hint", rng)
        for _ in range(count)
    ]

    uptake = sum(x.assistance_used for x in outcomes) / count
    mastery = sum(x.next_mastered for x in outcomes) / count
    correct = sum(x.probe_correct for x in outcomes) / count

    expected_mastery = 0.46
    expected_correct = (
        expected_mastery * 0.9
        + (1.0 - expected_mastery) * 0.2
    )

    assert uptake == pytest.approx(0.8, abs=0.015)
    assert mastery == pytest.approx(
        expected_mastery, abs=0.015
    )
    assert correct == pytest.approx(
        expected_correct, abs=0.015
    )


@pytest.mark.parametrize(
    "changes,error",
    [
        ({"baseline_learning": True}, TypeError),
        ({"baseline_learning": -0.1}, ValueError),
        ({"baseline_learning": 1.1}, ValueError),
        ({"hint_increment": float("nan")}, ValueError),
        ({"hint_uptake": float("inf")}, ValueError),
        ({"scaffold_cost": -0.1}, ValueError),
        ({"slip": 0.9, "guess": 0.2}, ValueError),
    ],
)
def test_invalid_parameters(params, changes, error):
    with pytest.raises(error):
        replace(params, **changes)


@pytest.mark.parametrize(
    "belief,error",
    [
        (True, TypeError),
        (float("nan"), ValueError),
        (float("inf"), ValueError),
        (-0.01, ValueError),
        (1.01, ValueError),
    ],
)
def test_invalid_beliefs(model, belief, error):
    with pytest.raises(error):
        model.predict_belief(belief, "no_offer")


def test_invalid_action_rejected(model):
    with pytest.raises(ValueError):
        model.expected_learning_probability("unknown")

    with pytest.raises(ValueError):
        model.predict_belief(0.5, "unknown")

    with pytest.raises(ValueError):
        model.step(False, "unknown", Random(1))


def test_invalid_observation_rejected(model):
    with pytest.raises(TypeError):
        model.update_belief(0.5, "no_offer", 1)


def test_invalid_generator_and_mastery_rejected(model):
    with pytest.raises(TypeError):
        model.step(False, "no_offer", None)

    with pytest.raises(TypeError):
        model.step(1, "no_offer", Random(1))


def test_impossible_observations_rejected(params):
    perfect = replace(
        params,
        baseline_learning=0.0,
        slip=0.0,
        guess=0.0,
    )

    model = ToySingleSkillPOMDP(perfect)

    with pytest.raises(ValueError, match="Impossible"):
        model.update_belief(0.0, "no_offer", True)

    with pytest.raises(ValueError, match="Impossible"):
        model.update_belief(1.0, "no_offer", False)


def test_records_are_immutable(params, model):
    with pytest.raises(FrozenInstanceError):
        params.slip = 0.5

    result = model.step(
        False, "no_offer", Random(1)
    )

    with pytest.raises(FrozenInstanceError):
        result.reward = 100.0
