"""Read-only fictional acceptance audit, including corruption and refusal tests."""
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
import uuid

import pytest

from src.prototype.pilot_fictional_acceptance_audit import (
    FictionalAuditError, audit_fictional_database,
)
from src.prototype.pilot_local_browser_preview import (
    SYNTHETIC_EPOCH, advance_fictional_visit,
    ensure_three_fictional_records,
)
from src.prototype.pilot_three_arm_store_draft import SyntheticThreeArmPilotStore
from src.prototype.study_v2 import RECOVERY_ACTIONS

ROOT = Path(__file__).resolve().parents[1] / "docs/rct_candidate_v1"


def build(tmp_path):
    return SyntheticThreeArmPilotStore(
        tmp_path / "fictional_browser_preview.sqlite3",
        items_path=ROOT / "items.csv",
        resources_path=ROOT / "resources.csv",
        simulations=41,
    )


def finish_all(store):
    pids = ensure_three_fictional_records(store)
    for arm, pid in pids.items():
        for visit in (1, 2, 3):
            if visit != 1:
                assert advance_fictional_visit(store, arm)["visit"] == visit
            for _ in range(120):
                state = store.snapshot(pid)
                if state["stage"] in ("awaiting_visit", "complete"):
                    break
                now = (
                    SYNTHETIC_EPOCH
                    + timedelta(days=4*(state["session"] - 1))
                    + timedelta(minutes=state["completed_actions"] + 1)
                )
                action = store.next_action(pid, at=now)
                store.mark_rendered(pid, action["action_id"], at=now)
                kind = action["action"]
                if kind in ("QUESTION", "DROP_2"):
                    response = dict(choice_id=action["question"]["options"][0][0])
                elif kind == "MVAS":
                    response = dict(rating=99)
                else:
                    assert kind in RECOVERY_ACTIONS
                    response = dict(status="completed")
                result = store.submit(
                    pid, action["action_id"], uuid.uuid4().hex,
                    response, at=now,
                )
                assert result["accepted"]
            else:
                raise AssertionError("fictional visit did not finish")
    assert all(store.snapshot(pid)["stage"] == "complete" for pid in pids.values())
    return pids


def test_completed_browser_fixture_has_read_only_pass_audit(tmp_path):
    store = build(tmp_path)
    finish_all(store)
    before_bytes = store.path.read_bytes()
    report = audit_fictional_database(store.path)
    assert report["result"] == "PASS_SYNTHETIC_ONLY"
    assert not report["human_enrollment_authorized"]
    assert report["fictional_only"] and report["virtual_time_only"]
    assert report["not_scientific_validation"]
    assert report["sqlite_integrity"] == "ok"
    assert report["issues"] == []
    for arm in "ABC":
        outcome = report["arms"][arm]
        assert outcome["result"] == "PASS"
        assert outcome["practice_by_visit"] == [20, 20, 15]
        assert outcome["pretest_questions"] == outcome["posttest_questions"] == 16
        assert outcome["mvas_responses"] == 6
        assert outcome["fatigue_pairs"] == [[99, 99]] * 3
        assert outcome["fatigue_delta_by_visit"] == [0, 0, 0]
        assert outcome["completed_actions"] == 93 + sum(outcome["recovery_by_visit"])
        assert all(n <= 2 for n in outcome["recovery_by_visit"])
        if arm in "BC":
            assert outcome["recovery_by_visit"] == [0, 0, 0]
    assert store.path.read_bytes() == before_bytes


def test_incomplete_fictional_participants_fail_without_mutation(tmp_path):
    store = build(tmp_path)
    ensure_three_fictional_records(store)
    before = store.path.read_bytes()
    report = audit_fictional_database(store.path)
    assert report["result"] == "FAIL_SYNTHETIC"
    assert all(report["arms"][arm]["result"] == "FAIL" for arm in "ABC")
    assert any("all three visits" in reason for reason in report["issues"])
    assert all(report["arms"][arm]["fatigue_delta_by_visit"] == []
               for arm in "ABC")
    assert any("six valid M-VAS recordings" in reason for reason in report["issues"])
    assert store.path.read_bytes() == before


def test_fatigue_tamper_is_detected(tmp_path):
    store = build(tmp_path)
    pids = finish_all(store)
    with sqlite3.connect(store.path) as db:
        row = db.execute(
            "SELECT action_id,response FROM pilot_actions WHERE pid=? "
            "AND public LIKE '%mvas_pre%' LIMIT 1",
            (pids["B"],),
        ).fetchone()
        assert row is not None
        response = json.loads(row[1])
        response["rating"] = 88
        db.execute(
            "UPDATE pilot_actions SET response=? WHERE action_id=?",
            (json.dumps(response), row[0]),
        )
    report = audit_fictional_database(store.path)
    assert report["result"] == "FAIL_SYNTHETIC"
    assert any("fatigue response disagrees" in x for x in report["issues"])
    assert report["arms"]["B"]["result"] == "FAIL"


def test_wrong_path_and_symlink_refused(tmp_path):
    with pytest.raises(FictionalAuditError):
        audit_fictional_database(tmp_path / "fictional_browser_preview.sqlite3")
    junk = tmp_path / "unrelated.sqlite3"
    junk.write_bytes(b"not an actual study DB")
    with pytest.raises(FictionalAuditError):
        audit_fictional_database(junk)
    store = build(tmp_path)
    other = tmp_path / "symlink" / "fictional_browser_preview.sqlite3"
    other.parent.mkdir()
    other.symlink_to(store.path)
    with pytest.raises(FictionalAuditError):
        audit_fictional_database(other)


def test_unauthorized_extra_synthetic_record_fails(tmp_path):
    store = build(tmp_path)
    ensure_three_fictional_records(store)
    store.new_synthetic_participant(arm="B", at=SYNTHETIC_EPOCH)
    report = audit_fictional_database(store.path)
    assert report["result"] == "FAIL_SYNTHETIC"
    assert any("exactly three fictional people" in reason for reason in report["issues"])
