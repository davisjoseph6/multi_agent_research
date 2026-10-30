"""Mechanistic tests of V5 guard reachability under the default synthetic model.

These are not real-learner results or evidence that either policy is optimal.
"""

from src.prototype.study_v2 import BKT
from src.prototype.study_v3_pomcp import CONCEPTS, ACTIONS, GenerativeAssumptions
from src.prototype.study_v5_guarded_planner import BeliefSupportGuardedPOMCP


def test_default_learning_rates_are_strictly_positive():
    assumptions = GenerativeAssumptions()
    assert all(0.0 < assumptions.rate(action) < 1.0 for action in ACTIONS)


def test_default_bkt_preserves_interior_beliefs_in_short_observation_sequences():
    bkt = BKT()
    for correct in (True, False):
        prior = 0.2
        for _ in range(12):
            prior = bkt.update(prior, correct)
            assert 0.0 < prior < 1.0


def test_zero_gain_condition_is_unreachable_for_interior_beliefs():
    assumptions = GenerativeAssumptions()
    belief = {concept: (i + 1) / 10 for i, concept in enumerate(CONCEPTS)}
    # Every legal action targets an imperfectly mastered concept and has
    # strictly positive assumed learning probability. Thus no legal action
    # has zero *belief-expected* gain under this model.
    for concept in CONCEPTS:
        for action in ACTIONS:
            expected_gain = (1.0 - belief[concept]) * assumptions.rate(action) / len(CONCEPTS)
            assert expected_gain > 0.0


def test_v5_guard_does_not_activate_for_interior_beliefs():
    planner = BeliefSupportGuardedPOMCP(simulations=25)
    for belief in (
        {concept: 0.2 for concept in CONCEPTS},
        {concept: (i + 1) / 10 for i, concept in enumerate(CONCEPTS)},
        {concept: (0.01 if i == 7 else 0.999) for i, concept in enumerate(CONCEPTS)},
    ):
        for seed in (71, 72):
            decision = planner.choose(belief, practice_concepts=CONCEPTS, resources_left=2, seed=seed)
            assert decision.expected_mastery_gain > 0.0
            assert decision.guard_applied is False
