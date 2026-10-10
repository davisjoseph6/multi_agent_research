"""Mathematical tests for local demonstration BKT state."""

from dataclasses import FrozenInstanceError

import pytest

from src.prototype.belief import (
    DemoBeliefTracker,
    PracticeBeliefEvent,
)


def test_initial_belief_and_prediction():
    tracker = DemoBeliefTracker()

    assert tracker.mastery == pytest.approx(0.2)
    assert tracker.predict_practice() == pytest.approx(0.38)


def test_correct_answer_updates_mastery():
    tracker = DemoBeliefTracker()

    event = tracker.observe_practice(correct=True)

    posterior = 0.2 * 0.9 / 0.38
    expected = posterior + (1 - posterior) * 0.1

    assert type(event) is PracticeBeliefEvent
    assert event.correct is True
    assert event.mastery_before == pytest.approx(0.2)
    assert event.pre_response_probability == pytest.approx(0.38)
    assert event.mastery_after == pytest.approx(expected)
    assert tracker.mastery == pytest.approx(expected)


def test_incorrect_answer_updates_mastery():
    tracker = DemoBeliefTracker()

    event = tracker.observe_practice(correct=False)

    posterior = 0.2 * 0.1 / (
        0.2 * 0.1 + 0.8 * 0.75
    )

    expected = posterior + (1 - posterior) * 0.1

    assert event.correct is False
    assert event.mastery_after == pytest.approx(expected)
    assert event.mastery_after < event.mastery_before


def test_repeated_observations_remain_probabilities():
    tracker = DemoBeliefTracker()

    for correct in (True, False, True, True, False):
        tracker.observe_practice(correct=correct)
        assert 0 <= tracker.mastery <= 1
        assert 0 <= tracker.predict_practice() <= 1


def test_trackers_are_independent():
    first = DemoBeliefTracker()
    second = DemoBeliefTracker()

    first.observe_practice(correct=True)

    assert first.mastery != second.mastery
    assert second.mastery == pytest.approx(0.2)


@pytest.mark.parametrize("value", [1, 0, None, "true"])
def test_rejects_non_boolean_observation(value):
    with pytest.raises(TypeError):
        DemoBeliefTracker().observe_practice(correct=value)


def test_belief_event_is_immutable():
    event = DemoBeliefTracker().observe_practice(
        correct=True
    )

    with pytest.raises(FrozenInstanceError):
        event.mastery_after = 1.0
