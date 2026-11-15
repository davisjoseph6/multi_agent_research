"""Durable QA harness must preserve logins and progress across process restarts.

The real trial and staging databases are not used; this is an isolated owner
rehearsal with no provider, public URL, or release authorization.
"""
from datetime import datetime, timezone
from pathlib import Path
import stat

import pytest
from werkzeug.test import Client
from werkzeug.wrappers import Response

from scripts.supervisor_private_qa import new_private_suite
from src.prototype.supervisor_recruitment import ADMIN_EMAILS

SCHOOL="persistent-self@aivancity.education"
EXTERNAL="persistent-external@gmail.com"
STAFF="davis.joseph@aivancity.education"
HEADERS={"Origin":"http://localhost","X-Study-Request":"1"}
NEW_PASSWORD="Persistent-QA-Researcher-Credential-2026-Long-Only!"


def private_dir(tmp_path):
    root=tmp_path/"durable"
    root.mkdir(mode=0o700)
    return root


def test_persistent_qa_restart_keeps_fixed_staff_and_student_state(tmp_path):
    root=private_dir(tmp_path)
    first=new_private_suite(root,(SCHOOL,EXTERNAL),port=8897,persistent=True)
    assert len(first["passwords"])==4
    reviewer=first["control"].test_client()
    response=reviewer.post("/control/api/login",json={
        "email":STAFF,"password":first["passwords"][STAFF],
    },headers=HEADERS)
    assert response.status_code==200
    csrf=reviewer.get_cookie("recruitment_csrf",path="/control/").value
    changed=reviewer.post("/control/api/change-password",json={
        "current":first["passwords"][STAFF],
        "replacement":NEW_PASSWORD,
    },headers={**HEADERS,"X-CSRF-Token":csrf})
    assert changed.status_code==200

    candidate=first["interest"].test_client()
    assert candidate.post("/interest/api/apply",json={
        "email":SCHOOL,"first_name":"Private",
        "last_name":"Test","language":"en",
        "questionnaire":"school","qa_acknowledged":True,
    },headers=HEADERS).status_code==202
    rows=first["ledger"].candidates()
    assert len(rows)==1
    assert reviewer.post("/control/api/approve",json={
        "candidate_ids":[rows[0]["candidate_id"]]},
        headers={**HEADERS,"X-CSRF-Token":csrf}).status_code==200
    issued=reviewer.post("/control/api/qa-issue-all",json={
        "confirm":True},headers={**HEADERS,"X-CSRF-Token":csrf})
    assert issued.status_code==200
    assert issued.json["issued"]==1
    import urllib.parse
    token=urllib.parse.parse_qs(
        urllib.parse.urlsplit(issued.json["links"][0]["test_link"]).fragment
    )["invite"][0]
    now=datetime.now(timezone.utc)
    first["intake"].consent(token,checks=[True]*6,optional=False,
                            language="en",at=now)
    answers={
        q.question_id:(
            q.correct_answer if i<4 else
            next(k for k in "ABCD" if k!=q.correct_answer)
        )
        for i,q in enumerate(first["store"].bank.forms["screening"])
    }
    assert first["intake"].screening(token,answers=answers,at=now)["eligible"]
    assert first["intake"].register(
        token,age=24,program="Private QA only",at=now)["registered"]
    identity=first["intake"].learner(token,at=now)
    question=first["store"].next_item(identity,token)
    first["store"].answer_assessment(
        identity,token,request_id="persistent-pretest-0001",
        item_id=question["question_id"],choice="A",shown_at=now,answered_at=now,
    )
    first_hashes={p.name:p.read_bytes() for p in first["credential_dir"].glob("*.txt")}

    second=new_private_suite(root,(SCHOOL,EXTERNAL),port=8897,persistent=True)
    assert second["passwords"]=={}  # no bootstrapping or resetting users
    assert len(list(second["credential_dir"].glob("*.txt")))==4
    assert {p.name:p.read_bytes() for p in second["credential_dir"].glob("*.txt")}==first_hashes
    assert len(second["ledger"].candidates())==1
    assert second["intake"].learner(token,at=datetime.now(timezone.utc))==identity
    state=second["store"].progress(identity,token)
    assert state["session"]==1
    with second["store"]._tx() as db:
        assert db.execute(
            "SELECT COUNT(*) FROM events WHERE learner_id=? AND phase='PRETEST'",
            (identity,),
        ).fetchone()[0]==1
    reviewer2=second["control"].test_client()
    assert reviewer2.post("/control/api/login",json={
        "email":STAFF,"password":NEW_PASSWORD,
    },headers=HEADERS).status_code==200
    assert second["store"].research==first["store"].research
    assert second["store"].contacts==first["store"].contacts


def test_persistent_qa_path_aliases_are_private_and_not_public_routes(tmp_path):
    suite=new_private_suite(private_dir(tmp_path),(SCHOOL,EXTERNAL),
                            port=8897,persistent=True)
    client=Client(suite["app"],Response)
    for friendly,target in {
        "/questionnaire/student":"/interest/school",
        "/questionnaire/external":"/interest/external",
        "/researcher":"/control/",
        "/researcher/invitations":"/control/qa/",
        "/participate":"/study/",
    }.items():
        response=client.get(friendly,environ_overrides={"REMOTE_ADDR":"127.0.0.1"})
        assert response.status_code==302
        assert response.headers["Location"]==target
        assert response.headers["Cache-Control"].startswith("private")
    for path in ("/", "/api/qa-issue-all", "/human-enrollment"):
        assert client.get(path,environ_overrides={
            "REMOTE_ADDR":"127.0.0.1"}).status_code==404
    assert suite["study"].test_client().get("/study/health").json[
        "enrollment_authorized"
    ] is False
    assert all(suite["ledger"].reminder_enabled() is False
               for _ in range(1))


def test_persistent_qa_must_be_in_explicit_private_directory(tmp_path):
    root=private_dir(tmp_path)
    bad=tmp_path/"world-readable"
    bad.mkdir(mode=0o755)
    with pytest.raises(ValueError):
        new_private_suite(bad,(SCHOOL,EXTERNAL),port=8897,persistent=True)
    link=tmp_path/"alias"
    link.symlink_to(root,target_is_directory=True)
    with pytest.raises(ValueError):
        new_private_suite(link,(SCHOOL,EXTERNAL),port=8897,persistent=True)
    with pytest.raises(ValueError,match="explicit boolean"):
        new_private_suite(root,(SCHOOL,EXTERNAL),port=8897,persistent="yes")
