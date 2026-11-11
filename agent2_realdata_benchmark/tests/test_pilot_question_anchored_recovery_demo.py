"""Candidate: source-grounded, question-anchored synthetic remedial actions.

This opt-in design is NOT an amendment to an approved human-study protocol.
The legacy V3 selector remains the default and is regression-tested.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid

import pytest

from src.prototype.pilot_session_flow_draft import PilotSequenceError
from src.prototype.pilot_three_arm_store_draft import SyntheticThreeArmPilotStore
from src.prototype.study_v2 import CONCEPTS, RECOVERY_ACTIONS
from src.prototype.study_v3_pomcp import EightConceptPOMCP


ROOT = Path(__file__).resolve().parents[1] / "docs" / "rct_candidate_v1"
T0 = datetime(2026, 11, 20, 9, tzinfo=timezone.utc)
STAFF = {
    "offline_staff_authorized": True,
    "synthetic_release_authorized": True,
}


def _build(tmp_path, *, anchored=True):
    return SyntheticThreeArmPilotStore(
        tmp_path / "fictional_only.sqlite3", items_path=ROOT / "items.csv",
        resources_path=ROOT / "resources.csv", simulations=41,
        question_anchored_recovery=anchored,
    )


def _submit(store, pid, action, response, at):
    assert store.mark_rendered(pid, action["action_id"], at=at)["accepted"]
    rid = uuid.uuid4().hex
    result = store.submit(pid, action["action_id"], rid, response, at=at)
    assert result["accepted"] and not result["replayed"]
    assert store.submit(pid, action["action_id"], rid, response, at=at)["replayed"]
    return result


def _arrive_at_one_incorrect_practice(store):
    pid = store.new_synthetic_participant(arm="A", at=T0)
    store.start_supervised_visit(pid, visit=1, at=T0, **STAFF)
    at = T0 + timedelta(seconds=1)
    for _ in range(16):
        a = store.next_action(pid, at=at)
        assert a["stage"] == "pretest" and a["action"] == "QUESTION"
        _submit(store, pid, a, {"choice_id": a["question"]["options"][0][0]}, at)
        at += timedelta(seconds=1)
    a = store.next_action(pid, at=at)
    assert a["action"] == "MVAS"
    _submit(store, pid, a, {"rating": 25}, at)
    at += timedelta(seconds=1)

    a = store.next_action(pid, at=at)
    assert a["action"] == "QUESTION" and a["stage"] == "practice"
    item = store.policy_bank.by_id[a["question"]["item_id"]]
    wrong = next(x for x, _ in item.options if x != item.answer_id)
    done = _submit(store, pid, a, {"choice_id": wrong}, at)
    assert done["correct"] is False
    at += timedelta(seconds=1)
    return pid, at, item, wrong


@pytest.mark.parametrize("action_kind", RECOVERY_ACTIONS)
def test_each_recovery_is_based_on_last_wrong_question(tmp_path, monkeypatch, action_kind):
    store = _build(tmp_path)
    pid, at, mistaken, wrong = _arrive_at_one_incorrect_practice(store)
    saved = store.selector._candidate

    def force_recovery(state):
        assert state["question_anchored_recovery"] is True
        assert state["last_incorrect_concept"] == mistaken.concept
        state["recovery"]["pomcp_resource_spent"] = 1
        return {
            "action": action_kind, "concept": mistaken.concept,
            "item_id": None,
        }

    monkeypatch.setattr(store.selector, "_candidate", force_recovery)
    response = store.next_action(pid, at=at)
    assert response == store.next_action(pid, at=at)
    assert response["action"] == action_kind
    assert response["stage"] == "practice"
    assert response["resource"]["question_anchored_demo_only"]
    anchor = response["resource"]["question_anchor"]
    assert anchor["target_item_id"] == mistaken.item_id
    assert anchor["target_question"] == mistaken.prompt
    assert anchor["prior_selected_option"]["id"] == wrong
    assert anchor["target_concept"] == mistaken.concept
    assert anchor["source"] == "MOST_RECENT_INCORRECT_PRACTICE_THIS_VISIT"
    assert not anchor["content_independently_reviewed"]
    assert "answer_id" not in response["resource"]
    assert response["resource"]["application_prompt"]
    if action_kind == "DROP_2":
        question = response["question"]
        assert question["item_id"] == mistaken.item_id
        assert question["prompt"] == mistaken.prompt
        assert question["fictional_question_anchored_retry"]
        assert len(question["options"]) == 2
        assert {x for x, _ in question["options"]} == {wrong, mistaken.answer_id}
        with pytest.raises(PilotSequenceError, match="not offered"):
            store.mark_rendered(pid, response["action_id"], at=at)
            # Never entered: see separate invalid-choice test.
        _submit(store, pid, response, {"choice_id": wrong}, at)
    else:
        assert "question" not in response
        _submit(store, pid, response, {"status": "completed"}, at)
    assert store.snapshot(pid)["index"] == 1
    assert store.snapshot(pid)["unique_practice_used"] == 1
    assert store.snapshot(pid)["recovery_completed"] == 1
    monkeypatch.setattr(store.selector, "_candidate", saved)


def test_recovery_cannot_be_offered_without_a_recorded_wrong_answer(tmp_path, monkeypatch):
    store = _build(tmp_path)
    pid = store.new_synthetic_participant(arm="A", at=T0)
    store.start_supervised_visit(pid, visit=1, at=T0, **STAFF)
    # Stub a broken selector choosing recovery before any wrong answer.
    def invented(state):
        assert state["last_incorrect_concept"] is None
        return {"action": "SOCRATIC_HINT", "concept": CONCEPTS[0], "item_id": None}
    monkeypatch.setattr(store.selector, "_candidate", invented)
    # Complete pretest, M-VAS and one correct practice response to reach index 1.
    at = T0 + timedelta(seconds=1)
    for _ in range(16):
        a = store.next_action(pid, at=at)
        _submit(store, pid, a, {"choice_id": a["question"]["options"][0][0]}, at)
        at += timedelta(seconds=1)
    a = store.next_action(pid, at=at)
    _submit(store, pid, a, {"rating": 20}, at)
    at += timedelta(seconds=1)
    # The warmup is always practice, so force a correct first practice answer.
    a = store.next_action(pid, at=at)
    item = store.policy_bank.by_id[a["question"]["item_id"]]
    _submit(store, pid, a, {"choice_id": item.answer_id}, at)
    at += timedelta(seconds=1)
    with pytest.raises(PilotSequenceError, match="no incorrect practice answer"):
        store.next_action(pid, at=at)


def test_two_choice_retry_rejects_a_hidden_third_option(tmp_path, monkeypatch):
    store = _build(tmp_path)
    pid, at, item, wrong = _arrive_at_one_incorrect_practice(store)
    monkeypatch.setattr(
        store.selector, "_candidate",
        lambda s: {"action": "DROP_2", "concept": item.concept, "item_id": None},
    )
    a = store.next_action(pid, at=at)
    store.mark_rendered(pid, a["action_id"], at=at)
    unoffered = next(option_id for option_id, _ in item.options
                     if option_id not in {wrong, item.answer_id})
    with pytest.raises(PilotSequenceError, match="not offered"):
        store.submit(pid, a["action_id"], uuid.uuid4().hex,
                     {"choice_id": unoffered}, at=at)
    assert store.next_action(pid, at=at) == a
    assert _submit(store, pid, a, {"choice_id": item.answer_id}, at)["accepted"]
    assert store.snapshot(pid)["index"] == 1


def test_planner_resource_actions_can_only_target_missed_concept():
    planner = EightConceptPOMCP(simulations=41)
    initial = {c: 0.2 for c in CONCEPTS}
    target = CONCEPTS[2]
    result = planner.choose(
        initial, practice_concepts=CONCEPTS,
        resource_concepts=(target,), resources_left=2, seed=71,
    )
    for name in result.root_visits:
        if not name.startswith("PRACTICE::"):
            assert name.endswith("::" + target)
    no_resource = planner.choose(
        initial, practice_concepts=CONCEPTS,
        resource_concepts=(), resource_actions=(),
        resources_left=2, seed=71,
    )
    assert all(name.startswith("PRACTICE::") for name in no_resource.root_visits)
    with pytest.raises(ValueError):
        planner.choose(
            initial, practice_concepts=CONCEPTS,
            resource_concepts=("INVENTED_CONCEPT",), seed=71,
        )


def test_original_concept_level_policy_remains_explicit_default(tmp_path):
    store = _build(tmp_path, anchored=False)
    assert store.question_anchored_recovery is False
    assert "original_concept_level_v3" in store.policy_config
    with pytest.raises(PilotSequenceError, match="policy or source fingerprint"):
        SyntheticThreeArmPilotStore(
            store.path, items_path=ROOT / "items.csv",
            resources_path=ROOT / "resources.csv",
            simulations=41, question_anchored_recovery=True,
        )
