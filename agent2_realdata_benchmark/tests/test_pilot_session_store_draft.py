"""SQLite synthetic-only pilot flow regression checks; no real student records."""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import uuid

import pytest

from src.prototype.pilot_session_flow_draft import PilotSequenceError
from src.prototype.pilot_session_store_draft import SyntheticPilotStore


T0 = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
AUTH = dict(offline_staff_authorized=True, synthetic_release_authorized=True)


def perform(store, pid, when, *, rating=31):
    offered = store.next_action(pid, at=when)
    assert offered["action"] in ("QUESTION", "MVAS")
    assert store.next_action(pid, at=when)["action_id"] == offered["action_id"]
    assert store.mark_rendered(pid, offered["action_id"], at=when)["first_report"]
    assert not store.mark_rendered(pid, offered["action_id"], at=when)["first_report"]
    payload = (
        {"rating": rating} if offered["action"] == "MVAS"
        else {"choice_id": "A"}
    )
    result = store.submit(pid, offered["action_id"], uuid.uuid4().hex,
                          payload, at=when)
    assert result["accepted"] and result["replayed"] is False
    return offered


def through_first_visit(store, pid):
    store.start_supervised_visit(pid, visit=1, at=T0, **AUTH)
    for n in range(16):
        offered = perform(store, pid, T0+timedelta(seconds=n+1))
        assert offered["stage"] == "pretest"
    offered = perform(store, pid, T0+timedelta(minutes=1), rating=15)
    assert offered["stage"] == "mvas_pre"
    for n in range(20):
        offered = perform(store, pid, T0+timedelta(minutes=2, seconds=n))
        assert offered["stage"] == "practice"
    offered = perform(store, pid, T0+timedelta(minutes=3), rating=27)
    assert offered["stage"] == "mvas_post"
    assert store.next_action(pid, at=T0+timedelta(minutes=3))["action"] == "AWAITING_SUPERVISOR"


def test_complete_restarts_and_persists_93_synthetic_actions(tmp_path):
    db = tmp_path / "pilot.sqlite3"
    store = SyntheticPilotStore(db)
    pid = store.new_synthetic_participant(at=T0)
    assert pid.startswith("SYN_PILOT_")
    through_first_visit(store, pid)
    snap = store.snapshot(pid)
    assert snap["visits_finished"] == 1
    assert snap["fatigue_deltas"] == (12, None, None)
    assert snap["completed_actions"] == 38

    # Restart the Python object and reconnect to the same on-disk state.
    store = SyntheticPilotStore(db)
    assert store.snapshot(pid) == snap

    v2 = T0 + timedelta(days=4, minutes=3)
    store.start_supervised_visit(pid, visit=2, at=v2, **AUTH)
    offered = perform(store, pid, v2+timedelta(seconds=1), rating=22)
    assert offered["stage"] == "mvas_pre"
    for n in range(20):
        offered = perform(store, pid, v2+timedelta(minutes=1, seconds=n))
        assert offered["stage"] == "practice"
    offered = perform(store, pid, v2+timedelta(minutes=2), rating=34)
    assert offered["stage"] == "mvas_post"

    v3 = v2 + timedelta(days=4, minutes=2)
    store.start_supervised_visit(pid, visit=3, at=v3, **AUTH)
    assert perform(store, pid, v3+timedelta(seconds=1), rating=31)["stage"] == "mvas_pre"
    for n in range(15):
        assert perform(store, pid, v3+timedelta(minutes=1, seconds=n))["stage"] == "practice"
    assert perform(store, pid, v3+timedelta(minutes=2), rating=40)["stage"] == "mvas_post"
    for n in range(16):
        assert perform(store, pid, v3+timedelta(minutes=3, seconds=n))["stage"] == "posttest"
    assert store.next_action(pid, at=v3+timedelta(minutes=4))["action"] == "COMPLETE"
    final = store.snapshot(pid)
    assert final["stage"] == "complete" and final["session"] == 3
    assert final["visits_started"] == final["visits_finished"] == 3
    assert final["completed_actions"] == 93  # 87 MCQ placeholders + six ratings
    assert final["fatigue_deltas"] == (12, 12, 9)
    assert final["approved_for_humans"] is False

    store = SyntheticPilotStore(db)
    assert store.snapshot(pid) == final


def test_unapproved_or_early_visits_rejected_and_roll_back(tmp_path):
    store = SyntheticPilotStore(tmp_path / "pilot.sqlite3")
    pid = store.new_synthetic_participant(at=T0)
    with pytest.raises(PilotSequenceError):
        store.start_supervised_visit(pid, visit=1, at=T0)
    with pytest.raises(PilotSequenceError):
        store.start_supervised_visit(pid, visit=2, at=T0, **AUTH)
    assert store.snapshot(pid)["stage"] == "awaiting_visit"
    through_first_visit(store, pid)
    before = store.snapshot(pid)
    for when in (T0+timedelta(days=2), T0+timedelta(days=6)):
        with pytest.raises(PilotSequenceError):
            store.start_supervised_visit(pid, visit=2, at=when, **AUTH)
        assert store.snapshot(pid) == before
    store.start_supervised_visit(pid, visit=2,
        at=T0+timedelta(days=4, minutes=3), **AUTH)
    assert store.snapshot(pid)["stage"] == "mvas_pre"


def test_pending_action_idempotency_and_foreign_record_denial(tmp_path):
    store = SyntheticPilotStore(tmp_path / "pilot.sqlite3")
    p = store.new_synthetic_participant(at=T0)
    other = store.new_synthetic_participant(at=T0)
    store.start_supervised_visit(p, visit=1, at=T0, **AUTH)
    a = store.next_action(p, at=T0)
    with pytest.raises(PilotSequenceError):
        store.mark_rendered(other, a["action_id"], at=T0)
    with pytest.raises(PilotSequenceError):
        store.submit(p, a["action_id"], "r1", {"choice_id": "B"}, at=T0)
    store.mark_rendered(p, a["action_id"], at=T0)
    assert store.submit(p, a["action_id"], "r1", {"choice_id": "B"}, at=T0)["replayed"] is False
    assert store.submit(p, a["action_id"], "r1", {"choice_id": "B"}, at=T0)["replayed"] is True
    with pytest.raises(PilotSequenceError):
        store.submit(p, a["action_id"], "r1", {"choice_id": "C"}, at=T0)
    with pytest.raises(PilotSequenceError):
        store.submit(p, a["action_id"], "r2", {"choice_id": "B"}, at=T0)
    assert store.snapshot(p)["completed_actions"] == 1
    assert store.snapshot(other)["completed_actions"] == 0


def test_mvas_cannot_be_forged_repeated_or_floated(tmp_path):
    store = SyntheticPilotStore(tmp_path / "pilot.sqlite3")
    pid = store.new_synthetic_participant(at=T0)
    store.start_supervised_visit(pid, visit=1, at=T0, **AUTH)
    for n in range(16):
        perform(store, pid, T0+timedelta(seconds=n+1))
    at = T0+timedelta(minutes=1)
    action = store.next_action(pid, at=at)
    assert action["action"] == "MVAS"
    store.mark_rendered(pid, action["action_id"], at=at)
    for invalid in (True, 25.5, "25", -1, 101, None):
        with pytest.raises(ValueError):
            store.submit(pid, action["action_id"], uuid.uuid4().hex,
                         {"rating": invalid}, at=at)
    with pytest.raises(PilotSequenceError):
        store.submit(pid, action["action_id"], uuid.uuid4().hex,
                     {"values": [25]}, at=at)
    assert store.snapshot(pid)["stage"] == "mvas_pre"
    r = store.submit(pid, action["action_id"], "valid1", {"rating": 0}, at=at)
    assert r["stage"] == "practice"
    with pytest.raises(PilotSequenceError):
        store.submit(pid, action["action_id"], "valid2", {"rating": 30}, at=at)


def test_action_timestamps_must_follow_offer_and_render(tmp_path):
    store = SyntheticPilotStore(tmp_path / "pilot.sqlite3")
    pid = store.new_synthetic_participant(at=T0)
    store.start_supervised_visit(pid, visit=1, at=T0, **AUTH)
    offer_at = T0 + timedelta(minutes=1)
    a = store.next_action(pid, at=offer_at)
    with pytest.raises(PilotSequenceError, match="predates"):
        store.mark_rendered(pid, a["action_id"], at=T0)
    store.mark_rendered(pid, a["action_id"], at=offer_at)
    with pytest.raises(PilotSequenceError, match="predates"):
        store.submit(pid, a["action_id"], "badclock", {"choice_id": "A"}, at=T0)
    assert store.submit(pid, a["action_id"], "goodclock",
                        {"choice_id": "A"}, at=offer_at)["accepted"]
    with pytest.raises(PilotSequenceError):
        store.next_action(pid, at=T0)


def test_consistent_sqlite_backup_and_recovery(tmp_path):
    db = tmp_path / "synthetic.sqlite3"
    store = SyntheticPilotStore(db)
    pid = store.new_synthetic_participant(at=T0)
    through_first_visit(store, pid)
    expected = store.snapshot(pid)
    destination = tmp_path / "backups" / "copy.sqlite3"
    outcome = store.backup(destination)
    assert len(outcome["sha256"]) == 64 and outcome["synthetic_only"]
    assert destination.stat().st_mode & 0o777 == 0o600
    assert SyntheticPilotStore(destination).snapshot(pid) == expected
    with pytest.raises(FileExistsError):
        store.backup(destination)


def test_database_version_and_synthetic_id_are_enforced(tmp_path):
    db = tmp_path / "pilot.sqlite3"
    store = SyntheticPilotStore(db)
    pid = store.new_synthetic_participant(at=T0)
    with pytest.raises(PilotSequenceError):
        store.snapshot("P_real_student_identity")
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE pilot_meta SET version='UNKNOWN' WHERE id=1")
    with pytest.raises(PilotSequenceError, match="schema mismatch"):
        SyntheticPilotStore(db)
    assert pid.startswith("SYN_PILOT_")


def test_mid_action_restart_retains_pending_identity(tmp_path):
    db = tmp_path / "synthetic.sqlite3"
    a = SyntheticPilotStore(db)
    pid = a.new_synthetic_participant(at=T0)
    a.start_supervised_visit(pid, visit=1, at=T0, **AUTH)
    offered = a.next_action(pid, at=T0+timedelta(seconds=1))

    b = SyntheticPilotStore(db)
    again = b.next_action(pid, at=T0+timedelta(seconds=2))
    assert again["action_id"] == offered["action_id"]
    b.mark_rendered(pid, offered["action_id"], at=T0+timedelta(seconds=3))
    b.submit(pid, offered["action_id"], "resume-once",
             {"choice_id": "C"}, at=T0+timedelta(seconds=4))
    assert SyntheticPilotStore(db).snapshot(pid)["completed_actions"] == 1


def test_simultaneous_next_action_keeps_single_pending_offer(tmp_path):
    db = tmp_path / "synthetic.sqlite3"
    store = SyntheticPilotStore(db)
    pid = store.new_synthetic_participant(at=T0)
    store.start_supervised_visit(pid, visit=1, at=T0, **AUTH)

    def call(_):
        return SyntheticPilotStore(db).next_action(
            pid, at=T0+timedelta(minutes=1)
        )["action_id"]

    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(call, range(12)))
    assert len(set(ids)) == 1
    with sqlite3.connect(db) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM pilot_actions WHERE pid=?", (pid,)
        ).fetchone()[0] == 1
