"""Check sequential scoring, history updates and student isolation."""

import math

import pytest

from scripts.fit_bkt import run_partition
from src.models.bkt import BKTParams


PARAMS = BKTParams(
    initial_mastery=0.2,
    learning=0.1,
    slip=0.1,
    guess=0.25,
)


def test_first_prediction_uses_prior():
    histories = [[
        (0, "student_A", [0], 1, True),
    ]]

    loss, predictions = run_partition(
        PARAMS, histories, 1, collect=True
    )

    assert len(predictions) == 1
    assert predictions[0][3] == pytest.approx(0.38)
    assert loss == pytest.approx(-math.log(0.38))


def test_scaffolding_updates_before_next_target():
    histories = [[
        # Earlier scaffolding: update state, do not score.
        (0, "student_A", [0], 1, False),

        # Current primary target: predict using updated state.
        (1, "student_A", [0], 0, True),
    ]]

    loss, predictions = run_partition(
        PARAMS, histories, 1, collect=True
    )

    posterior = (0.2 * 0.9) / 0.38
    updated = posterior + (1 - posterior) * 0.1
    expected_prediction = 0.25 + 0.65 * updated

    assert len(predictions) == 1
    assert predictions[0][3] == pytest.approx(
        expected_prediction
    )
    assert loss == pytest.approx(
        -math.log(1 - expected_prediction)
    )


def test_unknown_skill_does_not_update():
    histories = [[
        (0, "student_A", [], 0, False),
        (1, "student_A", [0], 1, True),
    ]]

    _, predictions = run_partition(
        PARAMS, histories, 1, collect=True
    )

    assert predictions[0][3] == pytest.approx(0.38)


def test_students_have_independent_initial_states():
    histories = [
        [(0, "student_A", [0], 1, True)],
        [(1, "student_B", [0], 0, True)],
    ]

    loss, predictions = run_partition(
        PARAMS, histories, 1, collect=True
    )

    assert predictions[0][3] == pytest.approx(0.38)
    assert predictions[1][3] == pytest.approx(0.38)

    expected = (
        -math.log(0.38)
        - math.log(1 - 0.38)
    ) / 2

    assert loss == pytest.approx(expected)
