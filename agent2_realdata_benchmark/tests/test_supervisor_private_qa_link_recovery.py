"""Researcher-mediated QA link recovery: never reset or re-enroll a student.

No real users, emails, mail providers, public traffic, or LIVE databases.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit, parse_qs
import json

import pytest

from scripts.supervisor_private_qa import new_private_suite
from src.prototype.supervisor_synthetic_store import SyntheticStudyError

SCHOOL="lost-link-tester@aivancity.education"
OTHER="lost-link-external@gmail.com"
STAFF="davis.joseph@aivancity.education"
PASSWORD="QA-recovery-rotated-private-password-2026!"
NOW=lambda:datetime.now(timezone.utc)


def headers(csrf=None):
    result={"Origin":"http://localhost","X-Study-Request":"1"}
    if csrf is not None:
        result["X-CSRF-Token"]=csrf
    return result


@pytest.fixture
def suite(tmp_path):
    home=tmp_path/"private-qa"
    home.mkdir(mode=0o700)
    return new_private_suite(home,(SCHOOL,OTHER),port=8897,persistent=True)


def create_link(suite):
    form=suite["interest"].test_client()
    assert form.post("/interest/api/apply",json={
        "email":SCHOOL,"first_name":"QA","last_name":"Only",
        "language":"en","questionnaire":"school","qa_acknowledged":True,
    },headers=headers()).status_code==202
    reviewer=suite["control"].test_client()
    assert reviewer.post("/control/api/login",json={
        "email":STAFF,"password":suite["passwords"][STAFF],
    },headers=headers()).status_code==200
    csrf=reviewer.get_cookie("recruitment_csrf",path="/control/").value
    assert reviewer.post("/control/api/change-password",json={
        "current":suite["passwords"][STAFF],"replacement":PASSWORD,
    },headers=headers(csrf)).status_code==200
    cid=suite["ledger"].candidates()[0]["candidate_id"]
    assert reviewer.post("/control/api/approve",json={
        "candidate_ids":[cid],
    },headers=headers(csrf)).status_code==200
    issued=reviewer.post("/control/api/qa-issue",json={
        "candidate_id":cid,
    },headers=headers(csrf))
    assert issued.status_code==200
    old=parse_qs(urlsplit(issued.json["test_link"]).fragment)["invite"][0]
    return reviewer,csrf,cid,old


def recover(reviewer,csrf,cid):
    return reviewer.post("/control/api/qa-recover",json={
        "candidate_id":cid,"confirm":True,
    },headers=headers(csrf))


def stage_pre_registration(suite,token,stage):
    if stage=="invited":
        return
    assert suite["intake"].consent(token,checks=[True]*6,
        optional=False,language="en",at=NOW())["stage"]=="screening"
    if stage=="consented":
        return
    answers={question.question_id:(
        question.correct_answer if i<4 else
        next(choice for choice in "ABCD" if choice!=question.correct_answer)
    ) for i,question in enumerate(suite["store"].bank.forms["screening"])}
    assert suite["intake"].screening(token,answers=answers,
        at=NOW())["eligible"] is True
    if stage=="screened":
        return
    assert suite["intake"].register(
        token,age=24,program="Private QA only",at=NOW())["registered"] is True


@pytest.mark.parametrize("stage",("invited","consented","screened"))
def test_recover_before_registration_preserves_original_intake_stage(suite,stage):
    reviewer,csrf,cid,old=create_link(suite)
    stage_pre_registration(suite,old,stage)
    denied=suite["control"].test_client().post(
        "/control/api/qa-recover",json={"candidate_id":cid,"confirm":True},
        headers=headers())
    assert denied.status_code==409
    response=recover(reviewer,csrf,cid)
    assert response.status_code==200
    assert response.json["stage"]==stage
    # The previous token cannot be used to pass intake stages.
    with pytest.raises(SyntheticStudyError,match="not found"):
        suite["intake"].status(old,at=NOW())
    # The new token resumes the exact persisted stage, not a fresh consent.
    token=parse_qs(urlsplit(response.json["test_link"]).fragment)["invite"][0]
    assert suite["intake"].status(token,at=NOW())["stage"]==stage
    assert len(suite["ledger"].candidates())==1
    with suite["store"]._tx() as db:
        assert db.execute("SELECT COUNT(*) FROM participants").fetchone()[0]==0


def test_recovery_after_quiz_answer_keeps_exact_id_arm_events_and_resume(suite):
    reviewer,csrf,cid,old=create_link(suite)
    stage_pre_registration(suite,old,"registered")
    ref=suite["intake"].learner(old,at=NOW())
    student=suite["study"].test_client()
    assert student.post("/study/api/exchange",json={"token":old},
                        headers=headers()).status_code==200
    assert suite["intake"].status(old,at=NOW())["stage"]=="participant"
    item=suite["store"].next_item(ref,old)
    assert item["phase"]=="PRETEST"
    suite["store"].answer_assessment(
        ref,old,request_id="recover-pretest-0001",
        item_id=item["question_id"],choice="A",shown_at=NOW(),answered_at=NOW(),
    )
    with suite["store"]._tx() as db:
        previous=db.execute(
            "SELECT grp,status FROM participants WHERE learner_id=?",(ref,)
        ).fetchone()
        grp=previous["grp"]
        snapshot=db.execute(
            "SELECT state_json FROM learner_state WHERE learner_id=?",(ref,)
        ).fetchone()["state_json"]
        events=db.execute(
            "SELECT COUNT(*) FROM events WHERE learner_id=?",(ref,)
        ).fetchone()[0]
        # Registration also records the eight screening assessment events.
        # Recovery must preserve the entire accumulated history, not merely
        # the single pretest response.
        assert events>=9
        assert db.execute("SELECT COUNT(*) FROM events WHERE learner_id=? "
                          "AND phase='PRETEST'",(ref,)).fetchone()[0]==1

    assert reviewer.post("/control/api/qa-recover",json={
        "candidate_id":cid,
    },headers=headers(csrf)).status_code==409
    assert reviewer.post("/control/api/qa-recover",json={
        "candidate_id":True,"confirm":True,
    },headers=headers(csrf)).status_code==409
    response=recover(reviewer,csrf,cid)
    assert response.status_code==200,response.json
    result=response.json
    assert result["learner_id"]==ref
    assert result["same_participant"] is True
    assert result["stage"]=="registered"
    assert result["old_link_revoked"] is True
    assert result["mail_sent"] is False
    assert result["qa_only"] is True
    new=parse_qs(urlsplit(result["test_link"]).fragment)["invite"][0]
    assert new!=old
    assert student.post("/study/api/status",json={},
                        headers=headers()).status_code==409
    with pytest.raises(SyntheticStudyError):
        suite["intake"].learner(old,at=NOW())

    fresh=suite["study"].test_client()
    accepted=fresh.post("/study/api/exchange",json={"token":new},
                        headers=headers())
    assert accepted.status_code==200
    assert accepted.json["stage"]=="participant"
    assert suite["intake"].learner(new,at=NOW())==ref
    result_status=fresh.post("/study/api/status",json={},
                             headers=headers())
    assert result_status.status_code==200
    assert result_status.json["phase"]=="PRETEST"

    with suite["store"]._tx() as db:
        assert db.execute(
            "SELECT COUNT(*) FROM participants"
        ).fetchone()[0]==1
        assert db.execute(
            "SELECT grp,status FROM participants WHERE learner_id=?",(ref,)
        ).fetchone()["grp"]==grp
        assert db.execute(
            "SELECT state_json FROM learner_state WHERE learner_id=?",(ref,)
        ).fetchone()["state_json"]==snapshot
        assert db.execute(
            "SELECT COUNT(*) FROM events WHERE learner_id=?",(ref,)
        ).fetchone()[0]==events
        assert db.execute("SELECT COUNT(*) FROM pii.invitations").fetchone()[0]==1
    assert suite["ledger"].candidates()[0]["invitation_status"]=="prepared"
    with suite["ledger"]._tx() as db:
        audit=db.execute(
            "SELECT actor,subject_id,details FROM audit "
            "WHERE action='qa_invitation_recovered'"
        ).fetchall()
        assert len(audit)==1
        assert audit[0]["actor"]==STAFF
        assert audit[0]["subject_id"]==cid
        assert ref in audit[0]["details"]
        assert old not in audit[0]["details"] and new not in audit[0]["details"]


def test_recovery_does_not_reopen_closed_study_or_allow_other_email(suite):
    reviewer,csrf,cid,old=create_link(suite)
    assert recover(reviewer,csrf,cid).status_code==200
    new_token=parse_qs(
        urlsplit(recover(reviewer,csrf,cid).json["test_link"]).fragment
    )["invite"][0]
    # Any arbitrary non-allowlisted email is denied even if the actor is staff.
    with pytest.raises(SyntheticStudyError,match="allowlisted"):
        suite["intake"].rotate_private_qa_invitation(
            "outside@example.net",new_token="A"*70,at=NOW())
    # A genuine LIVE store has an empty allowlist, no QA recovery.
    from src.prototype.supervisor_operational_intake import OperationalIntake
    from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore
    from src.prototype.supervisor_content import SupervisorBank
    from scripts.supervisor_private_qa import BANK
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        store=SupervisorSyntheticStore(Path(folder),bank=SupervisorBank(BANK),
                                       operational=True)
        intake=OperationalIntake(store,programs=("Private QA only",))
        with pytest.raises(SyntheticStudyError,match="allowlisted"):
            intake.rotate_private_qa_invitation(
                SCHOOL,new_token="B"*70,at=NOW())
    assert suite["intake"].status(new_token,at=NOW())["stage"]=="invited"
    with suite["store"]._tx() as db:
        db.execute("UPDATE collection_status SET closed_at=? WHERE one=1",
                   (NOW().isoformat(),))
    assert recover(reviewer,csrf,cid).status_code==409
    # Closing the cohort must not revoke the earlier token as a side effect
    # of a denied recovery or generate a second student.
    assert suite["intake"].status(new_token,at=NOW())["stage"]=="invited"
