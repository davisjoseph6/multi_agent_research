"""Offline fixture tests using the actual unapproved 95-item candidate CSV."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import uuid

import pytest

from src.prototype.pilot_item_bank_draft import PilotDraftItemBank
from src.prototype.pilot_session_flow_draft import PilotSequenceError, PilotSessionFlow
from src.prototype.pilot_session_store_draft import SyntheticPilotStore

T0 = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
ITEMS = Path(__file__).resolve().parents[1] / "docs/rct_candidate_v1/items.csv"
AUTH = dict(offline_staff_authorized=True, synthetic_release_authorized=True)


def submit_current(store, pid, at, *, correct=True, rating=30):
    action = store.next_action(pid, at=at)
    assert store.next_action(pid, at=at) == action
    store.mark_rendered(pid, action["action_id"], at=at)
    if action["action"] == "MVAS":
        assert action["scale"] == {"minimum": 0, "maximum": 100, "step": 1}
        response = {"rating": rating}
    else:
        question = action["question"]
        assert "answer_id" not in question
        assert "difficulty" not in question
        item = store.question_bank.by_id[question["item_id"]]
        choices = [key for key, _ in item.options]
        chosen = item.answer_id if correct else next(k for k in choices if k != item.answer_id)
        response = {"choice_id": chosen}
    request_id = uuid.uuid4().hex
    result = store.submit(pid, action["action_id"], request_id, response, at=at)
    assert result["accepted"] and not result["replayed"]
    assert store.submit(pid, action["action_id"], request_id, response, at=at)["replayed"]
    if action["action"] == "QUESTION":
        assert ("correct" in result) == (action["stage"] == "practice")
    return action


def test_bank_read_and_frozen_balanced_schedule():
    bank = PilotDraftItemBank(ITEMS)
    assert len(bank.by_id) == 95
    assert {len(bank.forms[f]) for f in ("pretest", "posttest")} == {16}
    assert len(bank.practice) == len({x.item_id for x in bank.practice}) == 55
    assert {q.concept for q in bank.practice} == {q.concept for q in bank.forms["pretest"]}
    item = bank.select(PilotSessionFlow(stage="pretest", session=1, index=0))
    assert "answer_id" not in item.public()
    assert bank.select(PilotSessionFlow(stage="practice", session=1, index=19)).item_id == bank.practice[19].item_id
    assert bank.select(PilotSessionFlow(stage="practice", session=2, index=0)).item_id == bank.practice[20].item_id
    assert bank.select(PilotSessionFlow(stage="practice", session=3, index=14)).item_id == bank.practice[54].item_id
    with pytest.raises(PilotSequenceError):
        bank.select(PilotSessionFlow(stage="practice", session=1, index=20))
    with pytest.raises(PilotSequenceError):
        bank.select(PilotSessionFlow(stage="mvas_pre", session=1))


def test_draft_items_integrate_into_real_persistent_synthetic_actions(tmp_path):
    db = tmp_path / "banked.sqlite3"
    store = SyntheticPilotStore(db, items_path=ITEMS)
    pid = store.new_synthetic_participant(at=T0)
    seen = {"pretest": set(), "practice": set(), "posttest": set()}
    store.start_supervised_visit(pid, visit=1, at=T0, **AUTH)
    for i in range(16):
        q = submit_current(store, pid, T0+timedelta(seconds=i+1))
        assert q["stage"] == "pretest" and q["draft_content_not_approved"]
        seen["pretest"].add(q["question"]["item_id"])
    assert store.scores(pid)["pretest"]["score"] == 16
    submit_current(store, pid, T0+timedelta(minutes=1), rating=11)
    for i in range(20):
        q = submit_current(store, pid, T0+timedelta(minutes=2, seconds=i))
        seen["practice"].add(q["question"]["item_id"])
    submit_current(store, pid, T0+timedelta(minutes=3), rating=26)
    assert store.snapshot(pid)["stage"] == "awaiting_visit"

    # Reopen from the exact bank and verify recorded source fingerprint.
    store = SyntheticPilotStore(db, items_path=ITEMS)
    assert store.snapshot(pid)["completed_actions"] == 38
    assert store.scores(pid)["practice"]["answered"] == 20
    v2 = T0+timedelta(days=4,minutes=3)
    store.start_supervised_visit(pid, visit=2, at=v2, **AUTH)
    submit_current(store, pid, v2+timedelta(seconds=1), rating=14)
    for i in range(20):
        q = submit_current(store, pid, v2+timedelta(minutes=1, seconds=i),correct=False)
        seen["practice"].add(q["question"]["item_id"])
    submit_current(store, pid, v2+timedelta(minutes=2), rating=23)

    v3 = v2+timedelta(days=4, minutes=2)
    store.start_supervised_visit(pid, visit=3, at=v3, **AUTH)
    submit_current(store, pid, v3+timedelta(seconds=1), rating=15)
    for i in range(15):
        q = submit_current(store, pid, v3+timedelta(minutes=1, seconds=i))
        seen["practice"].add(q["question"]["item_id"])
    submit_current(store, pid, v3+timedelta(minutes=2), rating=35)
    for i in range(16):
        q = submit_current(store, pid, v3+timedelta(minutes=3, seconds=i))
        assert q["stage"] == "posttest"
        seen["posttest"].add(q["question"]["item_id"])

    final = store.snapshot(pid)
    scores = store.scores(pid)
    assert final["stage"] == "complete"
    assert final["completed_actions"] == 93
    assert final["fatigue_deltas"] == (15, 9, 20)
    assert tuple(map(len, (seen["pretest"], seen["practice"],seen["posttest"]))) == (16, 55, 16)
    assert scores["pretest"]["score"] == 16
    assert scores["posttest"]["score"] == 16
    assert scores["practice"]["answered"] == 55
    assert scores["practice"]["correct"] == 35
    assert scores["synthetic_only"] and scores["draft_unapproved"]
    assert SyntheticPilotStore(db, items_path=ITEMS).scores(pid) == scores


def test_bank_configuration_cannot_be_mixed_or_changed(tmp_path):
    db = tmp_path / "banked.sqlite3"
    store = SyntheticPilotStore(db, items_path=ITEMS)
    pid = store.new_synthetic_participant(at=T0)
    with pytest.raises(PilotSequenceError, match="schema mismatch"):
        SyntheticPilotStore(db)
    assert store.snapshot(pid)["stage"] == "awaiting_visit"
    copied = tmp_path / "altered.csv"
    shutil.copyfile(ITEMS, copied)
    copied.write_bytes(copied.read_bytes() + b"\n")
    # A trailing blank line may be accepted as valid content but changes SHA.
    with pytest.raises(PilotSequenceError, match="schema mismatch"):
        SyntheticPilotStore(db, items_path=copied)
    different_db = tmp_path / "count_only.sqlite3"
    SyntheticPilotStore(different_db)
    with pytest.raises(PilotSequenceError, match="schema mismatch"):
        SyntheticPilotStore(different_db, items_path=ITEMS)


def test_rejected_wrong_option_preserves_pending_action(tmp_path):
    store = SyntheticPilotStore(tmp_path / "banked.sqlite3", items_path=ITEMS)
    pid = store.new_synthetic_participant(at=T0)
    store.start_supervised_visit(pid, visit=1, at=T0, **AUTH)
    action = store.next_action(pid, at=T0)
    store.mark_rendered(pid, action["action_id"], at=T0)
    with pytest.raises(PilotSequenceError):
        store.submit(pid, action["action_id"], "invalid", {"choice_id": "Z"}, at=T0)
    assert store.next_action(pid, at=T0) == action
    assert store.snapshot(pid)["completed_actions"] == 0


def test_bank_backup_restore_preserves_item_hash_and_scores(tmp_path):
    store = SyntheticPilotStore(tmp_path / "banked.sqlite3", items_path=ITEMS)
    pid = store.new_synthetic_participant(at=T0)
    store.start_supervised_visit(pid, visit=1, at=T0, **AUTH)
    submit_current(store, pid, T0)
    before = store.scores(pid)
    backup = tmp_path / "recovered.sqlite3"
    store.backup(backup)
    copy = SyntheticPilotStore(backup, items_path=ITEMS)
    assert copy.scores(pid) == before
