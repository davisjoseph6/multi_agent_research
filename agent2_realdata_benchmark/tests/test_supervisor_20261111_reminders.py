"""Research supervisor's 24-hour pre-session notifications are preview-only."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_synthetic_store import (
    SupervisorSyntheticStore, SyntheticStudyError,
)
from src.prototype.supervisor_reminder_preview import (
    MemoryOnlySupervisorReminders, due_fictional_session_reminders,
    acknowledge_fictional_reminder, dry_run,
)

DATA = Path(__file__).resolve().parents[1] / "data" / "supervisor_20261111"
T0 = datetime(2026,11,11,12,tzinfo=timezone.utc)


@pytest.fixture
def study(tmp_path):
    bank = SupervisorBank(DATA)
    db = SupervisorSyntheticStore(tmp_path, bank=bank)
    answers = {x.question_id: next(k for k in "ABCD" if k != x.correct_answer)
               for x in bank.forms["screening"]}
    record = db.register(
        contact_email="learner@example.test",
        econ_course=False, screening_answers=answers,
        consent_given=True, consent_version="fictional_v1",
        age=24, program="Synthetic", at=T0,
    )
    return db, record


def test_two_scheduled_24_hour_notices_do_not_send_real_emails(study):
    db, registered = study
    m = MemoryOnlySupervisorReminders()
    assert due_fictional_session_reminders(db,at=T0) == ()
    assert dry_run(db,m,at=T0+timedelta(days=2))["due"] == 0
    at2 = T0+timedelta(days=3)
    first = dry_run(db,m,at=at2)
    assert first["captured_and_logged"] == 1
    assert not first["real_email_sent"]
    assert dry_run(db,m,at=at2)["captured_and_logged"] == 0
    assert due_fictional_session_reminders(db,at=T0+timedelta(days=4)) == ()
    at3 = T0+timedelta(days=7)
    third = dry_run(db,m,at=at3)
    assert third["captured_and_logged"] == 1
    assert len(m.captured) == 2
    assert all(x["recipient"].endswith(".test")
               and x["synthetic_only"] for x in m.captured.values())
    with db._tx() as cx:
        from json import loads
        history=loads(cx.execute(
            "SELECT reminders_sent FROM pii.contacts"
        ).fetchone()[0])
        assert len(history) == 2
        assert all(x["transport"]=="MEMORY_ONLY_NO_REAL_EMAIL"
                   for x in history)


def test_tampered_or_expired_reminder_is_refused(study):
    db, registered = study
    at=T0+timedelta(days=3)
    notice, = due_fictional_session_reminders(db,at=at)
    with pytest.raises(SyntheticStudyError,match="tampered"):
        acknowledge_fictional_reminder(
            db, notice | {"recipient":"real@example.org"},at=at,
        )
    with pytest.raises(SyntheticStudyError,match="not currently due"):
        acknowledge_fictional_reminder(
            db,notice,at=T0+timedelta(days=4),
        )
    with pytest.raises(SyntheticStudyError,match="memory-only"):
        dry_run(db,object(),at=at)
    transport=MemoryOnlySupervisorReminders()
    with pytest.raises(SyntheticStudyError,match="real transport"):
        transport.capture(notice | {"recipient":"person@example.org"})


def test_only_noncompleted_scheduled_session_receives_preview(study):
    db, registration=study
    with db._tx() as cx:
        cx.execute("UPDATE participants SET status='withdrawn'")
    assert due_fictional_session_reminders(
        db,at=T0+timedelta(days=3)) == ()


def test_ineligible_candidate_never_creates_contact_for_reminder(tmp_path):
    b=SupervisorBank(DATA)
    db=SupervisorSyntheticStore(tmp_path,bank=b)
    all_right={x.question_id:x.correct_answer for x in b.forms["screening"]}
    result=db.register(contact_email="learner@example.test",
        econ_course=True, screening_answers=all_right,
        consent_given=True,consent_version="v1",age=24,
        program="Synthetic",at=T0)
    assert not result["eligible"]
    assert due_fictional_session_reminders(
        db,at=T0+timedelta(days=3)) == ()
    with db._tx() as cx:
        assert cx.execute(
            "SELECT COUNT(*) FROM pii.contacts"
        ).fetchone()[0] == 0
