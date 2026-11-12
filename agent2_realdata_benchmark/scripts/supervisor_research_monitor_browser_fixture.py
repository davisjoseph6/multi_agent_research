"""Disposable synthetic SQLite fixture for a real-browser dashboard smoke test.

NEVER use this launcher with participant data. It creates a temporary
in-memory-like private study database in a temp directory and binds to
127.0.0.1 only. A background fixture writer mimics a student quiz answer.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import tempfile
from threading import Thread
import time

from src.prototype.supervisor_research_monitor import (
    make_monitor_app, password_hash,
)

TEST_ONLY_SECRET="CI-Only-Researcher-Password-Not-Production-2026"
CONCEPTS=[f"C{i}" for i in range(1,9)]


def prepare(path):
    db=sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE participants(learner_id TEXT,grp TEXT,status TEXT);
        CREATE TABLE learner_state(learner_id TEXT,session_no INTEGER,
             step TEXT,updated_at TEXT,state_json TEXT);
        CREATE TABLE events(event_id INTEGER PRIMARY KEY,learner_id TEXT,
             session_no INTEGER,action_type TEXT,concept_id TEXT,
             bloom_level INTEGER,answered_at TEXT,phase TEXT,is_correct INTEGER);
        CREATE TABLE state_history(event_id INTEGER,state_json TEXT);
    """)
    first=json.dumps({"engine":{"mastery":{c:.35 for c in CONCEPTS}}})
    db.execute("INSERT INTO participants VALUES('STUDY_P001','A','active')")
    db.execute("INSERT INTO learner_state VALUES(?,?,?,?,?)",
               ("STUDY_P001",1,"QUIZ","2026-11-12T20:00:00+00:00",first))
    db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?)",
               (1,"STUDY_P001",1,"QUESTION","C1",1,
                "2026-11-12T20:00:00+00:00","QUIZ",1))
    db.execute("INSERT INTO state_history VALUES(1,?)",(first,))
    db.commit();db.close()


def add_second_answer(path):
    time.sleep(4)
    after=json.dumps({"engine":{"mastery":{
        c:(.66 if c=="C1" else .35) for c in CONCEPTS
    }}})
    db=sqlite3.connect(path,timeout=15)
    db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?)",
               (2,"STUDY_P001",1,"QUESTION","C1",1,
                "2026-11-12T20:01:00+00:00","QUIZ",1))
    db.execute("INSERT INTO state_history VALUES(2,?)",(after,))
    db.execute("UPDATE learner_state SET updated_at=?,state_json=?",
               ("2026-11-12T20:01:00+00:00",after))
    db.commit();db.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8795)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="supervisor-monitor-browser-") as tmp:
        path=Path(tmp)/"supervisor_operational_study.sqlite3"
        prepare(path)
        Thread(target=add_second_answer,args=(path,),daemon=True).start()
        app=make_monitor_app(
            path,admin_password_hash=password_hash(TEST_ONLY_SECRET),
        )
        app.run(host="127.0.0.1",port=args.port,debug=False,use_reloader=False)


if __name__=="__main__":
    main()
