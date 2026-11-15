"""Hermetic QA for simultaneous student and researcher test roles.

These tests use invented addresses, fake ephemeral passwords, a separate
temporary SQLite directory, no VPS, no OAuth and no network mail.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import stat

import pytest
from werkzeug.test import Client
from werkzeug.wrappers import Response

from scripts.supervisor_private_qa import new_private_suite, FORBIDDEN_PORTS

SCHOOL = "rehearsal.student@aivancity.education"
GMAIL = "rehearsal.external@gmail.com"
STAFF = "davis.joseph@aivancity.education"
NEWPASS = "New-Private-QA-Password-Only-2026-Long!"


@pytest.fixture
def suite(tmp_path):
    private = tmp_path / "qa"
    private.mkdir(mode=0o700)
    return new_private_suite(private, (SCHOOL, GMAIL), port=8897)


def headers(path="/", csrf=None):
    value = {"Origin": "http://localhost", "X-Study-Request": "1"}
    if csrf is not None:
        value["X-CSRF-Token"] = csrf
    return value


def submit(client, email, group):
    return client.post("/interest/api/apply", json={
        "email": email, "first_name": "Fictional", "last_name": "Tester",
        "language": "en", "questionnaire": group, "qa_acknowledged": True,
    }, headers=headers())


def signin(control, suite):
    login = control.post("/control/api/login", json={
        "email": STAFF, "password": suite["passwords"][STAFF],
    }, headers=headers())
    assert login.status_code == 200
    assert login.json["must_change_password"] is True
    csrf = control.get_cookie("recruitment_csrf", path="/control/").value
    change = control.post("/control/api/change-password", json={
        "current": suite["passwords"][STAFF], "replacement": NEWPASS,
    }, headers=headers(csrf=csrf))
    assert change.status_code == 200
    return csrf


def test_exactly_four_isolated_QA_admins_and_never_live(suite):
    credential_dir = suite["credential_dir"]
    assert stat.S_IMODE(credential_dir.stat().st_mode) == 0o700
    assert len(tuple(credential_dir.glob("*.txt"))) == 4
    assert all(stat.S_IMODE(p.stat().st_mode) == 0o600
               for p in credential_dir.glob("*.txt"))
    assert suite["store"].operational
    assert suite["store"].research.parent == suite["ledger"].file.parent
    control = suite["control"].test_client()
    assert control.get("/control/api/overview").status_code == 409
    assert control.get("/control/api/capabilities").status_code == 409
    student = suite["study"].test_client()
    assert student.get("/study/health").json["enrollment_authorized"] is False
    assert student.get("/study/health").json["deployment"] == "staging"


def test_passwordless_school_and_gmail_questionnaires_are_private_QA_only(suite):
    client = suite["interest"].test_client()
    assert client.get("/interest/school").status_code == 200
    assert client.get("/interest/external").status_code == 200
    assert "NOT real research enrollment" in client.get(
        "/interest/school").get_data(as_text=True)
    assert client.get("/interest/qa.js").status_code == 200
    assert client.get("/interest/unknown").status_code == 404
    assert submit(client, SCHOOL, "school").status_code == 202
    assert submit(client, GMAIL, "external").status_code == 202
    rows = suite["ledger"].candidates()
    assert len(rows) == 2
    assert {r["email"] for r in rows} == {SCHOOL, GMAIL}
    assert all(r["privacy_sha256"] == "UNAPPROVED" for r in rows)
    assert all(r["approved_for_invitation"] == 0 for r in rows)
    assert submit(client, "outsider@example.org", "external").status_code == 409
    assert submit(client, SCHOOL, "external").status_code == 409
    assert submit(client, GMAIL, "school").status_code == 409
    assert client.post("/interest/api/apply", json={}, headers={
        "Origin": "https://malicious.example", "X-Study-Request": "1",
    }).status_code == 403


def test_duplicate_school_questionnaire_returns_same_internal_candidate(suite):
    browser = suite["interest"].test_client()
    first = submit(browser, SCHOOL, "school")
    duplicate = submit(browser, SCHOOL.upper(), "school")
    assert first.status_code == duplicate.status_code == 202
    records = suite["ledger"].candidates()
    assert len(records) == 1
    assert records[0]["email"] == SCHOOL
    assert records[0]["application_count"] == 2
    # A questionnaire submission is never itself a randomized study ID.
    assert records[0]["approved_for_invitation"] == 0
    assert records[0]["invitation_status"] == "potential"
    with suite["store"]._tx() as db:
        assert db.execute("SELECT COUNT(*) FROM participants").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM pii.invitations").fetchone()[0] == 0


def test_qa_researcher_approves_then_issues_two_separate_token_flows(suite):
    applicants = suite["interest"].test_client()
    assert submit(applicants, SCHOOL, "school").status_code == 202
    assert submit(applicants, GMAIL, "external").status_code == 202
    staff = suite["control"].test_client()
    assert staff.get("/control/api/candidates").status_code == 409
    assert staff.post("/control/api/qa-issue", json={"candidate_id": 1},
                      headers=headers()).status_code == 409
    csrf = signin(staff, suite)
    before = staff.post("/control/api/qa-issue",
        json={"candidate_id": 1},headers=headers(csrf=csrf))
    assert before.status_code == 409
    candidate_rows = staff.get("/control/api/candidates").json["candidates"]
    ids = [r["candidate_id"] for r in candidate_rows]
    assert staff.post("/control/api/approve",json={
        "candidate_ids": ids,
    }, headers=headers(csrf=csrf)).json["approved"] == 2

    links = {}
    for row in candidate_rows:
        reply = staff.post("/control/api/qa-issue",
                           json={"candidate_id": row["candidate_id"]},
                           headers=headers(csrf=csrf))
        assert reply.status_code == 200, reply.json
        assert reply.json["mail_sent"] is False
        url = reply.json["test_link"]
        assert url.startswith("http://127.0.0.1:8897/study/#invite=")
        token = parse_qs(urlsplit(url).fragment)["invite"][0]
        status = suite["intake"].status(token, at=datetime.now(timezone.utc))
        assert status is not None
        links[row["email"]] = token
        again = staff.post("/control/api/qa-issue",
                           json={"candidate_id": row["candidate_id"]},
                           headers=headers(csrf=csrf))
        assert again.status_code == 409
    assert links[SCHOOL] != links[GMAIL]
    assert staff.get("/control/api/overview").status_code == 200
    assert staff.get("/control/api/capabilities").json["invitation_sending_available"] is False

    students = [suite["study"].test_client(), suite["study"].test_client()]
    for student, token in zip(students, links.values()):
        exchange = student.post("/study/api/exchange", json={"token": token},
                                headers=headers())
        assert exchange.status_code == 200
        assert student.get("/study/").status_code == 200
    assert staff.get("/control/qa/").status_code == 200


def test_QA_refuses_real_reserved_production_ports(tmp_path):
    private = tmp_path / "qa2"
    private.mkdir(mode=0o700)
    for port in FORBIDDEN_PORTS:
        with pytest.raises(ValueError, match="port"):
            new_private_suite(private, (SCHOOL, GMAIL), port=port)


def test_dispatcher_no_PUBLIC_paths_or_mail(suite):
    app = Client(suite["app"], Response)
    # Werkzeug's bare WSGI Client does not assign REMOTE_ADDR. Supply the
    # exact localhost address used by the real socket so this verifies the
    # underlying auth checks rather than being rejected by the transport gate.
    def get(path):
        return app.get(path, environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
    assert get("/").status_code == 404
    assert get("/control/api/overview").status_code == 409
    assert get("/interest/school").status_code == 200
    assert get("/study/health").json["enrollment_authorized"] is False
    assert get("/unrecognized").status_code == 404
    assert get("/interest/api/apply").status_code == 405


def test_qa_form_is_bilingual_passwordless_and_separate_from_signed_live_notice(suite):
    browser=suite["interest"].test_client()
    for form in ("school","external"):
        page=browser.get("/interest/"+form)
        assert page.status_code==200
        html=page.get_data(as_text=True)
        assert 'id="language"' in html
        assert 'id="no-ai-note"' in html
        assert 'id="ack"' in html
        assert "NOT real research enrollment" in html
        assert 'type="password"' not in html
        assert '/interest/qa.js' in html
        assert '/interest/qa.css' in html
    script=browser.get("/interest/qa.js")
    assert script.status_code==200
    source=script.get_data(as_text=True)
    for phrase in ("Prêt(e) à découvrir", "generative AI tools",
                   "IA générative", 'document.documentElement.lang',
                   'messages[lang].received'):
        assert phrase in source
    stylesheet=browser.get("/interest/qa.css")
    assert stylesheet.status_code==200
    assert "@media(max-width:680px)" in stylesheet.get_data(as_text=True)


def test_researcher_issues_all_approved_qa_links_in_one_action(suite):
    applicant=suite["interest"].test_client()
    submit(applicant,SCHOOL,"school")
    submit(applicant,GMAIL,"external")
    staff=suite["control"].test_client()
    assert staff.get("/control/qa/").status_code==200
    assert staff.get("/control/qa.js").status_code==200
    assert staff.post("/control/api/qa-issue-all",
        json={"confirm":True},headers=headers()).status_code==409
    csrf=signin(staff,suite)
    assert staff.post("/control/api/qa-issue-all",
        json={},headers=headers(csrf=csrf)).status_code==409
    none=staff.post("/control/api/qa-issue-all",
        json={"confirm":True},headers=headers(csrf=csrf))
    assert none.status_code==200 and none.json["issued"]==0
    ids=[r["candidate_id"] for r in suite["ledger"].candidates()]
    assert staff.post("/control/api/approve",json={
        "candidate_ids":ids},headers=headers(csrf=csrf)).status_code==200
    result=staff.post("/control/api/qa-issue-all",
        json={"confirm":True},headers=headers(csrf=csrf))
    assert result.status_code==200
    assert result.json["qa_only"] is True
    assert result.json["mail_sent"] is False
    assert result.json["issued"]==2
    assert len(result.json["links"])==2
    assert {x["email"] for x in result.json["links"]}=={SCHOOL,GMAIL}
    tokens=[parse_qs(urlsplit(x["test_link"]).fragment)["invite"][0]
            for x in result.json["links"]]
    assert len(set(tokens))==2
    for token in tokens:
        assert suite["intake"].status(token,at=datetime.now(timezone.utc))
    assert all(row["invitation_status"]=="prepared"
               for row in suite["ledger"].candidates())
    replay=staff.post("/control/api/qa-issue-all",
        json={"confirm":True},headers=headers(csrf=csrf))
    assert replay.status_code==200
    assert replay.json["issued"]==0 and replay.json["links"]==[]
    with suite["ledger"]._tx() as db:
        assert db.execute("SELECT COUNT(*) FROM mail_dispatch").fetchone()[0]==0


@pytest.mark.parametrize("researcher",(
    "davis.joseph@aivancity.education",
    "wiam.belouard@aivancity.education",
    "sara.elkardi@aivancity.education",
    "yaacoub@aivancity.ai",
))
def test_all_four_staff_can_individually_issue_private_qa_links(suite,researcher):
    applicant=suite["interest"].test_client()
    assert submit(applicant,SCHOOL,"school").status_code==202
    staff=suite["control"].test_client()
    password=suite["passwords"][researcher]
    result=staff.post("/control/api/login",
        json={"email":researcher,"password":password},headers=headers())
    assert result.status_code==200
    csrf=staff.get_cookie("recruitment_csrf",path="/control/").value
    assert staff.post("/control/api/qa-issue-all",
        json={"confirm":True},headers=headers(csrf=csrf)).status_code==409
    changed=staff.post("/control/api/change-password",
        json={"current":password,"replacement":NEWPASS+"another-unique"},
        headers=headers(csrf=csrf))
    assert changed.status_code==200
    assert staff.post("/control/api/approve",
        json={"candidate_ids":[suite["ledger"].candidates()[0]["candidate_id"]]},
        headers=headers(csrf=csrf)).status_code==200
    result=staff.post("/control/api/qa-issue-all",
        json={"confirm":True},headers=headers(csrf=csrf))
    assert result.status_code==200
    assert result.json["issued"]==1 and result.json["mail_sent"] is False


def test_only_explicit_private_qa_student_can_skip_wait_not_live(suite):
    """Regression for the displayed TEST ONLY button returning HTTP 409."""
    import json
    from src.prototype.supervisor_trace_engine import (
        SupervisorTraceEngine, CONCEPT_IDS,
    )
    token = suite["intake"].issue(SCHOOL,at=datetime.now(timezone.utc))
    suite["intake"].consent(
        token,checks=[True]*6,optional=False,language="en",
        at=datetime.now(timezone.utc),
    )
    answers={
        question.question_id:(
            question.correct_answer if i<4 else next(
                letter for letter in "ABCD" if letter!=question.correct_answer
            )
        )
        for i,question in enumerate(suite["store"].bank.forms["screening"])
    }
    assert suite["intake"].screening(token,answers=answers,
        at=datetime.now(timezone.utc))["eligible"]
    assert suite["intake"].register(
        token,age=24,program="Private QA only",
        at=datetime.now(timezone.utc),
    )["registered"]
    ref = suite["intake"].learner(token,at=datetime.now(timezone.utc))
    student=suite["study"].test_client()
    assert student.post("/study/api/exchange",json={"token":token},
                        headers=headers()).status_code==200
    assert student.post("/study/api/staging-next-session",json={},
                        headers=headers()).status_code==409
    with suite["store"]._tx() as db:
        state=json.loads(db.execute(
            "SELECT state_json FROM learner_state WHERE learner_id=?",(ref,)
        ).fetchone()["state_json"])
        state["phase"]="WAITING_NEXT_SESSION"
        state["session"]=1
        engine=SupervisorTraceEngine("A",dict.fromkeys(CONCEPT_IDS,.5))
        engine.question_in_session=20
        state["engine"]=engine.snapshot()
        db.execute(
            "UPDATE learner_state SET step='WAITING_NEXT_SESSION',"
            "step_index=0,state_json=? WHERE learner_id=?",
            (json.dumps(state),ref),
        )
    # The genuine three-day scheduling endpoint must remain blocked.
    assert student.post("/study/api/next-session",json={},
                        headers=headers()).status_code==409
    preview=student.post("/study/api/staging-next-session",json={},
                         headers=headers())
    assert preview.status_code==200, preview.json
    assert preview.json["session_started"]==2
    assert preview.json["staging_preview_advance"] is True
    assert student.post("/study/api/staging-next-session",json={},
                        headers=headers()).status_code==409
    assert student.get("/study/health").json["enrollment_authorized"] is False
    with suite["store"]._tx() as db:
        current=db.execute("SELECT grp FROM participants WHERE learner_id=?",
                           (ref,)).fetchone()
        assert current["grp"]=="A"
        assert db.execute("SELECT COUNT(*) FROM participants").fetchone()[0]==1
    assert suite["control"].test_client().get("/control/api/capabilities").status_code==409
