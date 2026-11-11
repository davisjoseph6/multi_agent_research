"""Private HTTP acceptance against actual supervisor CSVs, no real students."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import re

import pytest

from scripts.supervisor_fictional_browser import new_supervisor_fictional_runtime
from src.prototype.supervisor_fictional_web import make_supervisor_fictional_app

PORT=8783
T0=datetime(2026,11,11,12,tzinfo=timezone.utc)


@pytest.fixture
def h(tmp_path):
    runtime=new_supervisor_fictional_runtime(tmp_path)
    app=make_supervisor_fictional_app(runtime,port=PORT)
    app.config["TESTING"]=True
    client=app.test_client()
    base=f"http://127.0.0.1:{PORT}"
    home=client.get("/",base_url=base)
    assert home.status_code==200
    nonce=re.search(
        r'data-preview-nonce="([^"]+)"',
        home.get_data(as_text=True),
    ).group(1)
    return runtime,client,nonce


def post(h,route,data=None,*,fixture="F1",nonce=True,origin=True):
    runtime,client,key=h
    headers={}
    if nonce:headers["X-Preview-Nonce"]=key
    if origin:headers["Origin"]=f"http://127.0.0.1:{PORT}"
    return client.post(
        "/supervisor/api/"+route,
        json={"fixture":fixture,**(data or {})},
        headers=headers,
        base_url=f"http://127.0.0.1:{PORT}",
    )


def ok(h,route,data=None,**kw):
    r=post(h,route,data,**kw)
    assert r.status_code==200, (route,r.status_code,r.json)
    return r.json


def wrong_option(q):
    return next(k for k in "ABCD" if k!=q.correct_answer)


def register(h,fixture="F1",*,economics=False):
    q=ok(h,"screening",fixture=fixture)["questions"]
    assert len(q)==8
    assert all("correct_answer" not in x for x in q)
    bank=h[0].store.bank
    answers={item.question_id:wrong_option(item)
             for item in bank.forms["screening"]}
    result=ok(h,"register",{
        "consent":True,"econ_course":economics,
        "screening_answers":{} if economics else answers,
    },fixture=fixture)
    return result


def answer(h,bank,fixture="F1",correct=True,req=None):
    current=ok(h,"item",fixture=fixture)
    if current["kind"]=="question" or (
            current["kind"]=="recovery" and current.get("question_id")):
        qid=current["question_id"]
        original=bank.get(
            qid,form="practice" if qid.startswith("QZ_")
            else ("pretest" if qid.startswith("PRE_") else "posttest")
        )
        selection=original.correct_answer if correct else wrong_option(original)
        if current.get("action")=="DROP_2" and selection not in current["options"]:
            selection=next(k for k in current["options"]
                           if k!=original.correct_answer)
    elif current["kind"]=="recovery":
        selection=None
        qid=None
    else:
        raise AssertionError("expected a question: "+str(current))
    result=ok(h,"answer",{
        "question_id":qid,"choice":selection,
        "request_id":req or "synthetic_"+str(len(h[0].store.export_anonymous_events(
            ref=h[0].roster[fixture][0],token=h[0].roster[fixture][1])))+"_q",
    },fixture=fixture)
    assert result["accepted"] and "correct" not in result
    return current


def test_http_security_and_no_human_enrollment(h):
    runtime,client,nonce=h
    assert post(h,"status",nonce=False).status_code==403
    assert post(h,"status",origin=False).status_code==403
    assert client.get(
        "/",base_url=f"http://127.0.0.1:{PORT}",
        environ_overrides={"REMOTE_ADDR":"203.0.113.12"},
    ).status_code==403
    assert client.get("/",base_url="http://example.invalid").status_code==403
    home=client.get("/",base_url=f"http://127.0.0.1:{PORT}")
    assert home.headers["X-Frame-Options"]=="DENY"
    assert "frame-ancestors 'none'" in home.headers["Content-Security-Policy"]
    assert home.headers["X-Synthetic-Only"]=="1"
    assert "script-src 'self'" in home.headers["Content-Security-Policy"]
    assert post(h,"human-enrollment").status_code==404
    assert post(h,"real-email").status_code==404
    assert ok(h,"status")["registered"] is False
    for path in ("/supervisor-fake.js","/supervisor-fake.css"):
        r=client.get(path,base_url=f"http://127.0.0.1:{PORT}")
        assert r.status_code==200


def test_excluded_economics_candidate_does_not_affect_rotation(h):
    assert register(h,"F1",economics=True)["eligible"] is False
    assert ok(h,"status",fixture="F1")["registered"] is False
    # F2 is now the first successful candidate and privately receives A.
    assert register(h,"F2")["eligible"] is True
    ref,token=h[0].roster["F2"]
    with h[0].store._tx() as db:
        row=db.execute("SELECT grp FROM participants WHERE learner_id=?",(
            ref,)).fetchone()
        assert row["grp"]=="A"
    assert "group" not in str(ok(h,"status",fixture="F2"))
    assert "token" not in str(ok(h,"status",fixture="F2"))


def test_consent_and_selected_question_integrity(h):
    questions=ok(h,"screening")["questions"]
    bank=h[0].store.bank
    answers={x.question_id:wrong_option(x)
             for x in bank.forms["screening"]}
    refused=post(h,"register",{
        "consent":False,"econ_course":False,
        "screening_answers":answers,
    })
    assert refused.status_code==409
    assert register(h)["eligible"] is True
    current=ok(h,"item")
    assert current["kind"]=="question"
    assert current["phase"]=="PRETEST"
    assert "correct_answer" not in current
    assert post(h,"answer",{
        "question_id":"PRE_C1_L2_02","choice":"A",
        "request_id":"wrong_sequence_001",
    }).status_code==409
    q=bank.get(current["question_id"],form="pretest")
    assert ok(h,"answer",{
        "question_id":current["question_id"],
        "choice":q.correct_answer,
        "request_id":"first_assess_001",
    })["accepted"]
    assert ok(h,"status")["index"]==1
    assert post(h,"register",{
        "consent":True,"econ_course":False,
        "screening_answers":answers,
    }).status_code==409


def test_complete_three_session_parallel_fictional_http(h):
    assert register(h)["eligible"]
    bank=h[0].store.bank
    nquiz=0
    for session,block in ((1,20),(2,20),(3,15)):
        if session==1:
            for _ in range(16):
                question=answer(h,bank)
                assert question["phase"]=="PRETEST"
        for _ in range(block):
            question=answer(h,bank)
            assert question["kind"]=="question"
            assert question["question_id"].startswith("QZ_")
            nquiz+=1
        if session==3:
            for _ in range(16):
                question=answer(h,bank)
                assert question["phase"]=="POSTTEST"
        survey=ok(h,"item")
        assert survey["kind"]=="survey"
        report=ok(h,"survey",{
            "values":[1,2,3,4,5,6],
            "request_id":"fatigue_session_"+str(session),
        })
        assert report["session_completed"]==session
        if session<3:
            assert ok(h,"item")["kind"]=="waiting_next_session"
            assert ok(h,"advance-fictional-clock")["session_started"]==session+1
    assert nquiz==55
    assert ok(h,"status")["phase"]=="DONE"
    assert ok(h,"item")["kind"]=="done"
    ref,token=h[0].roster["F1"]
    exported=h[0].store.export_anonymous_events(ref=ref,token=token)
    assert len(exported)==8+16+55+16+3
    assert "email" not in str(exported).lower()
    assert "example.test" not in str(exported)


def test_four_step_recovery_is_not_skippable_in_http(h):
    assert register(h)["eligible"]
    bank=h[0].store.bank
    for _ in range(16):
        answer(h,bank,correct=True)
    first=answer(h,bank,correct=False)
    second=answer(h,bank,correct=False)
    assert first["question_id"]!=second["question_id"]
    resource=ok(h,"item")
    assert resource["action"]=="CONCEPT_SUMMARY"
    assert resource["content_status"]=="REQUIRES_INDEPENDENT_REVIEW"
    forged=post(h,"answer",{
        "question_id":"QZ_C1_L1_06","choice":"A",
        "request_id":"skip_recovery_1",
    })
    assert forged.status_code==409
    answer(h,bank)
    drop=ok(h,"item")
    assert drop["action"]=="DROP_2"
    assert len(drop["options"])==2
    answer(h,bank)
    assert ok(h,"item")["action"]=="WORKED_EXAMPLE"
    answer(h,bank)
    assert ok(h,"item")["action"]=="SOCRATIC_HINT"
    answer(h,bank)
    assert ok(h,"status")["phase"]=="QUIZ"
    with h[0].store._tx() as db:
        snap=h[0].store._state(db,h[0].roster["F1"][0])
        assert snap["engine"]["question_in_session"]==2
