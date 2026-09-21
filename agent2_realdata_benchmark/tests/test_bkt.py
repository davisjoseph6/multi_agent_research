#!/usr/bin/env python3
"""Mathematical and interface tests for BKT."""

import numpy as np
import pytest

from src.models.bkt import BKT, BKTParams


def test_single_skill_prediction():
    model = BKT(
        num_concepts=1,
        params=BKTParams(
            initial_mastery=0.5,
            learning=0.1,
            slip=0.1,
            guess=0.25,
        ),
    )

    expected = 0.5 * 0.9 + 0.5 * 0.25

    assert model.predict([0]) == pytest.approx(expected)


def test_correct_response_update():
    model = BKT(
        1,
        BKTParams(
            initial_mastery=0.5,
            learning=0.1,
            slip=0.1,
            guess=0.25,
        ),
    )

    model.update([0], correct=1)

    posterior = 0.45 / 0.575
    expected = posterior + (1 - posterior) * 0.1

    assert model.mastery[0] == pytest.approx(expected)
    assert model.mastery[0] == pytest.approx(0.8043478261)


def test_incorrect_response_update():
    model = BKT(
        1,
        BKTParams(
            initial_mastery=0.5,
            learning=0.1,
            slip=0.1,
            guess=0.25,
        ),
    )

    model.update([0], correct=0)

    posterior = 0.05 / 0.425
    expected = posterior + (1 - posterior) * 0.1

    assert model.mastery[0] == pytest.approx(expected)
    assert model.mastery[0] == pytest.approx(0.2058823529)


def test_prediction_does_not_change_state():
    model = BKT(3)

    before = model.mastery
    model.predict([0, 2])

    np.testing.assert_array_equal(before, model.mastery)


def test_multiskill_prediction():
    params = BKTParams(
        initial_mastery=0.5,
        learning=0.0,
        slip=0.1,
        guess=0.25,
    )

    model = BKT(2, params)

    # P(all mastered) = 0.5 * 0.5 = 0.25
    expected = 0.25 + 0.65 * 0.25

    assert model.predict([0, 1]) == pytest.approx(0.4125)


def test_multiskill_correct_updates_simultaneously():
    params = BKTParams(
        initial_mastery=0.5,
        learning=0.0,
        slip=0.1,
        guess=0.25,
    )

    model = BKT(2, params)

    model.update([0, 1], correct=1)

    expected = (0.5 * 0.575) / 0.4125

    np.testing.assert_allclose(
        model.mastery,
        [expected, expected],
    )


def test_multiskill_incorrect_updates_simultaneously():
    params = BKTParams(
        initial_mastery=0.5,
        learning=0.0,
        slip=0.1,
        guess=0.25,
    )

    model = BKT(2, params)

    model.update([0, 1], correct=0)

    expected = (0.5 * 0.425) / 0.5875

    np.testing.assert_allclose(
        model.mastery,
        [expected, expected],
    )


def test_unknown_skills_do_not_change_mastery():
    model = BKT(3)
    before = model.mastery

    model.update([], correct=0)

    np.testing.assert_array_equal(
        before,
        model.mastery,
    )

    with pytest.raises(ValueError):
        model.predict([])


def test_reject_duplicate_skills():
    model = BKT(3)

    with pytest.raises(ValueError):
        model.predict([0, 0])


def test_reject_invalid_skill_index():
    model = BKT(3)

    with pytest.raises(ValueError):
        model.predict([3])


def test_reject_invalid_response():
    model = BKT(3)

    with pytest.raises(ValueError):
        model.update([0], correct=2)


def test_invalid_parameters():
    with pytest.raises(ValueError):
        BKTParams(slip=0.8, guess=0.3)


def test_state_is_not_externally_mutable():
    model = BKT(2)

    copy = model.mastery
    copy[0] = 0.99

    assert model.mastery[0] == pytest.approx(0.2)


def test_reset():
    model = BKT(2)

    model.update([0], correct=1)
    model.reset()

    np.testing.assert_allclose(
        model.mastery,
        [0.2, 0.2],
    )
