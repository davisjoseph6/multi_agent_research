"""Offline fixture-only verification for future pilot admission control design."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import secrets
import sqlite3

import pytest

from src.prototype.pilot_admission_controls_draft import (
    AdmissionDenied, SyntheticAdmissionStore,
)


CONSENT_HASH = "a" * 64
SCREENING = "SYNTHETIC_ELIGIBILITY_V1"


class Clock:
    def __init__(self):
        self.value = datetime(2026, 11, 20, 9, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, **kwargs):
        self.value += timedelta(**kwargs)


def setup(tmp_path):
    clock = Clock()
    operator = secrets.token_bytes(32)
    auditor = secrets.token_bytes(32)
    params = dict(
        consent_sha256=CONSENT_HASH,
        screening_version=SCREENING,
        operator_key=operator,
        auditor_key=auditor,
        clock=clock,
    )
    store = SyntheticAdmissionStore(
        tmp_path / "fictional_admission.sqlite3", **params,
    )
    return store, clock, operator, auditor, params


def activated(store, operator):
    invite = store.issue_invitation(operator)
    store.screen(
        operator, invite["synthetic_pid"], eligible=True,
        screening_version=SCREENING,
    )
    result = store.consent(
        invite["private_invitation"],
        agreed=True, information_sha256=CONSENT_HASH,
    )
    assert result["created"]
    return invite


def test_no_real_db_names_or_weak_role_keys(tmp_path):
    with pytest.raises(AdmissionDenied):
        SyntheticAdmissionStore(
            tmp_path / "study.sqlite3",
            consent_sha256=CONSENT_HASH, screening_version=SCREENING,
            operator_key=b"t" * 32, auditor_key=b"a" * 32,
        )
    with pytest.raises(AdmissionDenied):
        SyntheticAdmissionStore(
            tmp_path / "fictional_admission.sqlite3",
            consent_sha256=CONSENT_HASH, screening_version=SCREENING,
            operator_key=b"short", auditor_key=b"short",
        )
    assert not (tmp_path / "study.sqlite3").exists()


def test_offline_operator_auditor_role_separation_and_consent(tmp_path):
    store, _, operator, auditor, _ = setup(tmp_path)
    with pytest.raises(AdmissionDenied):
        store.issue_invitation(auditor)
    invite = store.issue_invitation(operator)
    assert invite["synthetic_pid"].startswith("SYN_ADMISSION_")
    assert not invite["human_enrollment_authorized"]
    token = invite["private_invitation"]
    with pytest.raises(AdmissionDenied):
        store.consent(token, agreed=True, information_sha256=CONSENT_HASH)
    with pytest.raises(AdmissionDenied):
        store.screen(
            auditor, invite["synthetic_pid"], eligible=True,
            screening_version=SCREENING,
        )
    store.screen(
        operator, invite["synthetic_pid"], eligible=True,
        screening_version=SCREENING,
    )
    for agreement, digest in ((False, CONSENT_HASH), (True, "b" * 64)):
        with pytest.raises(AdmissionDenied):
            store.consent(token, agreed=agreement, information_sha256=digest)
    accepted = store.consent(token, agreed=True, information_sha256=CONSENT_HASH)
    assert accepted == {
        "accepted": True, "created": True, "synthetic_only": True,
        "human_enrollment_authorized": False,
    }
    repeated = store.consent(token, agreed=True, information_sha256=CONSENT_HASH)
    assert repeated["accepted"] and not repeated["created"]
    public = store.participant_status(token)
    assert public["status"] == "active"
    assert "arm" not in public and "pid" not in public
    with pytest.raises(AdmissionDenied):
        store.audit(operator)
    assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"


def test_ineligible_participant_never_receives_allocation(tmp_path):
    store, _, operator, auditor, _ = setup(tmp_path)
    invite = store.issue_invitation(operator)
    store.screen(
        operator, invite["synthetic_pid"], eligible=False,
        screening_version=SCREENING,
    )
    with pytest.raises(AdmissionDenied):
        store.consent(invite["private_invitation"], agreed=True,
                      information_sha256=CONSENT_HASH)
    assert store.audit(auditor)["allocated"] == 0


def test_server_side_concurrent_randomization_balances_complete_blocks(tmp_path):
    store, _, operator, auditor, _ = setup(tmp_path)
    people = [store.issue_invitation(operator) for _ in range(36)]
    for person in people:
        store.screen(operator, person["synthetic_pid"], eligible=True,
                     screening_version=SCREENING)

    def enroll(person):
        return store.consent(person["private_invitation"], agreed=True,
                             information_sha256=CONSENT_HASH)

    with ThreadPoolExecutor(max_workers=8) as pool:
        result = list(pool.map(enroll, people))
    assert all(x["created"] for x in result)
    for person in people:
        public = store.participant_status(person["private_invitation"])
        assert "arm" not in public and public["status"] == "active"
    with sqlite3.connect(store.path) as db:
        rows = db.execute(
            "SELECT block_id,arm,pid FROM admission_slots"
        ).fetchall()
        for block in {r[0] for r in rows}:
            group = [r[1] for r in rows if r[0] == block]
            assert len(group) in (6, 9)
            assert group.count("A") == group.count("B") == group.count("C")
        assert len(set(r[2] for r in rows if r[2] is not None)) == 36
    summary = store.audit(auditor)
    assert summary["result"] == "PASS_SYNTHETIC_ONLY"
    assert summary["allocated"] == 36
    assert summary["counts_by_status"]["active"] == 36
    assert not summary["human_enrollment_authorized"]


def test_supervised_visit_order_gap_and_withdrawal(tmp_path):
    store, clock, operator, auditor, _ = setup(tmp_path)
    invite = activated(store, operator)
    pid, token = invite["synthetic_pid"], invite["private_invitation"]
    with pytest.raises(AdmissionDenied):
        store.start_visit(operator, pid, 2)
    with pytest.raises(AdmissionDenied):
        store.start_visit(auditor, pid, 1)
    assert store.start_visit(operator, pid, 1)["status"] == "started"
    with pytest.raises(AdmissionDenied):
        store.start_visit(operator, pid, 1)
    clock.advance(minutes=45)
    assert store.finish_visit(operator, pid, 1)["status"] == "finished"
    with pytest.raises(AdmissionDenied):
        store.finish_visit(operator, pid, 1)
    clock.advance(hours=71)
    with pytest.raises(AdmissionDenied):
        store.start_visit(operator, pid, 2)
    clock.advance(hours=3)
    assert store.start_visit(operator, pid, 2)["visit"] == 2
    clock.advance(minutes=50)
    store.finish_visit(operator, pid, 2)
    clock.advance(hours=121)
    with pytest.raises(AdmissionDenied):
        store.start_visit(operator, pid, 3)
    assert store.participant_status(token)["visits_finished"] == 2
    assert store.withdraw(token)["stopped"]
    assert store.withdraw(token)["stopped"]
    with pytest.raises(AdmissionDenied):
        store.start_visit(operator, pid, 3)
    assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"


def test_full_synthetic_three_visit_sequence(tmp_path):
    store, clock, operator, auditor, _ = setup(tmp_path)
    person = activated(store, operator)
    pid = person["synthetic_pid"]
    for visit in (1, 2, 3):
        if visit > 1:
            clock.advance(days=4)
        store.start_visit(operator, pid, visit)
        clock.advance(minutes=30)
        store.finish_visit(operator, pid, visit)
    assert store.participant_status(person["private_invitation"]) == {
        "status": "active",
        "visits_started": 3,
        "visits_finished": 3,
        "synthetic_only": True,
        "human_enrollment_authorized": False,
    }
    assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"


def test_event_chain_detects_mutation_and_is_not_signature(tmp_path):
    store, _, operator, auditor, _ = setup(tmp_path)
    activated(store, operator)
    assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"
    with sqlite3.connect(store.path) as db:
        db.execute(
            "UPDATE admission_events SET kind='tampered' WHERE seq=1"
        )
    failed = store.audit(auditor)
    assert failed["result"] == "FAIL_SYNTHETIC"
    assert "synthetic event hash chain invalid" in failed["issues"]
    assert not failed["scientific_or_ethics_approval"]


def test_reopen_preserves_config_and_blocks_mismatch(tmp_path):
    store, clock, operator, auditor, params = setup(tmp_path)
    activated(store, operator)
    restored = SyntheticAdmissionStore(store.path, **params)
    assert restored.audit(auditor)["allocated"] == 1
    with pytest.raises(AdmissionDenied, match="frozen protocol"):
        SyntheticAdmissionStore(
            store.path, **{**params, "consent_sha256": "b" * 64},
        )
    with pytest.raises(AdmissionDenied):
        SyntheticAdmissionStore(
            store.path, **{**params, "screening_version": ""},
        )


def test_invitation_expiry_blocks_late_consent(tmp_path):
    store, clock, operator, auditor, _ = setup(tmp_path)
    person = store.issue_invitation(operator, lifetime_hours=1)
    store.screen(operator, person["synthetic_pid"], eligible=True,
                 screening_version=SCREENING)
    clock.advance(hours=2)
    with pytest.raises(AdmissionDenied, match="expired"):
        store.consent(person["private_invitation"],
                      agreed=True, information_sha256=CONSENT_HASH)
    assert store.audit(auditor)["allocated"] == 0


def test_not_mounted_in_any_public_http_app():
    root = Path(__file__).resolve().parents[1] / "src" / "prototype"
    code = (root / "rct_candidate_api.py").read_text(encoding="utf-8")
    assert "pilot_admission_controls_draft" not in code
    code = (root / "pilot_local_browser_preview.py").read_text(encoding="utf-8")
    assert "pilot_admission_controls_draft" not in code
