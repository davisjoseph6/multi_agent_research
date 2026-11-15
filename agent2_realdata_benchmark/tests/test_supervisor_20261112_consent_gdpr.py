"""Twelve supervisor GDPR acceptance cases (offline fictional data only).

Institutional sign-off, real sender, hosted retention and approved UI remain
independent conditions. These tests do not authorize public enrollment.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import sqlite3
import pytest

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_consent_flow import SyntheticConsentFlow
from src.prototype.supervisor_consent_texts import (
    CONSENT_VERSION, INELIGIBLE, KEEP_CONFIRMATION, DELETE_CONFIRMATION,
    DEBRIEF,
)
from src.prototype.supervisor_synthetic_store import (
    SupervisorSyntheticStore, SyntheticStudyError, dump, iso,
)

T0=datetime(2026,11,12,12,tzinfo=timezone.utc)
DATA=Path(__file__).resolve().parents[1]/"data"/"supervisor_20261111"


@pytest.fixture
def setup(tmp_path):
    store=SupervisorSyntheticStore(tmp_path,bank=SupervisorBank(DATA))
    flow=SyntheticConsentFlow(store,programs=("Fictional aivancity program",))
    return store,flow


def answers(store, right):
    return {q.question_id:(q.correct_answer if i<right else
            next(c for c in "ABCD" if c!=q.correct_answer))
            for i,q in enumerate(store.bank.forms["screening"])}


def intake(store,flow,fixture="F1",right=4,lang="en",optional=False,
           email="alpha@example.test"):
    flow.start_consent(fixture,checks=[True]*6,optional=optional,
                       language=lang,at=T0)
    assert flow.screen(fixture,answers=answers(store,right),at=T0)["eligible"]
    public=flow.register(fixture,email=email,age=22,
                         program="Fictional aivancity program",at=T0)
    assert "token" not in str(public).lower()
    return flow.identities[fixture]


def test_01_five_of_six_required_checks_cannot_start(setup):
    store,flow=setup
    with pytest.raises(SyntheticStudyError,match="six required"):
        flow.start_consent("F1",checks=[True]*5+[False],optional=True,
                           language="en",at=T0)
    assert not flow.drafts and not flow.identities


def test_02_six_checks_optional_left_blank_is_no(setup):
    store,flow=setup
    ref,token=intake(store,flow)
    with store._tx() as db:
        p=db.execute("SELECT consent_version,consent_lang,open_data_consent,consent_at "
                     "FROM participants WHERE learner_id=?",(ref,)).fetchone()
        assert p["consent_version"]==CONSENT_VERSION
        assert p["consent_lang"]=="en" and p["open_data_consent"]==0
        assert p["consent_at"]==iso(T0)


def test_03_economics_course_link_stores_nothing(setup):
    store,flow=setup
    flow.start_consent("F1",checks=[True]*6,optional=False,
                       language="en",at=T0)
    assert flow.declare_economics_course("F1")["message"]==INELIGIBLE
    with store._tx() as db:
        for table in ("participants","screening_log","events","deletion_log"):
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM pii.contacts").fetchone()[0]==0


def test_04_screening_six_of_eight_creates_only_anonymous_log(setup):
    store,flow=setup
    flow.start_consent("F1",checks=[True]*6,optional=False,
                       language="en",at=T0)
    assert not flow.screen("F1",answers=answers(store,6),at=T0)["eligible"]
    with store._tx() as db:
        row=db.execute("SELECT timestamp,score,eligible FROM screening_log").fetchone()
        assert set(row.keys())=={"timestamp","score","eligible"}
        assert row["score"]==6 and row["eligible"]==0
        assert db.execute("SELECT COUNT(*) FROM participants").fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM pii.contacts").fetchone()[0]==0
    assert flow.drafts=={}


def test_05_valid_registration_is_atomic_and_stores_hash_only(setup):
    store,flow=setup
    ref,token=intake(store,flow)
    with store._tx() as db:
        row=db.execute("SELECT screening_score,age,program,grp "
                       "FROM participants WHERE learner_id=?",(ref,)).fetchone()
        assert row["screening_score"]==4 and row["age"]==22
        assert row["grp"]=="A"
        contact=db.execute("SELECT email,token_hash FROM pii.contacts "
                           "WHERE learner_id=?",(ref,)).fetchone()
        assert contact["token_hash"]==hashlib.sha256(token.encode()).hexdigest()
        assert token!=contact["token_hash"]
    assert len(flow.private_mail_preview)==1
    assert not flow.private_mail_preview[0]["real_email_sent"]


def test_06_duplicate_email_is_rejected_without_rotation(setup):
    store,flow=setup
    intake(store,flow)
    flow.start_consent("F2",checks=[True]*6,optional=False,
                       language="en",at=T0)
    flow.screen("F2",answers=answers(store,4),at=T0)
    with pytest.raises(SyntheticStudyError,match="already registered"):
        flow.register("F2",email="ALPHA@example.test",age=22,
                      program="Fictional aivancity program",at=T0)
    with store._tx() as db:
        assert db.execute("SELECT COUNT(*) FROM participants").fetchone()[0]==1


def test_07_french_consent_and_optional_choice_persist(setup):
    store,flow=setup
    ref,_=intake(store,flow,lang="fr",optional=True)
    with store._tx() as db:
        row=db.execute("SELECT consent_lang,open_data_consent FROM participants "
                       "WHERE learner_id=?",(ref,)).fetchone()
        assert row["consent_lang"]=="fr" and row["open_data_consent"]==1


def test_08_withdraw_keep_invalidates_token_but_preserves_answers(setup):
    store,flow=setup
    ref,token=intake(store,flow)
    count_before=len(store.export_anonymous_events(ref=ref,token=token))
    result=flow.withdraw("F1",delete=False,at=T0+timedelta(days=1))
    assert result["message"]==KEEP_CONFIRMATION
    with store._tx() as db:
        assert db.execute("SELECT status FROM participants WHERE learner_id=?",
                          (ref,)).fetchone()["status"]=="withdrawn"
        assert db.execute("SELECT COUNT(*) FROM events WHERE learner_id=?",
                          (ref,)).fetchone()[0]==count_before
        assert db.execute("SELECT COUNT(*) FROM pii.contacts WHERE learner_id=?",
                          (ref,)).fetchone()[0]==1
    with pytest.raises(SyntheticStudyError,match="token"):
        store.progress(ref,token)


def test_09_withdraw_delete_removes_all_rows_and_preserves_single_log(setup):
    store,flow=setup
    ref,token=intake(store,flow)
    result=flow.withdraw("F1",delete=True,at=T0+timedelta(days=1))
    assert result["message"]==DELETE_CONFIRMATION
    with store._tx() as db:
        for table in ("participants","sessions","learner_state","state_history",
                      "events","surveys"):
            assert db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE learner_id=?",(ref,)
            ).fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM pii.contacts WHERE learner_id=?",
                          (ref,)).fetchone()[0]==0
        logs=db.execute("SELECT learner_id,channel FROM deletion_log").fetchall()
        assert len(logs)==1 and logs[0]["learner_id"]==ref
        assert logs[0]["channel"]=="website"
    with pytest.raises(SyntheticStudyError):
        store.progress(ref,token)


def test_10_two_missed_sessions_invalidate_token(setup):
    store,flow=setup
    ref,token=intake(store,flow)
    # Simulate completion of Session 1; 2026-11-11 scenario tests check
    # the actual 20-question/survey path separately.
    with store._tx() as db:
        state=store._state(db,ref)
        state.update(phase="WAITING_NEXT_SESSION",session=1)
        db.execute("UPDATE learner_state SET state_json=? WHERE learner_id=?",
                   (dump(state),ref))
    first=store.mark_missed(
        ref,token,at=T0+timedelta(days=4),
        reschedule_for=T0+timedelta(days=5),
    )
    assert first["missed_count"]==1 and not first["removed"]
    second=store.mark_missed(
        ref,token,at=T0+timedelta(days=5),reschedule_for=None,
    )
    assert second["removed"]
    with pytest.raises(SyntheticStudyError,match="token"):
        store.progress(ref,token)


def test_11_only_completed_get_points_and_debrief(setup):
    store,flow=setup
    ref,token=intake(store,flow)
    assert flow.privately_export_points()==[]
    with pytest.raises(SyntheticStudyError,match="Session 3"):
        flow.completed_debrief("F1")
    with store._tx() as db:
        db.execute("UPDATE participants SET status='completed',status_changed_at=? "
                   "WHERE learner_id=?",(iso(T0+timedelta(days=8)),ref))
    assert flow.completed_debrief("F1")["text"]==DEBRIEF
    export=flow.privately_export_points()
    assert export==[{"email":"alpha@example.test",
                    "completed_at":iso(T0+timedelta(days=8))}]
    assert "group" not in export[0] and "answer" not in export[0]


def test_12_close_collection_deletes_contact_only(setup):
    store,flow=setup
    ref,token=intake(store,flow)
    with store._tx() as db:
        before=db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    result=store.close_collection()
    assert result["fictional_contacts_deleted"]==1
    assert result["backups_deleted"] is False
    with store._tx() as db:
        assert db.execute("SELECT COUNT(*) FROM pii.contacts").fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM participants").fetchone()[0]==1
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0]==before
    with pytest.raises(SyntheticStudyError,match="token"):
        store.progress(ref,token)
