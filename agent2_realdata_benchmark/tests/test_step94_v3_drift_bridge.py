"""Controller-level counterexamples for V3 drift."""

from fractions import Fraction as F
import random

import pytest

from src.prototype.step94_v3_drift_bridge import (
    default_planner_drift_witness,
    exact_conditional_drift,
    true_deficit,
)

from src.prototype.study_v3_pomcp import (
    CONCEPTS,
    EightConceptPOMCP,
    GenerativeAssumptions,
    PlanningState,
)


def mostly_mastered_state(resources=2):
    return PlanningState(
        tuple(
            concept != "Nudge Theory"
            for concept in CONCEPTS
        ),
        resources,
    )


def test_deficit_is_exactly_one_eighth():
    assert true_deficit(
        mostly_mastered_state()
    ) == F(1, 8)


def test_v3_planner_can_choose_mastered_concept():
    witness = default_planner_drift_witness()

    assert witness["simulations"] == 240

    assert (
        witness["selected_concept"]
        != "Nudge Theory"
    )

    assert (
        witness["selected_concept_already_mastered"]
        is True
    )

    assert (
        witness["expected_one_step_deficit_change"]
        == "0"
    )

    assert witness[
        "strict_positive_uniform_drift_disproved_for_this_configuration"
    ] is True


def test_actual_transition_leaves_mastery_unchanged():
    witness = default_planner_drift_witness()

    planner = EightConceptPOMCP(
        simulations=240
    )

    state = mostly_mastered_state()

    action = (
        witness["selected_action"],
        witness["selected_concept"],
    )

    for seed in range(10):
        future, _, _ = planner._step(
            state,
            action,
            random.Random(seed),
        )

        assert future.mastered == state.mastered

        assert (
            true_deficit(future)
            == true_deficit(state)
        )


def test_weak_concept_has_negative_drift_if_targeted():
    assert exact_conditional_drift(
        mostly_mastered_state(),
        ("QUESTION", "Nudge Theory"),
    ) == -F(1, 160)


def test_zero_learning_rate_gives_zero_drift():
    assumptions = GenerativeAssumptions(
        learn_practice=0.0
    )

    assert exact_conditional_drift(
        mostly_mastered_state(),
        ("QUESTION", "Nudge Theory"),
        assumptions,
    ) == 0


def test_resource_budget_is_respected():
    with pytest.raises(
        ValueError,
        match="not executable",
    ):
        exact_conditional_drift(
            mostly_mastered_state(resources=0),
            ("WORKED_EXAMPLE", "Nudge Theory"),
        )


def test_one_simulation_has_no_visited_root_edges():
    planner = EightConceptPOMCP(
        simulations=1
    )

    belief = {
        c: (
            0.0 if c == "Nudge Theory"
            else 1.0
        )
        for c in CONCEPTS
    }

    result = planner.choose(
        belief,
        practice_concepts=CONCEPTS,
        resources_left=0,
        seed=71,
    )

    assert sum(
        result.root_visits.values()
    ) == 0

    assert result.concept != "Nudge Theory"
