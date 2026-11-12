"""Operational reminder queue is isolated, retryable and session-scoped."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_operational_intake import OperationalIntake
from src.prototype.supervisor_operational_scheduler import reconcile
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore

DATA=Path(__file__).resolve().parents[1]/"data"/"supervisor_20261111"
T=datetime(2026,11,12,12,tzinfo=timezone.utc)


def setup(tmp_path):
    store=SupervisorSyntheticStore(tmp_path,bank=SupervisorBank(DATA),
                                   operational=True)
    intake=OperationalIntake(store,programs=("Test student program",))
    token=intake.issue("test-reminder@example.example",at=T,allow_example=True)
    intake.consent(token,checks=[True]*5,optional=False,language="fr",at=T)
    answers={
        q.question_id:(q.correct_answer if i<4 else next(
            key for key in "ABCD" if key!=q.correct_answer))
        for i,q in enumerate(store.bank.forms["screening"])
    }
    intake.screening(token,answers=answers,at=T)
    intake.register(token,age=24,program="Test student program",at=T)
    learner=intake.learner(token,at=T)
    return store,intake,token,learner


def set_waiting(store,learner):
    # Test-only fixture: earlier study transitions are already covered by the
    # 465-step trace oracle and complete three-session Chromium test.
    with store._tx() as db:
        row=db.execute("SELECT state_json FROM learner_state "
                       "WHERE learner_id=?",(learner,)).fetchone()
        state=json.loads(row["state_json"])
        state["phase"]="WAITING_NEXT_SESSION"
        state["session"]=1
        db.execute(
            "UPDATE learner_state SET step='WAITING_NEXT_SESSION',session_no=1,"
            "state_json=? WHERE learner_id=?",
            (json.dumps(state),learner),
        )


def test_reminder_only_after_prior_session_and_exactly_one_per_visit(tmp_path):
    store,_,token,ref=setup(tmp_path)
    mail=[]
    send=lambda to,subject,body:mail.append((to,subject,body))
    # No Session 2 communication while the learner is in PRETEST.
    assert reconcile(store,at=T+timedelta(days=3),
                     grace_hours=6,send=send)["reminders_sent"]==0
    set_waiting(store,ref)
    today=T+timedelta(days=3)
    first=reconcile(store,at=today,grace_hours=6,send=send)
    assert first["reminders_sent"]==1
    assert len(mail)==1
    assert mail[0][0]=="test-reminder@example.example"
    assert "Europe/Paris" in mail[0][2]
    second=reconcile(store,at=today+timedelta(minutes=5),
                     grace_hours=6,send=send)
    assert second["reminders_sent"]==0
    assert len(mail)==1
    assert "test-reminder" not in str(second)
    with store._tx() as db:
        row=db.execute("SELECT status,attempts FROM pii.reminder_outbox").fetchone()
        assert (row["status"],row["attempts"])==("sent",1)


def test_email_delivery_failure_retries_without_marking_sent(tmp_path):
    store,_,_,ref=setup(tmp_path)
    set_waiting(store,ref)
    def failing(*_):
        raise OSError("simulated network loss")
    first=reconcile(store,at=T+timedelta(days=3),
                    grace_hours=12,send=failing)
    assert first["delivery_failures"]==1
    with store._tx() as db:
        row=db.execute("SELECT status,attempts FROM pii.reminder_outbox").fetchone()
        assert (row["status"],row["attempts"])==("pending",1)
    deliveries=[]
    second=reconcile(store,at=T+timedelta(days=3,minutes=30),
                     grace_hours=12,send=lambda *v:deliveries.append(v))
    assert second["reminders_sent"]==1
    assert len(deliveries)==1
    with store._tx() as db:
        row=db.execute("SELECT status,attempts FROM pii.reminder_outbox").fetchone()
        assert (row["status"],row["attempts"])==("sent",2)


def test_reschedule_generates_new_reminder_then_second_miss_revokes_link(tmp_path):
    store,intake,token,ref=setup(tmp_path)
    set_waiting(store,ref)
    emails=[]
    send=lambda *v:emails.append(v)
    assert reconcile(store,at=T+timedelta(days=3),
                     grace_hours=6,send=send)["reminders_sent"]==1
    detected=T+timedelta(days=4,hours=7)
    first=reconcile(store,at=detected,grace_hours=6,send=send)
    assert first["missed_once"]==1
    next_reminder=detected+timedelta(days=1)
    again=reconcile(store,at=next_reminder,
                    grace_hours=6,send=send)
    assert again["reminders_sent"]==1
    assert len(emails)==2
    with store._tx() as db:
        times=[r["scheduled_for"] for r in db.execute(
            "SELECT scheduled_for FROM pii.reminder_outbox "
            "ORDER BY scheduled_for"
        )]
        assert len(set(times))==2
    removed=reconcile(store,at=detected+timedelta(days=2,hours=7),
                      grace_hours=6,send=send)
    assert removed["removed_after_two_misses"]==1
    with store._tx() as db:
        assert db.execute("SELECT status FROM participants "
                          "WHERE learner_id=?",(ref,)).fetchone()[0]=="removed"
        assert db.execute("SELECT COUNT(*) FROM pii.invitations "
                          "WHERE learner_id=?",(ref,)).fetchone()[0]==0
    try:
        intake.learner(token,at=detected+timedelta(days=3))
    except Exception:
        pass
    else:
        raise AssertionError("removed learner's token still authenticates")
