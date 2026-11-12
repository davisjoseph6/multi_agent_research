"""Offline synthetic admin and end-of-collection lifecycle tests."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import os
import pytest

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_synthetic_store import (
    SupervisorSyntheticStore, SyntheticStudyError, iso,
)
from scripts.supervisor_gdpr_admin import (
    export_points, close_fictional_collection, private_folder,
)
from src.prototype.supervisor_fictional_backup import backup_private_fictional

NOW=datetime(2026,11,12,12,tzinfo=timezone.utc)
DATA=Path(__file__).resolve().parents[1]/"data"/"supervisor_20261111"


@pytest.fixture
def store(tmp_path):
    root=tmp_path/"state";root.mkdir(mode=0o700)
    return SupervisorSyntheticStore(root,bank=SupervisorBank(DATA))


def enroll(store,email="one@example.test"):
    bank=store.bank
    answers={
        item.question_id:next(
            v for v in "ABCD" if v!=item.correct_answer
        ) for item in bank.forms["screening"]
    }
    return store.register(
        contact_email=email,econ_course=False,screening_answers=answers,
        consent_version="v1.0",consent_given=True,consent_lang="en",
        open_data_consent=False,age=24,
        program="Synthetic classroom demonstration",at=NOW,
    )


def test_local_admin_refuses_world_readable_state_folder(tmp_path):
    p=tmp_path/"unsafe";p.mkdir(mode=0o755)
    with pytest.raises(SyntheticStudyError,match="0700"):
        private_folder(p)


def test_operator_email_withdrawal_keep_retains_research_and_invalidates_token(store):
    identity=enroll(store)
    ref,token=identity["fictional_learner_id"],identity["fictional_private_token"]
    result=store.offline_admin_withdraw(
        ref,delete=False,at=NOW+timedelta(days=1),channel="email",
    )
    assert result["withdrawn"] and not result["data_deleted"]
    assert not result["real_email_sent"]
    with store._tx() as db:
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0]==8
        assert db.execute("SELECT status FROM participants").fetchone()["status"]=="withdrawn"
    with pytest.raises(SyntheticStudyError,match="token"):
        store.progress(ref,token)


def test_operator_email_deletion_has_one_minimal_audit_log(store):
    identity=enroll(store)
    ref=identity["fictional_learner_id"]
    result=store.offline_admin_withdraw(
        ref,delete=True,at=NOW+timedelta(days=1),channel="email",
    )
    assert result["data_deleted"]
    with store._tx() as db:
        assert db.execute("SELECT COUNT(*) FROM pii.contacts").fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM participants").fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0]==0
        log=db.execute("SELECT learner_id,channel FROM deletion_log").fetchall()
        assert len(log)==1 and log[0]["channel"]=="email"
        assert log[0]["learner_id"]==ref


def test_points_export_only_completed_and_no_group_or_answers(store,tmp_path):
    first=enroll(store)
    second=enroll(store,email="two@example.test")
    with store._tx() as db:
        db.execute(
            "UPDATE participants SET status='completed',status_changed_at=? "
            "WHERE learner_id=?",
            (iso(NOW+timedelta(days=8)),first["fictional_learner_id"]),
        )
    folder=tmp_path/"reports";folder.mkdir(mode=0o700)
    target=folder/"points_export.csv"
    assert export_points(store,target)==1
    assert target.stat().st_mode & 0o077==0
    with target.open(newline="",encoding="utf-8") as handle:
        rows=list(csv.DictReader(handle))
    assert rows==[{"email":"one@example.test",
                   "completed_at":iso(NOW+timedelta(days=8))}]
    assert tuple(rows[0])==("email","completed_at")
    with pytest.raises(FileExistsError):
        export_points(store,target)


def test_end_collection_needs_export_and_closed_learners_then_removes_contact_backup(store,tmp_path):
    identity=enroll(store)
    private=tmp_path/"backups";private.mkdir(mode=0o700)
    backup_private_fictional(store,private)
    assert (private/"supervisor_fictional_contacts.sqlite3").exists()
    report_dir=tmp_path/"reports";report_dir.mkdir(mode=0o700)
    export_path=report_dir/"points_export.csv"
    with pytest.raises(SyntheticStudyError,match="points export"):
        close_fictional_collection(store,backups=private,points_file=export_path)
    assert export_points(store,export_path)==0
    with pytest.raises(SyntheticStudyError,match="sessions must be closed"):
        close_fictional_collection(store,backups=private,points_file=export_path)
    with store._tx() as db:
        db.execute(
            "UPDATE participants SET status='removed',status_changed_at=?",
            (iso(NOW+timedelta(days=10)),),
        )
    response=close_fictional_collection(
        store,backups=private,points_file=export_path,
    )
    assert response["fictional_contacts_deleted"]==1
    assert not response["physical_media_wipe_certified"]
    assert not (private/"supervisor_fictional_contacts.sqlite3").exists()
    assert (private/"supervisor_fictional_study.sqlite3").exists()
    with store._tx() as db:
        assert db.execute("SELECT COUNT(*) FROM pii.contacts").fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM participants").fetchone()[0]==1
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0]==8
