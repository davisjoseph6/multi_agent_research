"""Synthetic SQLite crash/restore drills, NOT production disaster recovery.

Offline, uses a consistent online SQLite backup and entirely fictional IDs.
It tests persistence of pending actions and idempotent submissions through a
store-instance restart. It does NOT certify encrypted offsite backups, RPO,
RTO, real cloud recovery, consent, identity, staffing, or institutional GO.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.prototype.pilot_three_arm_store_draft import SyntheticThreeArmPilotStore

DATA = Path(__file__).resolve().parents[1] / "docs/rct_candidate_v1"
T0 = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
AUTH = dict(offline_staff_authorized=True, synthetic_release_authorized=True)


def make_store(path):
    return SyntheticThreeArmPilotStore(
        path,
        items_path=DATA / "items.csv",
        resources_path=DATA / "resources.csv",
        simulations=41,
    )


def test_recovery_of_rendered_pending_action_and_idempotent_response(tmp_path):
    origin = make_store(tmp_path / "original.sqlite3")
    pid = origin.new_synthetic_participant(arm="A", at=T0)
    origin.start_supervised_visit(pid, visit=1, at=T0, **AUTH)
    at = T0 + timedelta(minutes=1)

    first = origin.next_action(pid, at=at)
    assert first["stage"] == "pretest"
    origin.mark_rendered(pid, first["action_id"], at=at)
    response = {"choice_id": first["question"]["options"][0][0]}
    request_id = "SYNTHETIC_RESTART_RESPONSE_0001"
    submitted = origin.submit(
        pid, first["action_id"], request_id, response, at=at,
    )
    assert submitted["accepted"] and not submitted["replayed"]
    assert origin.scores(pid)["pretest"]["answered"] == 1

    next_time = T0 + timedelta(minutes=2)
    pending = origin.next_action(pid, at=next_time)
    assert pending["action_id"] != first["action_id"]
    origin.mark_rendered(pid, pending["action_id"], at=next_time)
    before = origin.snapshot(pid)
    saved = tmp_path / "restored.sqlite3"
    digest = origin.backup(saved)
    assert len(digest["sha256"]) == 64
    assert digest["synthetic_only"]

    # Construct a fresh store, representing complete application restart
    # from a copied, consistent SQLite backup in a separate directory.
    recovered = make_store(saved)
    assert recovered.snapshot(pid) == before
    assert recovered.scores(pid) == origin.scores(pid)
    assert recovered.next_action(pid, at=next_time) == pending
    assert recovered.submit(
        pid, first["action_id"], request_id, response, at=next_time,
    )["replayed"]

    second_response = {"choice_id": pending["question"]["options"][0][0]}
    second_req = "SYNTHETIC_RESTART_RESPONSE_0002"
    second = recovered.submit(
        pid, pending["action_id"], second_req, second_response,
        at=next_time,
    )
    assert second["accepted"] and not second["replayed"]
    assert recovered.submit(
        pid, pending["action_id"], second_req, second_response,
        at=next_time,
    )["replayed"]
    assert recovered.scores(pid)["pretest"]["answered"] == 2
    assert recovered.snapshot(pid)["completed_actions"] == 2
    assert recovered.snapshot(pid)["arm"] == "A"
    assert not recovered.snapshot(pid)["approved_for_humans"]


def test_backup_restore_keeps_three_arm_isolation_and_absence_of_credentials(tmp_path):
    original = make_store(tmp_path / "source.sqlite3")
    ids = {
        arm: original.new_synthetic_participant(arm=arm, at=T0)
        for arm in "ABC"
    }
    for pid in ids.values():
        original.start_supervised_visit(pid, visit=1, at=T0, **AUTH)
    saved = tmp_path / "restart.sqlite3"
    original.backup(saved)
    restored = make_store(saved)
    assert restored.audit_arms()["allocated"] == {"A": 1, "B": 1, "C": 1}
    assert all(
        restored.snapshot(pid)["arm"] == arm
        for arm, pid in ids.items()
    )
    assert all(
        pid.startswith("SYN_PILOT_") for pid in ids.values()
    )
    # No consent, staff identity or institutional permission can be
    # inferred from the existence of a valid synthetic backup.
    assert not restored.audit_arms()["approved_for_humans"]
