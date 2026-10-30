"""V5 guard evidence. These checks are synthetic only, not human evidence."""
import dataclasses

from src.prototype.study_v3_pomcp import (
    CONCEPTS, PRACTICE, EightConceptPOMCP, GenerativeAssumptions,
)
from src.prototype.study_v5_guarded_planner import BeliefSupportGuardedPOMCP


def witness_belief():
    return {c: (0.0 if c == "Nudge Theory" else 1.0) for c in CONCEPTS}


def test_v3_original_counterexample_preserved():
    raw = EightConceptPOMCP(simulations=240).choose(
        witness_belief(), practice_concepts=CONCEPTS, resources_left=2, seed=71
    )
    assert raw.action == PRACTICE and raw.concept == "Utility"


def test_guard_intercepts_known_zero_gain_witness():
    choice = BeliefSupportGuardedPOMCP(simulations=240).choose(
        witness_belief(), practice_concepts=CONCEPTS, resources_left=2, seed=71
    )
    assert choice.guard_applied
    assert (choice.raw_action, choice.raw_concept) == (PRACTICE, "Utility")
    assert choice.concept == "Nudge Theory"
    assert choice.expected_mastery_gain > 0
    assert choice.policy_id == "pomcp_v5_positive_belief_support_guard_v1"


def test_guard_outputs_provenance_in_serializable_trace():
    choice = BeliefSupportGuardedPOMCP(simulations=240).choose(
        witness_belief(), practice_concepts=CONCEPTS, resources_left=2, seed=71
    )
    trace = dataclasses.asdict(choice)
    assert trace["guard_applied"] and trace["raw_concept"] == "Utility"
    assert len(trace["root_visits"]) == 40
    assert sum(trace["root_visits"].values()) == 239


def test_no_resources_only_practice_allowed():
    choice = BeliefSupportGuardedPOMCP(simulations=240).choose(
        witness_belief(), practice_concepts=CONCEPTS, resources_left=0, seed=71
    )
    assert choice.action == PRACTICE and choice.concept == "Nudge Theory"
    assert choice.expected_mastery_gain > 0


def test_availability_restriction_still_honored():
    choice = BeliefSupportGuardedPOMCP(simulations=240).choose(
        witness_belief(), practice_concepts=["Utility"], resources_left=2, seed=71
    )
    assert choice.concept == "Utility"
    assert choice.expected_mastery_gain == 0


def test_zero_learning_model_cannot_fabricate_gain():
    assumptions = GenerativeAssumptions(
        learn_practice=0, learn_summary=0, learn_drop2=0,
        learn_worked=0, learn_socratic=0,
    )
    choice = BeliefSupportGuardedPOMCP(simulations=80, assumptions=assumptions).choose(
        witness_belief(), practice_concepts=CONCEPTS, resources_left=2, seed=71
    )
    assert not choice.guard_applied
    assert choice.expected_mastery_gain == 0


def test_fully_mastered_state_has_no_strict_positive_gain():
    choice = BeliefSupportGuardedPOMCP(simulations=80).choose(
        dict.fromkeys(CONCEPTS, 1.0), practice_concepts=CONCEPTS, seed=71
    )
    assert not choice.guard_applied
    assert choice.expected_mastery_gain == 0


def test_deterministic_for_fixed_seed_and_config():
    planner = BeliefSupportGuardedPOMCP(simulations=80)
    a = planner.choose(witness_belief(), practice_concepts=CONCEPTS, seed=34)
    b = planner.choose(witness_belief(), practice_concepts=CONCEPTS, seed=34)
    assert a == b


def test_assumption_fingerprint_remains_model_fingerprint():
    assumptions = GenerativeAssumptions()
    choice = BeliefSupportGuardedPOMCP(simulations=80).choose(
        witness_belief(), practice_concepts=CONCEPTS, seed=34
    )
    assert choice.assumption_hash == assumptions.fingerprint
    assert choice.policy_id != choice.assumption_hash
