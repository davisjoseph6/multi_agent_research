"""Offline fictional backup/purge; never real identities."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_synthetic_store import (
    SupervisorSyntheticStore, SyntheticStudyError,
)
from src.prototype.supervisor_fictional_backup import (
    backup_private_fictional,purge_fake_contacts_after_collection,
)

DATA=Path(__file__).resolve().parents[1]/"data"/"supervisor_20261111"
NOW=datetime(2026,11,11,12,tzinfo=timezone.utc)


def setup(tmp_path):
    database=tmp_path/"source"
    database.mkdir(mode=0o700)
    bank=SupervisorBank(DATA)
    store=SupervisorSyntheticStore(database,bank=bank)
    screening={q.question_id:next(k for k in "ABCD" if k!=q.correct_answer)
        for q in bank.forms["screening"]}
    record=store.register(
        contact_email="fake@example.test",
        econ_course=False,screening_answers=screening,
        consent_version="offline",consent_given=True,
        age=21,program="Synthetic",at=NOW,
    )
    return store,record


def test_integrity_checked_backup_never_overwrites_or_exposes_real_contacts(tmp_path):
    store,record=setup(tmp_path)
    target=tmp_path/"private_backup"
    target.mkdir(mode=0o700)
    report=backup_private_fictional(store,target)
    assert report["kind"].startswith("FICTIONAL")
    assert not report["contains_real_contacts"]
    assert len(report["sha256"])==2
    assert all((target/name).is_file() for name in report["sha256"])
    assert (target/"fictional_backup_manifest.json").is_file()
    with sqlite3.connect(target/"supervisor_fictional_study.sqlite3") as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0]==8
        assert db.execute("SELECT COUNT(*) FROM participants").fetchone()[0]==1
    with sqlite3.connect(target/"supervisor_fictional_contacts.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]==1
    with pytest.raises(SyntheticStudyError,match="overwrite"):
        backup_private_fictional(store,target)


def test_no_contact_purge_while_active_and_delete_only_after_collection(tmp_path):
    store,record=setup(tmp_path)
    with pytest.raises(SyntheticStudyError,match="explicit"):
        purge_fake_contacts_after_collection(store,collection_closed=False)
    with pytest.raises(SyntheticStudyError,match="active"):
        purge_fake_contacts_after_collection(store,collection_closed=True)
    with store._tx() as db:
        db.execute("UPDATE participants SET status='completed'")
    assert purge_fake_contacts_after_collection(
        store,collection_closed=True)==1
    assert purge_fake_contacts_after_collection(
        store,collection_closed=True)==0
    with store._tx() as db:
        assert db.execute(
            "SELECT COUNT(*) FROM pii.contacts"
        ).fetchone()[0]==0
        assert db.execute(
            "SELECT COUNT(*) FROM events"
        ).fetchone()[0]==8
        assert db.execute(
            "SELECT COUNT(*) FROM participants"
        ).fetchone()[0]==1


def test_backup_rejects_nonprivate_destinations_and_tampered_contacts(tmp_path):
    store,record=setup(tmp_path)
    invalid=tmp_path/"world_readable"
    invalid.mkdir(mode=0o755)
    with pytest.raises(SyntheticStudyError,match="0700"):
        backup_private_fictional(store,invalid)
    private=tmp_path/"private"
    private.mkdir(mode=0o700)
    with store._tx() as db:
        db.execute(
            "UPDATE pii.contacts SET email=?",
            ("real@university.edu",),
        )
    with pytest.raises(SyntheticStudyError,match="nonfictional"):
        backup_private_fictional(store,private)
    with pytest.raises(SyntheticStudyError,match="nonfictional"):
        purge_fake_contacts_after_collection(
            store,collection_closed=True,
        )
