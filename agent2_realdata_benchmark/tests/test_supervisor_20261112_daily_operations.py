"""Time-dependent offline reminder and missed-session behavior."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_synthetic_store import (
    SupervisorSyntheticStore, SyntheticStudyError,
    iso, dump,
)
from src.prototype.supervisor_daily_operations import (
    reconcile_missed_fictional,dry_run_daily,
)

NOW=datetime(2026,11,12,12,tzinfo=timezone.utc)
DATA=Path(__file__).resolve().parents[1]/"data"/"supervisor_20261111"


@pytest.fixture
def fixture(tmp_path):
    store=SupervisorSyntheticStore(tmp_path,bank=SupervisorBank(DATA))
    answers={q.question_id:next(
        x for x in "ABCD" if x!=q.correct_answer
    ) for q in store.bank.forms["screening"]}
    p=store.register(
        contact_email="test@example.test",econ_course=False,
        screening_answers=answers,consent_version="v1.0",
        consent_given=True,age=23,program="Synthetic",
        at=NOW,
    )
    ref,token=p["fictional_learner_id"],p["fictional_private_token"]
    with store._tx() as db:
        state=store._state(db,ref)
        state.update(phase="WAITING_NEXT_SESSION",session=1)
        db.execute("UPDATE learner_state SET state_json=? WHERE learner_id=?",
                   (dump(state),ref))
    return store,ref,token


def test_daily_job_requires_explicit_missed_grace(fixture):
    store,ref,token=fixture
    with pytest.raises(SyntheticStudyError,match="grace"):
        reconcile_missed_fictional(store,at=NOW,grace_hours=-1)
    with pytest.raises(SyntheticStudyError,match="grace"):
        reconcile_missed_fictional(store,at=NOW,grace_hours=100)


def test_previsit_notification_only_memory_and_idempotent(fixture):
    store,ref,token=fixture
    # Session 2 scheduled four days after registering.
    report=dry_run_daily(store,at=NOW+timedelta(days=3),grace_hours=1)
    assert report["reminder_capture"]["captured_and_logged"]==1
    assert not report["real_email_sent"]
    repeated=dry_run_daily(store,at=NOW+timedelta(days=3),grace_hours=1)
    assert repeated["reminder_capture"]["captured_and_logged"]==0
    with store._tx() as db:
        log=db.execute("SELECT reminders_sent FROM pii.contacts").fetchone()[0]
        assert "session_2" in log


def test_two_missed_scheduled_dates_remove_without_email_and_keep_state(fixture):
    store,ref,token=fixture
    before=store.progress(ref,token)
    assert before["phase"]=="WAITING_NEXT_SESSION"
    at=NOW+timedelta(days=4,hours=2)
    first=reconcile_missed_fictional(store,at=at,grace_hours=1)
    assert first["status_changes"][0]["misses"]==1
    assert not first["status_changes"][0]["removed"]
    assert store.progress(ref,token)==before
    again=reconcile_missed_fictional(store,at=at,grace_hours=1)
    assert again["status_changes"]==[]
    next_run=at+timedelta(days=2,hours=2)
    second=reconcile_missed_fictional(store,at=next_run,grace_hours=1)
    assert second["status_changes"][0]["removed"] is True
    assert not second["real_email_sent"]
    with store._tx() as db:
        row=db.execute("SELECT status,missed_sessions FROM participants").fetchone()
        assert row["status"]=="removed" and row["missed_sessions"]==2
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0]==8
    with pytest.raises(SyntheticStudyError,match="token"):
        store.progress(ref,token)
