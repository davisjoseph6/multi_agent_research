"""Falsifiability checks for the meaning of deterioration in V3."""
from fractions import Fraction as F
import random

import pytest

from src.prototype.step79_deterioration import (
    AnchorWindow, NonstationaryAssumptions, nonstationary_transition,
    paired_response_change,
)
from src.prototype.study_v2 import BKT
from src.prototype.study_v3_pomcp import (
    CONCEPTS, EightConceptPOMCP, GenerativeAssumptions, PlanningState,
)


def anchors(wave, values, version="item-bank-v1"):
    return AnchorWindow(wave, version, tuple((f"A{i}", v) for i, v in enumerate(values)))


def test_low_initial_performance_is_not_decline():
    result = paired_response_change(anchors(0, [False] * 8), anchors(1, [False] * 8))
    assert result.observed_decline_signal is False
    assert result.one_sided_exact_p == 1
    assert result.latent_forgetting_proven is False


def test_eight_correct_to_incorrect_transitions_generate_an_alert():
    result = paired_response_change(anchors(0, [True] * 8), anchors(1, [False] * 8))
    assert result.correct_to_incorrect == 8
    assert result.one_sided_exact_p == F(1, 256)
    assert result.observed_decline_signal is True
    assert result.latent_forgetting_proven is False


def test_equal_discordance_does_not_generate_an_alert():
    result = paired_response_change(
        anchors(0, [True] * 4 + [False] * 4),
        anchors(1, [False] * 4 + [True] * 4),
    )
    assert result.one_sided_exact_p == F(163, 256)
    assert result.observed_decline_signal is False


def test_no_discordances_give_p_one():
    result = paired_response_change(anchors(0, [True, False]), anchors(1, [True, False]))
    assert result.one_sided_exact_p == 1
    assert result.observed_decline_signal is False


def test_item_order_may_change_but_ids_must_match():
    first = AnchorWindow(1, "v", (("a", True), ("b", False)))
    second = AnchorWindow(2, "v", (("b", True), ("a", False)))
    change = paired_response_change(first, second)
    assert change.correct_to_incorrect == 1
    assert change.incorrect_to_correct == 1
    with pytest.raises(ValueError, match="identifiers"):
        paired_response_change(first, AnchorWindow(2, "v", (("a", False), ("c", True))))


def test_version_and_time_mismatch_rejected():
    with pytest.raises(ValueError, match="versions"):
        paired_response_change(anchors(0, [True]), anchors(1, [False], "new"))
    with pytest.raises(ValueError, match="follow"):
        paired_response_change(anchors(1, [True]), anchors(1, [False]))


def test_malformed_responses_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        AnchorWindow(0, "v", (("x", True), ("x", False)))
    with pytest.raises(ValueError, match="invalid item"):
        AnchorWindow(0, "v", (("x", 1),))
    with pytest.raises(ValueError, match="alpha"):
        paired_response_change(anchors(0, [True]), anchors(1, [False]), alpha=0.05)


def test_v3_never_forgets_an_already_mastered_concept():
    planner = EightConceptPOMCP(simulations=2)
    start = PlanningState((True,) * len(CONCEPTS), 2)
    for seed in range(25):
        next_state, _, _ = planner._step(start, ("QUESTION", CONCEPTS[0]), random.Random(seed))
        assert next_state.mastered == start.mastered


def test_bkt_belief_can_decline_without_latent_forgetting():
    prior = 0.8
    posterior = BKT().update(prior, False)
    assert posterior < prior
    assert posterior > 0
    # The latent V3 transition above can remain true simultaneously.


def test_forgetting_model_can_lose_mastery():
    start = PlanningState((True,) * len(CONCEPTS), 2)
    future = nonstationary_transition(
        start, ("QUESTION", CONCEPTS[0]), random.Random(1),
        learning=GenerativeAssumptions(learn_practice=0.0),
        nonstationarity=NonstationaryAssumptions(1.0),
    )
    assert future.mastered == (False,) * len(CONCEPTS)


def test_zero_forgetting_recovers_monotonic_property():
    start = PlanningState((True,) * len(CONCEPTS), 2)
    for seed in range(10):
        future = nonstationary_transition(
            start, ("QUESTION", CONCEPTS[0]), random.Random(seed),
            nonstationarity=NonstationaryAssumptions(0.0),
        )
        assert future.mastered == start.mastered


def test_resources_and_bad_parameters():
    start = PlanningState((False,) * len(CONCEPTS), 0)
    with pytest.raises(ValueError, match="resource"):
        nonstationary_transition(start, ("WORKED_EXAMPLE", CONCEPTS[0]), random.Random(0))
    for bad in (float("nan"), -0.1, 1.1, True):
        with pytest.raises(ValueError):
            NonstationaryAssumptions(bad)


def test_forgetting_is_reproducible_and_does_not_mutate_original_state():
    start = PlanningState((True,) * len(CONCEPTS), 1)
    params = NonstationaryAssumptions(0.4)
    x = nonstationary_transition(start, ("CONCEPT_SUMMARY", CONCEPTS[3]), random.Random(42), nonstationarity=params)
    y = nonstationary_transition(start, ("CONCEPT_SUMMARY", CONCEPTS[3]), random.Random(42), nonstationarity=params)
    assert x == y
    assert x.resources_left == 0
    assert start.resources_left == 1
