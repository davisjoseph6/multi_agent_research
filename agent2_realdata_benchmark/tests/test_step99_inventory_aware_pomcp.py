"""Finite-inventory POMCP safety and accounting tests (research only)."""
import random

import pytest

from src.prototype.step99_inventory_aware_pomcp import (
    DRAFT_COUNTS, InventoryProgress, InventoryAwarePOMCP, SimulatedState,
)
from src.prototype.study_v3_pomcp import CONCEPTS, PRACTICE


def test_initial_bank_has_55_questions_and_forces_question_warmup():
    p = InventoryProgress()
    assert sum(p.remaining) == 55
    assert len(p.legal()) == 8
    assert all(kind == PRACTICE for kind, _ in p.legal())
    after_first = p.after((PRACTICE, CONCEPTS[0]))
    assert len(after_first.legal()) == 40


def test_practice_consumes_one_without_affecting_resource_budget():
    p = InventoryProgress().after((PRACTICE, CONCEPTS[0]))
    assert p.remaining[0] == 6
    assert p.answered_in_session == 1
    assert p.resources_left == 2


def test_resource_consumes_slot_not_question():
    p = InventoryProgress().after((PRACTICE, CONCEPTS[0]))
    q = p.after(("WORKED_EXAMPLE", CONCEPTS[0]))
    assert q.remaining == p.remaining
    assert q.answered_in_session == 1
    assert q.resources_left == 1
    q = q.after(("SOCRATIC_HINT", CONCEPTS[0]))
    assert q.resources_left == 0
    assert all(action == PRACTICE for action, _ in q.legal())


def test_twenty_twenty_fifteen_questions_and_resource_resets():
    p = InventoryProgress()
    sessions = (20, 20, 15)
    for index, count in enumerate(sessions):
        # First action of each session must consume a normal question.
        assert all(a[0] == PRACTICE for a in p.legal())
        warmup = next(a for a in p.legal() if a[0] == PRACTICE)
        p = p.after(warmup)
        # Earlier sessions may exhaust Utility. Always select a resource
        # attached to an available practice concept.
        resource = next(a for a in p.legal() if a[0] == "CONCEPT_SUMMARY")
        p = p.after(resource)
        assert p.resources_left == 1
        for _ in range(count - 1):
            action = next(a for a in p.legal() if a[0] == PRACTICE)
            p = p.after(action)
        assert p.session == index + 1
        assert p.answered_in_session == 0
        assert p.resources_left == (2 if index < 2 else 0)
    assert p.done
    assert sum(p.remaining) == 0
    assert p.legal() == ()


def test_a_concept_depletion_blocks_its_resources():
    p = InventoryProgress()
    for _ in range(DRAFT_COUNTS[0]):
        p = p.after((PRACTICE, CONCEPTS[0]))
    assert p.remaining[0] == 0
    assert all(concept != CONCEPTS[0] for _, concept in p.legal())
    with pytest.raises(ValueError, match="not feasible"):
        p.after(("WORKED_EXAMPLE", CONCEPTS[0]))


def test_inventory_invariant_rejects_impossible_snapshot():
    with pytest.raises(ValueError, match="disagree"):
        InventoryProgress(remaining=(6,) * 8)
    with pytest.raises(ValueError, match="Invalid session"):
        InventoryProgress(session=4)


def test_root_selection_is_feasible_and_deterministic_for_seed():
    planner = InventoryAwarePOMCP(horizon=3, simulations=80)
    p = InventoryProgress()
    beliefs = {c: .25 for c in CONCEPTS}
    first = planner.choose(beliefs, p, seed=79)
    again = planner.choose(beliefs, p, seed=79)
    assert (first.action, first.concept) in p.legal()
    assert first.action == PRACTICE
    assert first == again
    assert first.synthetic_only


def test_single_action_transition_consumes_one_real_question():
    planner = InventoryAwarePOMCP(simulations=5)
    p = InventoryProgress()
    state = SimulatedState((False,) * 8, p)
    next_state, observation, reward = planner.step(
        state, (PRACTICE, CONCEPTS[0]), random.Random(2))
    assert sum(next_state.progress.remaining) == 54
    assert observation in (0, 1)
    assert -1 <= reward <= 1


def test_depleted_inventory_prevents_search_action_even_if_belief_high():
    p = InventoryProgress()
    for _ in range(DRAFT_COUNTS[0]):
        p = p.after((PRACTICE, CONCEPTS[0]))
    result = InventoryAwarePOMCP(simulations=50).choose(
        {c: 1.0 if c == CONCEPTS[0] else .2 for c in CONCEPTS}, p, seed=3)
    assert result.concept != CONCEPTS[0]


def test_last_session_terminal_and_no_post_question_recovery():
    p = InventoryProgress()
    while not p.done:
        action = next(x for x in p.legal() if x[0] == PRACTICE)
        p = p.after(action)
    assert p.session == 3
    assert p.resources_left == 0
    with pytest.raises(ValueError):
        p.after(("SOCRATIC_HINT", CONCEPTS[0]))


def test_no_resource_is_allowed_before_first_question_of_any_session():
    p = InventoryProgress()
    for session_length in (20, 20):
        assert all(a[0] == PRACTICE for a in p.legal())
        with pytest.raises(ValueError, match="not feasible"):
            p.after(("CONCEPT_SUMMARY", CONCEPTS[-1]))
        for _ in range(session_length):
            p = p.after(next(a for a in p.legal() if a[0] == PRACTICE))
    assert p.session == 2
    assert all(a[0] == PRACTICE for a in p.legal())


def test_invalid_belief_rejected():
    planner = InventoryAwarePOMCP(simulations=3)
    with pytest.raises(ValueError):
        planner.choose({c: float("nan") for c in CONCEPTS}, InventoryProgress())
