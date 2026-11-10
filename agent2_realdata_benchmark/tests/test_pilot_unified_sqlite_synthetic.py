"""Atomic synthetic single-file admission + learning engineering regression.

All participants, times, content and staff capabilities here are fictional.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import secrets
import sqlite3
import uuid

import pytest

from scripts.pilot_integrated_synthetic_journey import _response
from src.prototype.pilot_unified_sqlite_synthetic import (
    UnifiedSyntheticError, UnifiedSyntheticStudyStore,
)
from src.prototype.pilot_admission_controls_draft import AdmissionDenied
from src.prototype.pilot_session_flow_draft import PilotSequenceError


CONTENT = Path(__file__).resolve().parents[1] / "docs" / "rct_candidate_v1"
HASH = sha256(b"FAKE_UNAPPROVED_CONSENT").hexdigest()
SCREENING = "SYNTHETIC_SCREENING_V1"


class Clock:
    def __init__(self):
        self.value = datetime(2026, 11, 20, 9, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def at(self, value):
        self.value = value


def setup(tmp_path):
    operator = secrets.token_bytes(32)
    auditor = secrets.token_bytes(32)
    clock = Clock()
    params = dict(
        consent_sha256=HASH, screening_version=SCREENING,
        operator_key=operator, auditor_key=auditor,
        clock=clock, simulations=41,
        items_path=CONTENT / "items.csv",
        resources_path=CONTENT / "resources.csv",
    )
    store = UnifiedSyntheticStudyStore(
        tmp_path / "fictional_admission.sqlite3", **params,
    )
    return store, clock, operator, auditor, params


def screened(store, operator):
    invite = store.issue_invitation(operator)
    store.screen(operator, invite["synthetic_pid"], eligible=True,
                 screening_version=SCREENING)
    return invite


def test_atomic_consent_learning_provisioning_retries_and_faults(tmp_path):
    store, clock, operator, auditor, params = setup(tmp_path)
    invitation = screened(store, operator)
    token, pid = invitation["private_invitation"], invitation["synthetic_pid"]
    with pytest.raises(AdmissionDenied):
        store.operator_lookup(auditor, pid)
    for stage in ("after_allocation", "after_learning"):
        with pytest.raises(UnifiedSyntheticError, match="injected"):
            store.consent_and_create(token, agreed=True,
                                    information_sha256=HASH, fail_at=stage)
        with sqlite3.connect(store.path) as db:
            assert db.execute("SELECT COUNT(*) FROM unified_links").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM pilot_people").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM admission_slots WHERE pid IS NOT NULL").fetchone()[0] == 0
            assert db.execute("SELECT status FROM admission_people WHERE pid=?", (pid,)).fetchone()[0] == "eligible"
    created = store.consent_and_create(
        token, agreed=True, information_sha256=HASH,
    )
    assert created["created"] and not created["human_enrollment_authorized"]
    assert store.consent_and_create(
        token, agreed=True, information_sha256=HASH,
    )["created"] is False
    learning_pid, arm = store.operator_lookup(operator, pid)
    assert learning_pid.startswith("SYN_PILOT_") and arm in "ABC"
    assert "arm" not in store.admission.participant_status(token)
    assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"
    reopened = UnifiedSyntheticStudyStore(store.path, **params)
    assert reopened.operator_lookup(operator, pid) == (learning_pid, arm)
    assert reopened.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"


def test_atomic_visit_start_rolls_back_both_subsystems(tmp_path):
    store, clock, operator, auditor, _ = setup(tmp_path)
    invite = screened(store, operator)
    store.consent_and_create(
        invite["private_invitation"], agreed=True, information_sha256=HASH,
    )
    with pytest.raises(UnifiedSyntheticError, match="injected"):
        store.start_visit(operator, invite["synthetic_pid"], 1,
                          fail_at="after_attendance")
    learning_pid, _ = store.operator_lookup(operator, invite["synthetic_pid"])
    assert store.learning.snapshot(learning_pid)["visits_started"] == 0
    assert store.admission.participant_status(invite["private_invitation"])["visits_started"] == 0
    assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"
    assert store.start_visit(operator, invite["synthetic_pid"], 1)["accepted"]
    with pytest.raises(UnifiedSyntheticError):
        store.finish_visit(operator, invite["synthetic_pid"], 1)
    assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"


def test_complete_nine_fictional_people_three_atomic_visit_boundaries(tmp_path):
    store, clock, operator, auditor, params = setup(tmp_path)
    people = []
    assignments = Counter()
    for _ in range(9):
        invitation = screened(store, operator)
        store.consent_and_create(
            invitation["private_invitation"], agreed=True,
            information_sha256=HASH,
        )
        learning_pid, arm = store.operator_lookup(
            operator, invitation["synthetic_pid"],
        )
        assignments[arm] += 1
        people.append((invitation["synthetic_pid"], learning_pid, arm))
    assert all(assignments[arm] >= 1 for arm in "ABC")

    initial = clock.value
    completed = 0
    for visit in (1, 2, 3):
        start = initial + timedelta(days=4 * (visit - 1))
        clock.at(start)
        for pid, _, _ in people:
            store.start_visit(operator, pid, visit)
        for pid, learning_pid, _ in people:
            for step in range(65):
                snap = store.learning.snapshot(learning_pid)
                if snap["stage"] in ("awaiting_visit", "complete"):
                    break
                at = start + timedelta(minutes=step + 1)
                action = store.learning.next_action(learning_pid, at=at)
                assert action["synthetic_only"]
                store.learning.mark_rendered(learning_pid, action["action_id"], at=at)
                request_id = uuid.uuid4().hex
                response = _response(action)
                result = store.learning.submit(
                    learning_pid, action["action_id"],
                    request_id, response, at=at,
                )
                assert result["accepted"] and not result["replayed"]
            else:
                pytest.fail("synthetic visit did not finish its learning steps")
            assert store.learning.snapshot(learning_pid)["visits_finished"] == visit
            completed += 1

        clock.at(start + timedelta(minutes=70))
        for pid, learning_pid, _ in people:
            if visit == 1 and pid == people[0][0]:
                with pytest.raises(UnifiedSyntheticError, match="injected"):
                    store.finish_visit(
                        operator, pid, visit, fail_at="after_attendance",
                    )
                with sqlite3.connect(store.path) as db:
                    n = db.execute(
                        "SELECT COUNT(*) FROM admission_visits "
                        "WHERE pid=? AND finished_at IS NOT NULL", (pid,),
                    ).fetchone()[0]
                    assert n == 0
            store.finish_visit(operator, pid, visit)
        assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"
        reopened = UnifiedSyntheticStudyStore(store.path, **params)
        assert reopened.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"
    assert completed == 27
    result = store.audit(auditor)
    assert result["fictional_active_records"] == 9
    assert result["fictional_learning_links"] == 9
    assert result["single_database_combined_writes_atomic"]
    assert not result["cross_database_atomicity"]
    assert result["single_sqlite_file"]
    assert not result["human_enrollment_authorized"]


def test_atomic_withdrawal_revokes_existing_pending_action(tmp_path):
    store, clock, operator, auditor, _ = setup(tmp_path)
    invite = screened(store, operator)
    store.consent_and_create(
        invite["private_invitation"], agreed=True,
        information_sha256=HASH,
    )
    pid = invite["synthetic_pid"]
    learner, _ = store.operator_lookup(operator, pid)
    store.start_visit(operator, pid, 1)
    at = clock.value + timedelta(minutes=1)
    pending = store.learning.next_action(learner, at=at)
    store.learning.mark_rendered(learner, pending["action_id"], at=at)
    clock.at(at + timedelta(seconds=1))
    stopped = store.withdraw(invite["private_invitation"])
    assert stopped["stopped"] and stopped["changed"]
    assert not store.withdraw(invite["private_invitation"])["changed"]
    assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"
    with pytest.raises(UnifiedSyntheticError):
        store.operator_lookup(operator, pid)
    with pytest.raises(PilotSequenceError):
        store.learning.next_action(learner, at=clock.value)
    with pytest.raises(PilotSequenceError):
        store.learning.submit(
            learner, pending["action_id"], uuid.uuid4().hex,
            _response(pending), at=clock.value,
        )
    with pytest.raises(UnifiedSyntheticError):
        store.start_visit(operator, pid, 2)
    assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"


def test_atomic_withdrawal_prior_to_consent_leaves_no_learning_record(tmp_path):
    store, _, operator, auditor, _ = setup(tmp_path)
    invite = screened(store, operator)
    result = store.withdraw(invite["private_invitation"])
    assert result["stopped"] and result["changed"]
    with pytest.raises(AdmissionDenied):
        store.consent_and_create(
            invite["private_invitation"], agreed=True,
            information_sha256=HASH,
        )
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM pilot_people").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM unified_links").fetchone()[0] == 0
    assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"


def test_rejects_unreviewed_human_database_and_policy_mismatch(tmp_path):
    store, _, operator, auditor, params = setup(tmp_path)
    with pytest.raises(AdmissionDenied):
        UnifiedSyntheticStudyStore(
            tmp_path / "human_study.sqlite3", **params,
        )
    with pytest.raises(AdmissionDenied):
        UnifiedSyntheticStudyStore(
            store.path, **{**params, "consent_sha256": "b" * 64},
        )
    assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"
