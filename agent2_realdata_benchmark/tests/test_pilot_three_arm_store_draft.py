"""Offline three-arm rehearsal with unapproved content and synthetic records."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import uuid

import pytest

from src.prototype.pilot_session_flow_draft import PilotSequenceError
from src.prototype.pilot_three_arm_store_draft import (
    SyntheticThreeArmPilotStore, POLICY_VERSION,
)
from src.prototype.study_v2 import CONCEPTS, RECOVERY_ACTIONS

T0 = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1] / "docs/rct_candidate_v1"
ITEMS = ROOT / "items.csv"
RESOURCES = ROOT / "resources.csv"
AUTH = dict(offline_staff_authorized=True, synthetic_release_authorized=True)


def build(db, simulations=41):
    return SyntheticThreeArmPilotStore(
        db, items_path=ITEMS, resources_path=RESOURCES, simulations=simulations)


def do_action(store, pid, when, expected=None):
    action = store.next_action(pid, at=when)
    assert action == store.next_action(pid, at=when)
    assert action["synthetic_only"] and action["draft_content_not_approved"]
    if expected:
        assert action["action"] == expected
    assert store.mark_rendered(pid, action["action_id"], at=when)["accepted"]
    kind = action["action"]
    if kind in ("QUESTION", "DROP_2"):
        q = action["question"]
        assert "answer_id" not in q and "difficulty" not in q
        assert len(q["options"]) >= 2
        assert isinstance(q["options"], list)
        response = dict(choice_id=q["options"][0][0])
    elif kind == "MVAS":
        assert action["scale"] == dict(minimum=0, maximum=100, step=1)
        response = dict(rating=37 if action["stage"] == "mvas_post" else 22)
    else:
        assert kind in RECOVERY_ACTIONS
        assert action["resource"]["text"]
        response = dict(status="completed")
    request_id = uuid.uuid4().hex
    result = store.submit(pid, action["action_id"], request_id, response, at=when)
    assert result["accepted"] and not result["replayed"]
    assert store.submit(pid, action["action_id"], request_id, response, at=when)["replayed"]
    return action


def complete_one(store, pid):
    actions = Counter()
    all_practice_ids = set()
    for session in (1, 2, 3):
        at = T0 + timedelta(days=4 * (session - 1))
        store.start_supervised_visit(pid, visit=session, at=at, **AUTH)
        when = at + timedelta(seconds=1)
        if session == 1:
            for _ in range(16):
                a = do_action(store, pid, when, "QUESTION")
                assert a["stage"] == "pretest"
                when += timedelta(seconds=1)
        a = do_action(store, pid, when, "MVAS")
        assert a["stage"] == "mvas_pre"
        when += timedelta(seconds=1)
        within = Counter()
        for _ in range(30):  # 20 questions + at most 2 resources, or 15 + 2.
            if store.snapshot(pid)["stage"] != "practice":
                break
            a = do_action(store, pid, when)
            assert a["stage"] == "practice"
            within[a["action"]] += 1
            actions[a["action"]] += 1
            if a["action"] == "QUESTION":
                item_id = a["question"]["item_id"]
                assert item_id not in all_practice_ids
                all_practice_ids.add(item_id)
            when += timedelta(seconds=1)
        else:
            raise AssertionError("practice budget did not close")
        assert within["QUESTION"] == (20 if session in (1, 2) else 15)
        assert sum(n for k, n in within.items() if k in RECOVERY_ACTIONS) <= 2
        a = do_action(store, pid, when, "MVAS")
        assert a["stage"] == "mvas_post"
        when += timedelta(seconds=1)
        if session == 3:
            for _ in range(16):
                a = do_action(store, pid, when, "QUESTION")
                assert a["stage"] == "posttest"
                when += timedelta(seconds=1)
        else:
            assert store.snapshot(pid)["stage"] == "awaiting_visit"
    assert store.snapshot(pid)["stage"] == "complete"
    assert len(all_practice_ids) == 55
    assert store.scores(pid)["practice"]["answered"] == 55
    assert store.scores(pid)["posttest"]["answered"] == 16
    assert store.scores(pid)["pretest"]["answered"] == 16
    assert store.snapshot(pid)["fatigue_deltas"] == (15, 15, 15)
    return actions


def test_each_arm_completes_full_three_visit_journey(tmp_path):
    db = tmp_path / "three_arm.sqlite3"
    store = build(db)
    observed = {}
    for arm in "ABC":
        pid = store.new_synthetic_participant(arm=arm, at=T0)
        observed[arm] = complete_one(store, pid)
        assert store.snapshot(pid)["arm"] == arm
        assert store.snapshot(pid)["visits_finished"] == 3
        assert store.scores(pid)["posttest"]["score"] is not None
    assert observed["B"] == Counter({"QUESTION": 55})
    assert observed["C"] == Counter({"QUESTION": 55})
    assert observed["A"]["QUESTION"] == 55
    assert sum(observed["A"][a] for a in RECOVERY_ACTIONS) <= 6
    audit = store.audit_arms()
    assert audit["allocated"] == {"A": 1, "B": 1, "C": 1}
    assert not audit["approved_for_humans"]
    assert build(db).audit_arms() == audit


def test_arm_a_resource_actions_do_not_advance_practice_count(tmp_path, monkeypatch):
    store = build(tmp_path / "three_arm.sqlite3")
    pid = store.new_synthetic_participant(arm="A", at=T0)
    store.start_supervised_visit(pid, visit=1, at=T0, **AUTH)
    when = T0 + timedelta(seconds=1)
    for _ in range(16):
        do_action(store, pid, when, "QUESTION")
        when += timedelta(seconds=1)
    do_action(store, pid, when, "MVAS")
    when += timedelta(seconds=1)
    do_action(store, pid, when, "QUESTION")
    when += timedelta(seconds=1)
    assert store.snapshot(pid)["index"] == 1
    normal = store.selector._candidate

    def force_two_resource_actions(state):
        spent = state["recovery"].get("pomcp_resource_spent", 0)
        if state["arm"] == "A" and state["index"] == 1 and spent < 2:
            state["recovery"]["pomcp_resource_spent"] = spent + 1
            return dict(action="CONCEPT_SUMMARY", concept=CONCEPTS[0], item_id=None)
        return normal(state)

    monkeypatch.setattr(store.selector, "_candidate", force_two_resource_actions)
    for _ in range(2):
        a = do_action(store, pid, when, "CONCEPT_SUMMARY")
        assert a["resource"]["resource_id"]
        assert store.snapshot(pid)["index"] == 1
        when += timedelta(seconds=1)
    assert store.snapshot(pid)["recovery_offered"] == 2
    assert store.snapshot(pid)["unique_practice_used"] == 1
    assert store.next_action(pid, at=when)["action"] == "QUESTION"

    with sqlite3.connect(store.path) as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM pilot_three_arm_selected"
        ).fetchone()[0]
        assert n == 16 + 1 + 1 + 2 + 1


def test_b_and_c_never_offer_recovery_actions_in_first_visit(tmp_path):
    store = build(tmp_path / "three_arm.sqlite3")
    for arm in "BC":
        pid = store.new_synthetic_participant(arm=arm, at=T0)
        store.start_supervised_visit(pid, visit=1, at=T0, **AUTH)
        when = T0 + timedelta(seconds=1)
        for _ in range(16):
            do_action(store, pid, when, "QUESTION")
            when += timedelta(seconds=1)
        do_action(store, pid, when, "MVAS")
        when += timedelta(seconds=1)
        for _ in range(20):
            action = do_action(store, pid, when, "QUESTION")
            assert action["stage"] == "practice"
            when += timedelta(seconds=1)
        assert store.snapshot(pid)["recovery_offered"] == 0


def test_policy_config_and_assignment_are_immutable_across_restarts(tmp_path):
    db = tmp_path / "three_arm.sqlite3"
    store = build(db)
    pid = store.new_synthetic_participant(arm="B", at=T0)
    assert build(db).snapshot(pid)["arm"] == "B"
    with pytest.raises(PilotSequenceError, match="policy or source fingerprint"):
        build(db, simulations=42)
    with pytest.raises(PilotSequenceError, match="A, B or C"):
        store.new_synthetic_participant(arm="D", at=T0)
    with pytest.raises(PilotSequenceError, match="unknown synthetic"):
        store.snapshot("SYN_PILOT_unknown")
    with pytest.raises(PilotSequenceError, match="cannot convert"):
        # Existing populated draft-bank-only SQLite must remain separated.
        other = tmp_path / "previous_bank.sqlite3"
        from src.prototype.pilot_session_store_draft import SyntheticPilotStore
        old = SyntheticPilotStore(other, items_path=ITEMS)
        old.new_synthetic_participant(at=T0)
        build(other)


def test_invalid_foreign_and_stale_actions_are_rejected(tmp_path):
    store = build(tmp_path / "three_arm.sqlite3")
    p = store.new_synthetic_participant(arm="A", at=T0)
    q = store.new_synthetic_participant(arm="C", at=T0)
    store.start_supervised_visit(p, visit=1, at=T0, **AUTH)
    a = store.next_action(p, at=T0)
    with pytest.raises(PilotSequenceError):
        store.mark_rendered(q, a["action_id"], at=T0)
    with pytest.raises(PilotSequenceError):
        store.submit(q, a["action_id"], "other", {"choice_id": "A"}, at=T0)
    store.mark_rendered(p, a["action_id"], at=T0)
    with pytest.raises(PilotSequenceError):
        store.submit(p, a["action_id"], "bad", {"choice_id": "Z"}, at=T0)
    assert store.next_action(p, at=T0) == a
    good = dict(choice_id=a["question"]["options"][0][0])
    assert store.submit(p, a["action_id"], "same", good, at=T0)["accepted"]
    assert store.submit(p, a["action_id"], "same", good, at=T0)["replayed"]
    with pytest.raises(PilotSequenceError):
        store.submit(p, a["action_id"], "same", {"choice_id": "Z"}, at=T0)


def test_synthetic_backup_retains_policy_and_action_integrity(tmp_path):
    store = build(tmp_path / "three_arm.sqlite3")
    pid = store.new_synthetic_participant(arm="A", at=T0)
    store.start_supervised_visit(pid, visit=1, at=T0, **AUTH)
    do_action(store, pid, T0 + timedelta(seconds=1))
    before = store.snapshot(pid)
    backup = tmp_path / "backup.sqlite3"
    assert store.backup(backup)["synthetic_only"]
    restored = build(backup)
    assert restored.snapshot(pid) == before
    assert restored.scores(pid) == store.scores(pid)
