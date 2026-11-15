"""Researcher-only read-only mastery dashboard; separate from participant portal."""
from __future__ import annotations

from base64 import b64encode
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from src.prototype.supervisor_research_monitor import (
    ITERATIONS, make_monitor_app, password_hash, password_matches,
)

CONCEPTS=[f"C{i}" for i in range(1,9)]
SECRET="Very-Private-Researcher-Password-2026"
BASE="http://127.0.0.1:8790"
ADMIN=BASE+"/admin/"


def make_test_db(tmp_path):
    path=tmp_path/"supervisor_operational_study.sqlite3"
    db=sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE participants(
            learner_id TEXT,grp TEXT,status TEXT);
        CREATE TABLE learner_state(
            learner_id TEXT,session_no INTEGER,step TEXT,
            updated_at TEXT,state_json TEXT);
        CREATE TABLE events(
            event_id INTEGER PRIMARY KEY,learner_id TEXT,
            session_no INTEGER,action_type TEXT,concept_id TEXT,
            bloom_level INTEGER,answered_at TEXT,phase TEXT,is_correct INTEGER,
            question_id TEXT,response_time_ms INTEGER);
        CREATE TABLE state_history(event_id INTEGER,state_json TEXT);
        CREATE TABLE sessions(learner_id TEXT,session_no INTEGER,
            started_at TEXT,ended_at TEXT,status TEXT);
    """)
    first=json.dumps({"engine":{"mastery":{c:.4 for c in CONCEPTS}}})
    after=json.dumps({"engine":{"mastery":{
        c:(.53 if c=="C1" else .4) for c in CONCEPTS
    }}})
    db.execute("INSERT INTO participants VALUES('STUDY_P001','A','active')")
    db.execute("INSERT INTO learner_state VALUES(?,?,?,?,?)",
               ("STUDY_P001",1,"QUIZ","2026-11-12T20:00:00+00:00",after))
    db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?)",
               (1,"STUDY_P001",1,"QUESTION","C1",1,
                "2026-11-12T20:00:00+00:00","QUIZ",1,"QZ_C1_L1_01",5300))
    db.execute("INSERT INTO sessions VALUES(?,?,?,?,?)",
               ("STUDY_P001",1,"2026-11-12T19:59:00+00:00",
                None,"in_progress"))
    db.execute("INSERT INTO state_history VALUES(1,?)",(after,))
    db.commit();db.close()
    return path


def auth(password=SECRET,username="researcher"):
    b64=b64encode((username+":"+password).encode("utf-8")).decode("ascii")
    return {"Authorization":"Basic "+b64}


def test_password_hash_is_salted_and_researcher_only():
    h1=password_hash(SECRET)
    h2=password_hash(SECRET)
    assert h1 != h2 and len(h1)<160
    assert str(ITERATIONS) in h1
    assert password_matches(SECRET,h1)
    assert not password_matches("wrong password",h1)
    with pytest.raises(ValueError):
        password_hash("weak")
    with pytest.raises(ValueError):
        password_matches(SECRET,"nonsense")


def test_monitor_does_not_expose_data_without_independent_auth(tmp_path):
    app=make_monitor_app(make_test_db(tmp_path),
                         admin_password_hash=password_hash(SECRET))
    client=app.test_client()
    for endpoint in ("/admin/","/admin/app.js","/admin/app.css",
                     "/admin/api/participants","/admin/api/mastery/STUDY_P001"):
        r=client.get(endpoint,base_url=BASE)
        assert r.status_code==401,endpoint
        assert r.headers.get("Cache-Control","").startswith("no-store")
        assert "Basic" in r.headers.get("WWW-Authenticate","")
        wrong=client.get(endpoint,headers=auth("wrong"),base_url=BASE)
        assert wrong.status_code==401,endpoint
    assert client.get("/admin/api/participants",headers=auth(username="participant"),
                      base_url=BASE).status_code==401
    assert client.get("/admin/api/participants",headers=auth(),
                      base_url=BASE,environ_base={"REMOTE_ADDR":"203.0.113.8"}).status_code==403
    assert client.post("/admin/api/participants",headers=auth(),
                       base_url=BASE).status_code==405
    assert client.get("/admin/api/mastery/not-valid",headers=auth(),
                      base_url=BASE).status_code==404


def test_live_mastery_curve_and_participants_are_pseudonymous_and_read_only(tmp_path):
    path=make_test_db(tmp_path)
    app=make_monitor_app(path,admin_password_hash=password_hash(SECRET))
    client=app.test_client()
    before=path.read_bytes()
    students=client.get("/admin/api/participants",headers=auth(),base_url=BASE)
    assert students.status_code==200
    assert students.json["contains_pii"] is False
    assert students.json["refresh_seconds"]==5
    assert students.json["participants"][0]["grp"]=="A"
    assert students.json["participants"][0]["regular_answers_by_session"]=={"1":1}
    response=client.get("/admin/api/mastery/STUDY_P001",headers=auth(),base_url=BASE)
    assert response.status_code==200
    assert response.json["arm"]=="A"
    assert len(response.json["points"])==1
    assert response.json["points"][0]["response_seconds"]==5.3
    assert response.json["sessions"][0]["quiz_correct"]==1
    assert response.json["sessions"][0]["question_answer_seconds"]==5.3
    timing=client.get("/admin/api/question-timings.csv",headers=auth(),base_url=BASE)
    assert timing.status_code==200
    assert "5.3" in timing.get_data(as_text=True)
    summary=client.get("/admin/api/session-metrics.csv",headers=auth(),base_url=BASE)
    assert summary.status_code==200
    assert "STUDY_P001" in summary.get_data(as_text=True)
    assert "email" not in summary.get_data(as_text=True)
    assert response.json["points"][0]["mastery"]["C1"]==.53
    assert len(response.json["points"][0]["mastery"])==8
    assert response.json["x_axis"].startswith("Scored")
    assert "BKT" in response.json["y_axis"]
    assert "email" not in str(response.json).casefold()
    assert "token" not in str(response.json).casefold()
    assert path.read_bytes()==before, "dashboard must never modify research DB"
    for asset in ("/admin/","/admin/app.js","/admin/app.css"):
        assert client.get(asset,headers=auth(),base_url=BASE).status_code==200


def test_monitor_rejects_other_database_and_never_attaches_contacts(tmp_path):
    path=tmp_path/"supervisor_operational_contacts.sqlite3"
    path.write_bytes(b"not a study database")
    with pytest.raises(ValueError,match="research-only"):
        make_monitor_app(path,admin_password_hash=password_hash(SECRET))
    study=make_test_db(tmp_path)
    with pytest.raises(ValueError,match="research-only"):
        make_monitor_app(study.parent / "missing.sqlite3",
                         admin_password_hash=password_hash(SECRET))
    link=tmp_path/"study_link.sqlite3"
    link.symlink_to(study)
    with pytest.raises(ValueError,match="research-only"):
        make_monitor_app(link,admin_password_hash=password_hash(SECRET))


def test_researcher_js_and_service_remain_off_public_caddy_route(tmp_path):
    module=Path(__file__).resolve().parents[1]
    caddy=(module/"ops/supervisor/install_staging.sh").read_text()
    enable=(module/"ops/supervisor/enable_researcher_dashboard.sh").read_text()
    js=(module/"src/prototype/static/supervisor_research_monitor.js").read_text()
    assert "8790" not in caddy
    assert "--bind 127.0.0.1:8790" in enable
    assert "curl -sS -o /dev/null" in enable
    assert "401" in enable
    assert "setInterval(" in js and "5000" in js
    assert "mastery" in js
    assert "/admin/api/mastery/" in js
    assert "location.href" not in js
    assert "no_real_participant_enrollment" not in enable
    subprocess.run(["bash","-n",str(module/"ops/supervisor/enable_researcher_dashboard.sh")],
                   check=True)
