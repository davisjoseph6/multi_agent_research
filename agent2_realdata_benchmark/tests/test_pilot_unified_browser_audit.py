"""Read-only audit against one actual three-arm unified fictional SQLite cohort."""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import secrets
import sqlite3
import uuid

import pytest

from scripts.pilot_unified_browser_audit import (
    FictionalAuditError, audit_fictional_browser,
)
from src.prototype.pilot_unified_fictional_browser import (
    FIXTURE_IDS, FixtureClock, SYNTHETIC_EPOCH,
    advance_unified_fictional_visit, ensure_unified_fictional_roster,
)
from src.prototype.pilot_unified_sqlite_synthetic import UnifiedSyntheticStudyStore
from src.prototype.study_v2 import RECOVERY_ACTIONS

CONTENT = Path(__file__).resolve().parents[1] / "docs" / "rct_candidate_v1"
CONSENT_HASH = sha256(b"UNAPPROVED_SYNTHETIC_BROWSER_INFORMATION").hexdigest()
SCREENING = "UNIFIED_BROWSER_SYNTHETIC_SCREENING_V1"


def setup_cohort(tmp_path):
    clock = FixtureClock()
    operator, auditor = secrets.token_bytes(32), secrets.token_bytes(32)
    store = UnifiedSyntheticStudyStore(
        tmp_path / "fictional_admission.sqlite3",
        consent_sha256=CONSENT_HASH, screening_version=SCREENING,
        operator_key=operator, auditor_key=auditor,
        clock=clock, items_path=CONTENT / "items.csv",
        resources_path=CONTENT / "resources.csv", simulations=41,
    )
    roster = ensure_unified_fictional_roster(
        store, operator, screening_version=SCREENING,
        information_sha256=CONSENT_HASH,
    )
    return store, roster, operator, auditor, clock


def finish_one(store, roster, operator, clock, fixture):
    pid = roster[fixture]
    learner, private_arm = store.operator_lookup(operator, pid)
    for visit in (1, 2, 3):
        if visit > 1:
            result = advance_unified_fictional_visit(
                store, operator, fixture, roster, clock,
            )
            assert result["visit_started"] == visit
        for _ in range(70):
            state = store.learning.snapshot(learner)
            if state["stage"] in ("awaiting_visit", "complete"):
                break
            at = (SYNTHETIC_EPOCH
                  + timedelta(days=4 * (visit - 1),
                              minutes=state["completed_actions"] + 1))
            action = store.learning.next_action(learner, at=at)
            store.learning.mark_rendered(learner, action["action_id"], at=at)
            if action["action"] in ("QUESTION", "DROP_2"):
                response = {"choice_id": action["question"]["options"][0][0]}
            elif action["action"] == "MVAS":
                response = {"rating": 30}
            else:
                assert action["action"] in RECOVERY_ACTIONS
                response = {"status": "completed"}
            accepted = store.learning.submit(
                learner, action["action_id"], uuid.uuid4().hex,
                response, at=at,
            )
            assert accepted["accepted"]
        else:
            pytest.fail("fictional visit did not end")
    assert advance_unified_fictional_visit(
        store, operator, fixture, roster, clock, finish_final=True,
    )["visits_finished"] == 3
    assert store.operator_lookup(operator, pid)[1] == private_arm


def test_audit_is_read_only_and_marks_partial_fictional_cohort(tmp_path):
    store, roster, operator, auditor, clock = setup_cohort(tmp_path)
    path = store.path
    before = sha256(path.read_bytes()).hexdigest()
    report = audit_fictional_browser(path)
    after = sha256(path.read_bytes()).hexdigest()
    assert after == before
    assert report["result"] == "PASS_SYNTHETIC_ONLY"
    assert report["displayed_fixtures"] == 3
    assert report["fictional_cohort"] == 9
    assert not report["all_three_complete"]
    assert report["total_questions_completed"] == 0
    assert report["total_mvas_completed"] == 0
    assert all(report["fictional_roster"][alias]["current_visit"] == 1
               for alias in FIXTURE_IDS)
    assert not report["human_enrollment_authorized"]
    assert report["no_study_records_or_assignments_exported"]
    full_report = json.dumps(report, sort_keys=True)
    assert "SYN_ADMISSION_" not in full_report
    assert "SYN_PILOT_" not in full_report
    assert "private_invitation" not in full_report
    assert "allocated_by_arm" not in full_report
    assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"


def test_audit_tracks_one_completed_and_then_all_completed(tmp_path):
    store, roster, operator, auditor, clock = setup_cohort(tmp_path)
    finish_one(store, roster, operator, clock, "F1")
    partial = audit_fictional_browser(store.path)
    assert partial["result"] == "PASS_SYNTHETIC_ONLY"
    assert partial["fictional_roster"]["F1"] == {
        "learning_stage": "complete", "current_visit": 3,
        "learning_visits_finished": 3,
        "attendance_visits_finished": 3,
        "questions_completed": 87, "mvas_completed": 6,
        "fully_finished": True,
    }
    assert not partial["all_three_complete"]
    assert not partial["fictional_roster"]["F2"]["fully_finished"]
    assert not partial["fictional_roster"]["F3"]["fully_finished"]
    finish_one(store, roster, operator, clock, "F2")
    finish_one(store, roster, operator, clock, "F3")
    complete = audit_fictional_browser(store.path)
    assert complete["result"] == "PASS_SYNTHETIC_ONLY"
    assert complete["all_three_complete"]
    assert complete["total_questions_completed"] == 261
    assert complete["total_mvas_completed"] == 18
    assert all(item["fully_finished"]
               for item in complete["fictional_roster"].values())
    assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"


def test_audit_rejects_foreign_and_missing_database(tmp_path):
    with pytest.raises(FictionalAuditError):
        audit_fictional_browser(tmp_path / "human_study.sqlite3")
    with pytest.raises(FictionalAuditError):
        audit_fictional_browser(tmp_path / "fictional_admission.sqlite3")
    store, roster, operator, auditor, clock = setup_cohort(tmp_path)
    alias = tmp_path / "alias"
    alias.symlink_to(store.path)
    with pytest.raises(FictionalAuditError):
        audit_fictional_browser(alias)


def test_audit_refuses_mutated_unified_config(tmp_path):
    store, roster, operator, auditor, clock = setup_cohort(tmp_path)
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE unified_config SET value=? WHERE id=1",
                   ('{"version":"HUMAN"}',))
    with pytest.raises(FictionalAuditError):
        audit_fictional_browser(store.path)


def test_audit_refuses_tampered_concealed_arm_and_chain(tmp_path):
    store, roster, operator, auditor, clock = setup_cohort(tmp_path)
    pid = roster["F1"]
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE unified_links SET arm='Z' WHERE admission_pid=?",
                   (pid,))
    with pytest.raises(FictionalAuditError):
        audit_fictional_browser(store.path)
    with sqlite3.connect(store.path) as db:
        true_arm = db.execute(
            "SELECT arm FROM admission_slots WHERE pid=?", (pid,),
        ).fetchone()[0]
        db.execute("UPDATE unified_links SET arm=? WHERE admission_pid=?",
                   (true_arm, pid))
        db.execute("UPDATE admission_events SET kind='fabricated' WHERE seq=1")
    with pytest.raises(FictionalAuditError):
        audit_fictional_browser(store.path)
