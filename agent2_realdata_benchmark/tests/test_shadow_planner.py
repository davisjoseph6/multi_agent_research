"""Synthetic-only tests for the shadow recovery adapter."""

from dataclasses import FrozenInstanceError

import pytest

from src.prototype.belief import DemoBeliefTracker
from src.prototype.shadow_planner import (
    ShadowRecoveryDiagnostic,
    propose_shadow_recovery,
)


def evaluate(tracker, **kwargs):
    arguments = {
        "source_row": 0,
        "session_id": "synthetic-session",
        "simulated_permission_to_offer": True,
        "simulations": 300,
        "seed": 42,
    }
    arguments.update(kwargs)

    return propose_shadow_recovery(tracker, **arguments)


def test_incorrect_practice_triggers_recovery():
    tracker = DemoBeliefTracker()
    tracker.observe_practice(correct=False)

    before = tracker.mastery
    result = evaluate(tracker)

    assert type(result) is ShadowRecoveryDiagnostic
    assert result.detector_status == "flag"
    assert result.recovery_disposition == "proposed"

    assert result.predicted_correctness < 0.35

    assert result.allowed_actions == (
        "no_offer",
        "optional_hint",
        "optional_scaffold",
    )

    assert result.simulated_action in result.allowed_actions
    assert result.mode == "hypothetical_shadow_only"

    # Search must not change actual learner-state estimates.
    assert tracker.mastery == before


def test_correct_practice_does_not_trigger_recovery():
    tracker = DemoBeliefTracker()
    tracker.observe_practice(correct=True)

    result = evaluate(tracker)

    assert result.detector_status == "no_flag"
    assert result.recovery_disposition == "no_action"
    assert result.allowed_actions == ("no_offer",)
    assert result.simulated_action == "no_offer"


def test_simulated_permission_absent_blocks_assistance():
    tracker = DemoBeliefTracker()
    tracker.observe_practice(correct=False)

    result = evaluate(
        tracker,
        simulated_permission_to_offer=False,
    )

    assert result.detector_status == "flag"
    assert result.recovery_disposition == "blocked"
    assert result.allowed_actions == ("no_offer",)
    assert result.simulated_action == "no_offer"


def test_unavailable_resources_defer_assistance():
    tracker = DemoBeliefTracker()
    tracker.observe_practice(correct=False)

    result = evaluate(
        tracker,
        hint_available=False,
        scaffold_available=False,
    )

    assert result.recovery_disposition == "deferred"
    assert result.allowed_actions == ("no_offer",)


def test_single_available_resource_is_respected():
    tracker = DemoBeliefTracker()
    tracker.observe_practice(correct=False)

    result = evaluate(
        tracker,
        scaffold_available=False,
    )

    assert result.allowed_actions == (
        "no_offer",
        "optional_hint",
    )

    assert result.simulated_action != "optional_scaffold"


def test_repeated_shadow_decisions_are_deterministic():
    tracker = DemoBeliefTracker()
    tracker.observe_practice(correct=False)

    first = evaluate(tracker)
    second = evaluate(tracker)

    assert first == second


def test_mastery_not_confused_with_correctness_probability():
    tracker = DemoBeliefTracker()

    result = evaluate(tracker)

    assert result.mastery_belief == pytest.approx(0.2)
    assert result.predicted_correctness == pytest.approx(0.38)

    assert (
        result.mastery_belief
        != result.predicted_correctness
    )


@pytest.mark.parametrize(
    "field",
    [
        "simulated_permission_to_offer",
        "hint_available",
        "scaffold_available",
    ],
)
def test_rejects_nonboolean_feasibility(field):
    tracker = DemoBeliefTracker()

    with pytest.raises(TypeError):
        evaluate(tracker, **{field: 1})


def test_rejects_wrong_tracker_type():
    with pytest.raises(TypeError):
        evaluate(
            object(),
            source_row=0,
            session_id="synthetic-session",
        )


def test_diagnostic_is_immutable():
    result = evaluate(DemoBeliefTracker())

    with pytest.raises(FrozenInstanceError):
        result.simulated_action = "delivered"
