"""Independent forensic integrity checks on synthetic SQLite study data."""
import shutil
import sqlite3

import pytest

from scripts.step123_v4_independent_audit import IntegrityError, audit_database
from scripts.step123_v4_audited_mock import make_mock


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    database = tmp_path_factory.mktemp("v4ledger") / "synthetic.sqlite3"
    report = make_mock(database, simulations=20)
    return database, report


def tampered_copy(sample, tmp_path):
    source, _ = sample
    target = tmp_path / "damaged.sqlite3"
    shutil.copyfile(source, target)
    return target


def test_independent_passes_three_arm_complete_mock(sample):
    path, report = sample
    assert audit_database(path) == report
    assert report["participants"] == 3
    assert report["per_arm"] == {"A": 1, "B": 1, "C": 1}
    assert report["normal_question_counts"] == {
        "pretest": 48, "practice": 165, "posttest": 48, "fatigue": 9
    }
    assert report["synthetic_only"] and not report["human_evidence"]
    assert report["passed"]


def test_refuses_overwriting_synthetic_database(sample):
    path, _ = sample
    with pytest.raises(FileExistsError):
        make_mock(path)


def test_rejects_missing_database(tmp_path):
    with pytest.raises(IntegrityError, match="does not exist"):
        audit_database(tmp_path / "missing.sqlite3")


def test_rejects_incomplete_participant(sample, tmp_path):
    path = tampered_copy(sample, tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE synthetic_participants SET stage='practice' WHERE arm='B'")
    with pytest.raises(IntegrityError, match="unfinished"):
        audit_database(path)


def test_rejects_unmatched_deleted_event(sample, tmp_path):
    path = tampered_copy(sample, tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM synthetic_protocol_events WHERE seq=("
                   "SELECT seq FROM synthetic_protocol_events "
                   "WHERE event_json LIKE '%answer_recorded%' LIMIT 1)")
    with pytest.raises(IntegrityError, match="wrong event for normal question|broken event pairing"):
        audit_database(path)


def test_rejects_bank_hash_tampering(sample, tmp_path):
    path = tampered_copy(sample, tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE synthetic_participants SET item_bank_hash='tampered' WHERE arm='C'")
    with pytest.raises(IntegrityError, match="bank hash mismatch"):
        audit_database(path)


def test_rejects_untracked_response_record(sample, tmp_path):
    path = tampered_copy(sample, tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM synthetic_responses WHERE request_id=("
                   "SELECT request_id FROM synthetic_responses LIMIT 1)")
    with pytest.raises(IntegrityError, match="response/event count mismatch"):
        audit_database(path)


def test_rejects_real_identifier(sample, tmp_path):
    path = tampered_copy(sample, tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=OFF")
        db.execute("UPDATE synthetic_participants SET participant_id='REAL_PERSON' WHERE arm='B'")
    with pytest.raises(IntegrityError, match="non-synthetic|foreign-key integrity violation"):
        audit_database(path)


def test_read_only_audit_does_not_modify_database(sample):
    path, _ = sample
    original = path.read_bytes()
    audit_database(path)
    assert path.read_bytes() == original
