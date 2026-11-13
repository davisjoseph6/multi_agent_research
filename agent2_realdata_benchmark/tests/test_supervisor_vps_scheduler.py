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


def _test_only_survey_phase(store,ref,session):
    """Create a well-formed synthetic survey boundary; no real subjects."""
    with store._tx() as db:
        row=db.execute("SELECT state_json FROM learner_state WHERE learner_id=?",
                       (ref,)).fetchone()
        state=json.loads(row["state_json"])
        state["phase"]="SURVEY"
        state["session"]=session
        db.execute(
            "UPDATE learner_state SET session_no=?,step='SURVEY',"
            "step_index=0,state_json=? WHERE learner_id=?",
            (session,json.dumps(state),ref),
        )
        db.execute(
            "UPDATE sessions SET status='in_progress',started_at=? "
            "WHERE learner_id=? AND session_no=?",
            (iso(T + timedelta(days=4*(session-1))),ref,session),
        )


def test_late_first_session_completion_cannot_shortcut_to_session_two(tmp_path):
    """Protect 3-day minimum even if a learner resumes an unfinished session."""
    from src.prototype.supervisor_synthetic_store import iso,SyntheticStudyError
    store,intake,token,ref=setup(tmp_path)
    _test_only_survey_phase(store,ref,1)
    completed=T+timedelta(days=3,hours=8)
    store.submit_survey(ref,token,values=(4,4,4,4,4,4),
                        time_ms=1000,request_id="late_survey_1",at=completed)
    with store._tx() as db:
        row=db.execute("SELECT scheduled_for FROM sessions WHERE learner_id=? "
                       "AND session_no=2",(ref,)).fetchone()
    assert row["scheduled_for"]==iso(completed+timedelta(days=3))
    try:
        store.open_next_session(ref,token,completed+timedelta(days=2))
    except SyntheticStudyError as exc:
        assert "date has not arrived" in str(exc)
    else:
        raise AssertionError("session started before minimum 3-day interval")


def test_late_second_session_completion_shifts_session_three_not_earlier(tmp_path):
    from src.prototype.supervisor_synthetic_store import iso
    store,_,token,ref=setup(tmp_path)
    _test_only_survey_phase(store,ref,2)
    completed=T+timedelta(days=7,hours=12)
    store.submit_survey(ref,token,values=(1,2,3,4,5,6),
                        time_ms=2000,request_id="late_survey_2",at=completed)
    with store._tx() as db:
        planned=db.execute(
            "SELECT scheduled_for FROM sessions WHERE learner_id=? AND session_no=3",
            (ref,),
        ).fetchone()["scheduled_for"]
    assert planned==iso(completed+timedelta(days=3))


def test_on_time_completion_preserves_original_day_four_and_day_eight(tmp_path):
    from src.prototype.supervisor_synthetic_store import iso
    store,_,token,ref=setup(tmp_path)
    _test_only_survey_phase(store,ref,1)
    store.submit_survey(ref,token,values=(4,4,4,4,4,4),
                        time_ms=1000,request_id="ontime_survey_1",
                        at=T+timedelta(minutes=25))
    with store._tx() as db:
        schedule=db.execute(
            "SELECT session_no,scheduled_for FROM sessions WHERE learner_id=? "
            "ORDER BY session_no",(ref,),
        ).fetchall()
    assert schedule[1]["scheduled_for"]==iso(T+timedelta(days=4))
    assert schedule[2]["scheduled_for"]==iso(T+timedelta(days=8))
