"""Researcher-only per-learner export uses genuine operational study tables.

No network, provider credentials, external emails, invitation delivery or
release activation. Tests guarantee stable per-email study pseudonyms,
scientifically interpretable timing, BKT measurements and PII boundaries.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
import json
from zipfile import ZipFile

import pytest

from scripts.supervisor_private_qa import new_private_suite
from src.prototype.supervisor_research_export import (
    build_student_research_archive, _csv_bytes,
)
from src.prototype.supervisor_trace_engine import CONCEPT_IDS


SCHOOL = "researcher-download@aivancity.education"
GMAIL = "separate-qa@gmail.com"
STAFF = "davis.joseph@aivancity.education"
NOW = lambda: datetime.now(timezone.utc)


@pytest.fixture
def prepared(tmp_path):
    root = tmp_path / "rehearsal-private"
    root.mkdir(mode=0o700)
    suite = new_private_suite(root,(SCHOOL,GMAIL),port=8897)
    intake = suite["intake"]
    store = suite["store"]
    token = intake.issue(SCHOOL,at=NOW())
    # School accounts require six affirmative declarations in this QA protocol.
    intake.consent(token,checks=[True]*6,optional=False,
                   language="en",at=NOW())
    answers = {
        q.question_id: (
            q.correct_answer if i < 4 else
            next(k for k in "ABCD" if k != q.correct_answer)
        )
        for i,q in enumerate(store.bank.forms["screening"])
    }
    assert intake.screening(token,answers=answers,at=NOW())["eligible"]
    result = intake.register(token,age=24,program="Private QA only",at=NOW())
    assert result["registered"] is True
    ref = intake.learner(token,at=NOW())
    assert ref == "STUDY_P001"

    start = NOW()
    for idx,question in enumerate(store.bank.forms["pretest"]):
        answered=start+timedelta(seconds=30+idx*20)
        store.answer_assessment(
            ref,token,request_id=f"qa-pretest-{idx:03d}",
            item_id=question.question_id,
            choice=question.correct_answer,
            shown_at=answered-timedelta(seconds=5),answered_at=answered,
        )
    with store._tx() as db:
        state=store._state(db,ref)
        assert state["phase"] == "QUIZ"

    question=store.next_item(ref,token)
    assert question["kind"]=="question"
    assert question["action"]=="QUESTION"
    qid=question["question_id"]
    correct=store.bank.get(qid,form="practice").correct_answer
    scored=start+timedelta(seconds=480)
    store.answer_quiz(
        ref,token,request_id="qa-quiz-0001",item_id=qid,choice=correct,
        shown_at=scored-timedelta(seconds=12),answered_at=scored,
    )
    # Test the next-session gap calculation using real DB schema with
    # invented fixture intervals; no submission or participant response
    # in the real RCT is mutated.
    with store._tx() as db:
        baseline=start.isoformat()
        end=(start+timedelta(minutes=45)).isoformat()
        next_start=(start+timedelta(days=4)).isoformat()
        db.execute(
            "UPDATE sessions SET started_at=?,ended_at=?,status='completed' "
            "WHERE learner_id=? AND session_no=1",(baseline,end,ref),
        )
        db.execute(
            "UPDATE sessions SET started_at=?,status='in_progress' "
            "WHERE learner_id=? AND session_no=2",(next_start,ref),
        )
        db.execute(
            "INSERT INTO surveys(learner_id,session_no,submitted_at,"
            "Q1,Q2,Q3,Q4,Q5,Q6,time_ms) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (ref,1,end,1,2,3,4,5,6,25000),
        )
    return suite,ref,token


def login(suite):
    client=suite["control"].test_client()
    headers={"Origin":"http://localhost","X-Study-Request":"1"}
    login_result=client.post("/control/api/login",json={
        "email":STAFF,"password":suite["passwords"][STAFF],
    },headers=headers)
    assert login_result.status_code==200
    csrf=client.get_cookie("recruitment_csrf",path="/control/").value
    changed=client.post("/control/api/change-password",json={
        "current":suite["passwords"][STAFF],
        "replacement":"Strong-Researcher-Download-Password-2026-Private!",
    },headers={**headers,"X-CSRF-Token":csrf})
    assert changed.status_code==200
    return client


def unpack(raw):
    with ZipFile(BytesIO(raw)) as archive:
        files={name:archive.read(name) for name in archive.namelist()}
    def rows(name):
        return list(csv.DictReader(StringIO(files[name].decode("utf-8-sig"))))
    return files,rows


def test_real_operational_student_export_contains_every_requested_measure(prepared):
    suite,ref,_ = prepared
    research=suite["store"].research
    import sqlite3
    db=sqlite3.connect(research.as_uri()+"?mode=ro",uri=True)
    db.row_factory=sqlite3.Row
    try:
        archive=build_student_research_archive(db,learner_id=ref)
    finally:
        db.close()
    files,rows=unpack(archive)
    assert set(files)=={
        "research_metadata.json","event_log.csv","mastery_progression.csv",
        "question_intervals.csv","session_timings.csv","fatigue.csv",
        "assessments.csv",
    }
    meta=json.loads(files["research_metadata.json"])
    assert meta["learner_id"]==ref
    assert meta["arm"]=="A"
    assert meta["initial_bkt_mastery"] is not None
    assert set(meta["initial_bkt_mastery"])==set(CONCEPT_IDS)
    assert meta["initial_overall_bkt_mean"] is not None
    assert meta["session_sequence"]["3"]==["QUIZ","POSTTEST","SURVEY"]
    mastery=rows("mastery_progression.csv")
    assert len(mastery)>=1
    assert mastery[0]["arm"]=="A"
    assert mastery[0]["question_id"]
    assert mastery[0]["event_id"]
    assert set(CONCEPT_IDS).issubset(mastery[0])
    mean=round(sum(float(mastery[0][k]) for k in CONCEPT_IDS)/8,6)
    assert float(mastery[0]["overall_bkt_mean"])==mean
    intervals=rows("question_intervals.csv")
    assert len(intervals)>=17  # sixteen pretest questions + one quiz
    assert intervals[0]["between_answers_seconds"]==""
    assert float(intervals[1]["between_answers_seconds"])==20
    assert intervals[0]["response_latency_ms"]=="5000"
    assert float(intervals[-1]["between_answers_seconds"])>=0
    sessions=rows("session_timings.csv")
    assert len(sessions)==3
    assert sessions[0]["status"]=="completed"
    assert float(sessions[0]["session_elapsed_seconds"])==2700
    assert float(sessions[1]["gap_since_previous_session_end_seconds"])==(
        4*86400-2700
    )
    fatigue=rows("fatigue.csv")
    assert len(fatigue)==1
    assert [fatigue[0][f"Q{i}"] for i in range(1,7)]==list("123456")
    assert rows("assessments.csv")
    assert any(e["phase"]=="PRETEST" for e in rows("assessments.csv"))
    assert all(e["phase"] in ("SCREENING","PRETEST","POSTTEST")
               for e in rows("assessments.csv"))
    assert any(e["phase"]=="QUIZ" for e in rows("event_log.csv"))
    # Pseudonymized archive must not contain names, emails, invitation
    # secrets or private consent/reflection contents.
    assert SCHOOL.encode() not in archive
    assert GMAIL.encode() not in archive
    assert b"@aivancity.education" not in archive


def test_export_is_strictly_researcher_authenticated_and_audited(prepared):
    suite,ref,token=prepared
    control=suite["control"].test_client()
    uri=f"/control/api/research-export/{ref}.zip"
    assert control.get(uri).status_code==409
    assert suite["study"].test_client().get(uri).status_code==404
    control=login(suite)
    bad=control.get("/control/api/research-export/invalid.zip")
    assert bad.status_code==409
    missing=control.get("/control/api/research-export/STUDY_P999.zip")
    assert missing.status_code==409
    archive=control.get(uri)
    assert archive.status_code==200
    assert archive.mimetype=="application/zip"
    assert "attachment" in archive.headers["Content-Disposition"]
    assert archive.headers["Cache-Control"].startswith("private, no-store")
    files,_=unpack(archive.data)
    assert json.loads(files["research_metadata.json"])["learner_id"]==ref
    with suite["ledger"]._tx() as db:
        log=db.execute(
            "SELECT actor,action,details FROM audit "
            "WHERE action='pseudonymous_research_export'"
        ).fetchall()
    assert len(log)==1 and log[0]["actor"]==STAFF
    assert log[0]["details"]==ref


def test_csv_formula_injection_is_neutralized():
    content=_csv_bytes(
        ("label","number"),
        ({"label":"=1+1","number":12},),
    ).decode("utf-8-sig")
    assert content.startswith("label,number")
    assert "'=HYPERLINK" in content


def test_learner_id_remains_one_per_email_and_one_arm(prepared):
    suite,ref,token=prepared
    store=suite["store"]
    with store._tx() as db:
        rows=db.execute(
            "SELECT p.learner_id,p.grp,c.email FROM participants p "
            "JOIN pii.contacts c USING(learner_id)"
        ).fetchall()
        assert len(rows)==1
        assert rows[0]["learner_id"]==ref
        assert rows[0]["grp"]=="A"
        assert rows[0]["email"]==SCHOOL
        assert db.execute(
            "SELECT COUNT(*) FROM participants WHERE learner_id=?",(ref,)
        ).fetchone()[0]==1
    with pytest.raises(Exception,match="already registered"):
        suite["intake"].issue(SCHOOL,at=NOW())
