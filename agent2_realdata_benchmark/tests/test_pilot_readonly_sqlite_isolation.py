"""Fail-closed tests for query-only *synthetic* SQLite monitoring.

These tests do not touch the VPS, live candidates, human enrollment or
real participant data. Run against fresh disposable, unapproved SQLite DBs.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from src.prototype.pilot_session_store_draft import SyntheticPilotStore
from src.prototype.pilot_three_arm_store_draft import SyntheticThreeArmPilotStore

ROOT = Path(__file__).resolve().parents[1] / "docs/rct_candidate_v1"
T0 = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
FLAGS = dict(offline_staff_authorized=True, synthetic_release_authorized=True)


def build(tmp_path):
    return SyntheticThreeArmPilotStore(
        tmp_path / "synthetic_readonly.sqlite3",
        items_path=ROOT / "items.csv",
        resources_path=ROOT / "resources.csv",
        simulations=41,
    )


def test_reader_connection_is_query_only_and_cannot_mutate(tmp_path):
    store = build(tmp_path)
    pid = store.new_synthetic_participant(arm="A", at=T0)
    with store._read_transaction() as db:
        assert db.execute("PRAGMA query_only").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM pilot_people").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            db.execute(
                "DELETE FROM pilot_people WHERE pid=?", (pid,),
            )
    assert store.snapshot(pid)["arm"] == "A"
    assert store.audit_arms()["allocated"] == {"A": 1}


def test_synthetic_monitoring_never_enters_reserved_write_transaction(
    tmp_path, monkeypatch,
):
    store = build(tmp_path)
    pid = store.new_synthetic_participant(arm="B", at=T0)

    def forbidden_write_transaction():
        raise AssertionError("read-only monitoring entered writer lock")

    # Monitoring and scoring must function without calling _transaction at
    # all; no test fixture can be changed by these operations.
    monkeypatch.setattr(store, "_transaction", forbidden_write_transaction)
    snap = store.snapshot(pid)
    assert snap["arm"] == "B"
    assert snap["completed_actions"] == 0
    assert snap["stage"] == "awaiting_visit"
    assert store.scores(pid)["pretest"]["answered"] == 0
    assert store.audit_arms()["allocated"] == {"B": 1}


def test_readers_remain_available_while_other_client_reserves_writer_lock(tmp_path):
    store = build(tmp_path)
    pid = store.new_synthetic_participant(arm="C", at=T0)
    with sqlite3.connect(store.path, isolation_level=None, timeout=1) as writer:
        writer.execute("BEGIN IMMEDIATE")
        try:
            snap = store.snapshot(pid)
            assert snap["arm"] == "C"
            assert snap["fictional_only"]
            assert store.scores(pid)["posttest"]["answered"] == 0
            assert store.audit_arms()["allocated"] == {"C": 1}
        finally:
            writer.rollback()


def test_atomic_arm_snapshot_includes_persisted_action_and_score(tmp_path):
    store = build(tmp_path)
    pid = store.new_synthetic_participant(arm="A", at=T0)
    store.start_supervised_visit(pid, visit=1, at=T0, **FLAGS)
    at = T0 + timedelta(seconds=1)
    action = store.next_action(pid, at=at)
    assert action["action"] == "QUESTION"
    assert store.mark_rendered(pid, action["action_id"], at=at)["accepted"]
    response = {"choice_id": action["question"]["options"][0][0]}
    assert store.submit(
        pid, action["action_id"], "read-only-test-1", response, at=at,
    )["accepted"]
    snap = store.snapshot(pid)
    assert snap["arm"] == "A"
    assert snap["index"] == 1
    assert snap["completed_actions"] == 1
    assert snap["unique_practice_used"] == 0
    assert snap["recovery_offered"] == 0
    assert store.scores(pid)["pretest"]["answered"] == 1
    assert not snap["approved_for_humans"]
    assert store.audit_arms()["completed_actions_by_arm"]["A"]["QUESTION"] == 1


def test_base_synthetic_store_counts_use_read_only_connection(tmp_path, monkeypatch):
    store = SyntheticPilotStore(tmp_path / "base_synthetic.sqlite3")
    pid = store.new_synthetic_participant(at=T0)
    monkeypatch.setattr(
        store, "_transaction",
        lambda: (_ for _ in ()).throw(AssertionError("writer lock used")),
    )
    snap = store.snapshot(pid)
    assert snap["pid"] == pid
    assert snap["completed_actions"] == 0
    assert snap["fictional_only"]
