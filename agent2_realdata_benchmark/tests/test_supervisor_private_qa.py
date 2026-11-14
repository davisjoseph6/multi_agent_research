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
    assert app.get("/").status_code == 404
    assert app.get("/control/api/overview").status_code == 409
    assert app.get("/interest/school").status_code == 200
    assert app.get("/study/health").json["enrollment_authorized"] is False
    assert app.get("/unrecognized").status_code == 404
    assert app.get("/interest/api/apply").status_code == 405
