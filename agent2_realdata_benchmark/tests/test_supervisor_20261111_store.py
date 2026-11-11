"""SQLite, privacy, scheduling and append-only acceptance for supervisor design."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_synthetic_store import (
    SupervisorSyntheticStore, SyntheticStudyError,
)

DATA = Path(__file__).resolve().parents[1] / "data" / "supervisor_20261111"
NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)


@pytest.fixture
def fixture(tmp_path):
    bank = SupervisorBank(DATA)
    store = SupervisorSyntheticStore(tmp_path, bank=bank)
    return store, bank


def screening_answers(bank, correct=0):
    rows = bank.forms["screening"]
    return {
        item.question_id: (
            item.correct_answer if i < correct
            else next(k for k in "ABCD" if k != item.correct_answer)
        )
        for i, item in enumerate(rows)
    }


def enroll(store, bank, *, email="demo@example.test", econ=False, right=0):
    return store.register(
        contact_email=email,
        econ_course=econ,
        screening_answers=screening_answers(bank, correct=right),
        consent_version="v1.0-fixture", consent_given=True,
        age=23, program="Fictional research student", at=NOW,
    )


def complete_pretest(store, bank, identity):
    ref, token = identity["fictional_learner_id"], identity["fictional_private_token"]
    for i, item in enumerate(bank.forms["pretest"]):
        current = store.next_item(ref, token)
        assert current["question_id"] == item.question_id
        assert "correct_answer" not in str(current)
        result = store.answer_assessment(
            ref, token, request_id=f"pretest_{ref}_{i}",
            item_id=item.question_id,
            choice=item.correct_answer,
            shown_at=NOW, answered_at=NOW + timedelta(seconds=1),
        )
        assert "correct" not in result
    return ref, token


def test_eight_required_tables_and_separate_pii_store(fixture):
    store, bank = fixture
    with store._tx() as db:
        names = {
            row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "config", "participants", "sessions", "learner_state",
            "events", "state_history", "surveys"
        }.issubset(names)
        separate = {
            row[0] for row in db.execute(
                "SELECT name FROM pii.sqlite_master WHERE type='table'"
            )
        }
        assert "contacts" in separate and "contacts" not in names
    assert store.research != store.contacts
    assert store.research.stat().st_mode & 0o077 == 0
    assert store.contacts.stat().st_mode & 0o077 == 0


def test_screening_exclusion_does_not_allocate_or_shift_rotation(fixture):
    store, bank = fixture
    assert not enroll(store, bank, right=6)["eligible"]
    assert not enroll(store, bank, econ=True, right=1)["eligible"]
    with store._tx() as db:
        assert db.execute("SELECT COUNT(*) FROM participants").fetchone()[0] == 0
    ids = [
        enroll(store, bank, email=f"learner{i}@example.test")
        for i in range(5)
    ]
    with store._tx() as db:
        arms = [x["grp"] for x in db.execute(
            "SELECT grp FROM participants ORDER BY learner_id"
        )]
    assert arms == ["A", "B", "C", "A", "B"]
    assert all(x["eligible"] and x["synthetic_only"] for x in ids)


def test_registration_rejects_real_contacts_and_missing_consent(fixture):
    store, bank = fixture
    with pytest.raises(SyntheticStudyError, match="invented"):
        enroll(store, bank, email="real@university.fr")
    with pytest.raises(SyntheticStudyError, match="consent"):
        store.register(
            contact_email="fictional@example.test",
            econ_course=False,
            screening_answers=screening_answers(bank),
            consent_version="v1", consent_given=False,
            age=21, program="Test", at=NOW,
        )


def test_pretest_initializes_eight_concepts_and_never_teaches(fixture):
    store, bank = fixture
    identity = enroll(store, bank)
    ref, token = complete_pretest(store, bank, identity)
    progress = store.progress(ref, token)
    assert progress["phase"] == "QUIZ"
    with store._tx() as db:
        state = store._state(db, ref)
        assert set(state["engine"]["mastery"]) == {
            f"C{i}" for i in range(1, 9)}
        assert all(x == .75 for x in state["engine"]["mastery"].values())
        assert all(x == 1 for x in state["engine"]["bloom"].values())
        events = db.execute(
            "SELECT COUNT(*) FROM events WHERE learner_id=?", (ref,)
        ).fetchone()[0]
        history = db.execute(
            "SELECT COUNT(*) FROM state_history WHERE learner_id=?", (ref,)
        ).fetchone()[0]
        assert events == history == 24  # 8 screen, 16 pretest
    assert store.next_item(ref, token)["question_id"] == "QZ_C1_L1_01"
    with pytest.raises(SyntheticStudyError, match="token"):
        store.progress(ref, "wrong"*12)


def test_quiz_question_and_reading_recovery_commit_atomically(fixture):
    store, bank = fixture
    identity = enroll(store, bank)
    ref, token = complete_pretest(store, bank, identity)
    # All pretest answers correct, so the greedy policy starts at C1.
    for i in range(2):
        item = store.next_item(ref, token)
        assert item["kind"] == "question"
        assert item["question_id"].startswith("QZ_")
        source = bank.get(item["question_id"], form="practice")
        wrong = next(k for k in "ABCD" if k != source.correct_answer)
        assert store.answer_quiz(
            ref, token, request_id=f"wrong_q_{i:03d}",
            item_id=item["question_id"], choice=wrong,
            shown_at=NOW, answered_at=NOW,
        )["accepted"]
    # A wrong-answer run on the first concept activates recovery.
    next_step = store.next_item(ref, token)
    assert next_step["kind"] == "recovery"
    assert next_step["action"] == "CONCEPT_SUMMARY"
    assert next_step["content_status"] == "REQUIRES_INDEPENDENT_REVIEW"
    with pytest.raises(SyntheticStudyError, match="pending"):
        store.answer_quiz(
            ref, token, request_id="forged_next_regular",
            item_id="QZ_C1_L1_06", choice="A",
            shown_at=NOW, answered_at=NOW,
        )
    store.answer_quiz(
        ref, token, request_id="summary_0001",
        item_id=None, choice=None,
        shown_at=NOW, answered_at=NOW,
    )
    drop = store.next_item(ref, token)
    assert drop["action"] == "DROP_2"
    assert len(drop["options"]) == 2
    assert "correct_answer" not in drop
    source = bank.get(drop["question_id"], form="practice")
    store.answer_quiz(
        ref, token, request_id="drop2_correct_1",
        item_id=drop["question_id"], choice=source.correct_answer,
        shown_at=NOW, answered_at=NOW,
    )
    with store._tx() as db:
        n = db.execute(
            "SELECT COUNT(*) FROM events WHERE learner_id=?", (ref,)
        ).fetchone()[0]
        h = db.execute(
            "SELECT COUNT(*) FROM state_history WHERE learner_id=?", (ref,)
        ).fetchone()[0]
        assert n == h == 29  # 24 before quiz + 3 questions + 2 recovery
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            db.execute("DELETE FROM events WHERE learner_id=?", (ref,))
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            db.execute("UPDATE state_history SET state_json='{}'")


def test_session_schedule_six_item_survey_and_no_early_next_session(fixture):
    store, bank = fixture
    identity = enroll(store, bank)
    ref, token = complete_pretest(store, bank, identity)
    for i in range(20):
        item = store.next_item(ref, token)
        source = bank.get(item["question_id"], form="practice")
        store.answer_quiz(
            ref, token, request_id=f"regular_{i:03d}",
            item_id=item["question_id"], choice=source.correct_answer,
            shown_at=NOW, answered_at=NOW,
        )
    assert store.progress(ref, token)["phase"] == "SURVEY"
    with pytest.raises(SyntheticStudyError, match="six validated"):
        store.submit_survey(
            ref, token, values=(1,2,3,4,5,8), time_ms=1000,
            request_id="bad_survey", at=NOW,
        )
    report = store.submit_survey(
        ref, token, values=(1,2,3,4,5,6), time_ms=1000,
        request_id="survey_s1", at=NOW,
    )
    assert report["session_completed"] == 1
    assert store.progress(ref, token)["phase"] == "WAITING_NEXT_SESSION"
    with pytest.raises(SyntheticStudyError, match="date"):
        store.open_next_session(ref, token, at=NOW + timedelta(days=1))
    report = store.open_next_session(ref, token, at=NOW + timedelta(days=4))
    assert report["session_started"] == 2
    assert store.progress(ref, token)["phase"] == "QUIZ"
    with store._tx() as db:
        vals = db.execute("SELECT Q1,Q2,Q3,Q4,Q5,Q6 FROM surveys").fetchone()
        assert tuple(vals) == (1,2,3,4,5,6)


def test_recontact_does_not_leak_into_deidentified_research_export(fixture):
    store, bank = fixture
    identity = enroll(store, bank, email="not-real@example.test")
    ref, token = complete_pretest(store, bank, identity)
    rows = store.export_anonymous_events(ref=ref, token=token)
    assert len(rows) == 24
    assert all("email" not in row and "token_hash" not in row
               for row in rows)
    assert "not-real@example.test" not in str(rows)
    assert all(row["learner_id"] == ref for row in rows)


def test_missed_visit_reschedule_within_48_hours_and_remove_after_two(fixture):
    store, bank = fixture
    identity = enroll(store, bank)
    ref, token = complete_pretest(store, bank, identity)
    for i in range(20):
        item = store.next_item(ref, token)
        source = bank.get(item["question_id"], form="practice")
        store.answer_quiz(
            ref, token, request_id=f"regular_{i:03d}",
            item_id=item["question_id"], choice=source.correct_answer,
            shown_at=NOW, answered_at=NOW,
        )
    store.submit_survey(
        ref, token, values=(3,3,3,3,3,3), time_ms=1000,
        request_id="survey_s1", at=NOW,
    )
    with pytest.raises(SyntheticStudyError, match="two days"):
        store.mark_missed(
            ref, token, at=NOW + timedelta(days=4),
            reschedule_for=NOW + timedelta(days=7),
        )
    first = store.mark_missed(
        ref, token, at=NOW + timedelta(days=4),
        reschedule_for=NOW + timedelta(days=5),
    )
    assert first["missed_count"] == 1 and not first["removed"]
    second = store.mark_missed(
        ref, token, at=NOW + timedelta(days=5),
        reschedule_for=None,
    )
    assert second["missed_count"] == 2 and second["removed"]
    with pytest.raises(SyntheticStudyError, match="inactive"):
        store.progress(ref, token)
