"""Tests for independent V6 development-only evaluation."""
import pytest

from src.prototype.study_v3_pomcp import CONCEPTS
from src.prototype.step95_v6_decline_candidate import ObservationChangeController, POLICY_ID
from scripts.step95_v6_development import v6_episode, compare


def beliefs(value=.25):
    return {c: value for c in CONCEPTS}


def test_no_initial_deterioration_signal():
    c = ObservationChangeController()
    assert not any(c.signals.values())
    assert c.choose(beliefs(), 2).action == "QUESTION"


def test_initial_low_mastery_not_deterioration():
    c = ObservationChangeController()
    for _ in range(4):
        c.observe(CONCEPTS[0], False)
    assert not c.signals[CONCEPTS[0]]


def test_observed_correct_then_incorrect_can_trigger():
    c = ObservationChangeController()
    c.observe(CONCEPTS[0], True)
    c.observe(CONCEPTS[0], True)
    c.observe(CONCEPTS[0], False)
    assert not c.signals[CONCEPTS[0]]
    c.observe(CONCEPTS[0], False)
    assert c.signals[CONCEPTS[0]]
    assert c.signal_onsets == 1


def test_signal_can_trigger_costed_resource():
    c = ObservationChangeController()
    for value in (True, True, False, False):
        c.observe(CONCEPTS[0], value)
    choice = c.choose(beliefs(), 2)
    assert (choice.action, choice.concept, choice.signal) == ("WORKED_EXAMPLE", CONCEPTS[0], True)
    assert not c.signals[CONCEPTS[0]]


def test_no_resource_overspending():
    c = ObservationChangeController()
    for value in (True, True, False, False):
        c.observe(CONCEPTS[0], value)
    choice = c.choose(beliefs(), 0)
    assert choice.action == "QUESTION"
    assert c.signals[CONCEPTS[0]]


def test_observation_validation():
    c = ObservationChangeController()
    with pytest.raises(ValueError):
        c.observe(CONCEPTS[0], 1)
    with pytest.raises(ValueError):
        c.observe("invalid", True)


def test_belief_validation():
    with pytest.raises(ValueError):
        ObservationChangeController().choose({CONCEPTS[0]: .2}, 2)


def test_deterministic_episode_and_session_count():
    x = v6_episode("slow_forgetting", 100000)
    assert x == v6_episode("slow_forgetting", 100000)
    assert x["steps"] == 55
    assert x["resource_actions"] <= 6
    assert x["synthetic_only"] is True


def test_dev_report_contains_five_comparators_and_paired_diffs():
    report = compare("slow_forgetting", 2, 3, lengths=(2, 2))
    assert len(report["policies"]) == 6
    assert report["manifest"]["split"] == "development"
    assert report["manifest"]["seed_start"] == 100000
    assert report["human_evidence"] is False
    assert f"v6_minus_v5" in report["paired_contrasts"]


def test_invalid_experiment_fails_closed():
    with pytest.raises(ValueError):
        compare("hidden_scenario", 2)
    with pytest.raises(ValueError):
        compare("slow_forgetting", 0)


def test_reproducible_development_report():
    assert compare("slow_forgetting", 2, 3, lengths=(2,)) == compare("slow_forgetting", 2, 3, lengths=(2,))


def test_single_wrong_then_correct_does_not_trigger():
    c = ObservationChangeController()
    for value in (True, True, False, True, False):
        c.observe(CONCEPTS[0], value)
    assert not c.signals[CONCEPTS[0]]
    assert c.signal_onsets == 0


def test_policy_never_claims_hidden_truth_in_decision():
    choice = ObservationChangeController().choose(beliefs(), 2)
    assert choice.policy_id == POLICY_ID
    assert not hasattr(choice, "latent_mastery")
    assert not hasattr(choice, "true_forgetting")


def test_uninformative_belief_cannot_evoke_recovery_without_signal():
    c = ObservationChangeController()
    assert c.choose(beliefs(0.0), 2).action == "QUESTION"
    assert c.signal_onsets == 0
