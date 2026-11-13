"""Researcher-authorized timing summaries computed from immutable events.

Inter-answer durations are calendar elapsed time, not item response latency.
They are shown in decimal ms, seconds, hours and days as requested.
Never join identifying contacts in this research-only helper.
"""
from __future__ import annotations

from datetime import datetime
import json
import sqlite3

from .supervisor_trace_engine import CONCEPT_IDS


def inter_answer_times(db: sqlite3.Connection, *, learner_id: str | None = None):
    if learner_id is not None and (
        type(learner_id) is not str or not learner_id.startswith("STUDY_P")
    ):
        raise ValueError("invalid learner reference")
    query=(
        "SELECT learner_id,session_no,phase,question_id,answered_at,"
        "response_time_ms,event_id FROM events "
        "WHERE question_id IS NOT NULL AND action_type='QUESTION' "
        "AND phase IN ('PRETEST','QUIZ','POSTTEST') "
        "AND (? IS NULL OR learner_id=?) "
        "ORDER BY learner_id,event_id"
    )
    previous={}
    result=[]
    for row in db.execute(query,(learner_id,learner_id)):
        key=row["learner_id"]
        answered=datetime.fromisoformat(row["answered_at"])
        earlier=previous.get(key)
        delta=None if earlier is None else max(0.0,(answered-earlier).total_seconds())
        previous[key]=answered
        result.append({
            "learner_id":key,"session":row["session_no"],"phase":row["phase"],
            "question_id":row["question_id"],"event_id":row["event_id"],
            "answered_at_utc":row["answered_at"],
            "response_latency_ms":row["response_time_ms"],
            "between_answers_ms":None if delta is None else round(delta*1000,3),
            "between_answers_seconds":None if delta is None else round(delta,6),
            "between_answers_hours":None if delta is None else round(delta/3600,9),
            "between_answers_days":None if delta is None else round(delta/86400,11),
            "includes_breaks_and_interventions":True,
        })
    return result


def mastery_series(db: sqlite3.Connection, learner_id: str):
    row=db.execute(
        "SELECT p.learner_id,p.grp,p.status,l.step,l.session_no "
        "FROM participants p JOIN learner_state l USING(learner_id) "
        "WHERE p.learner_id=?",(learner_id,)
    ).fetchone()
    if row is None:
        raise ValueError("participant not found")
    points=[]
    events=db.execute(
        "SELECT e.event_id,e.session_no,e.action_type,e.answered_at,"
        "e.question_id,h.state_json FROM events e "
        "JOIN state_history h USING(event_id) WHERE e.learner_id=? "
        "AND e.phase='QUIZ' AND e.action_type IN "
        "('QUESTION','DROP_2','SOCRATIC_HINT') AND e.is_correct IS NOT NULL "
        "ORDER BY e.event_id",(learner_id,)
    ).fetchall()
    for n,event in enumerate(events,1):
        state=json.loads(event["state_json"])
        model=state.get("engine")
        mastery=model.get("mastery") if isinstance(model,dict) else None
        if not isinstance(mastery,dict):
            continue
        points.append({
            "index":n,"session":event["session_no"],
            "action":event["action_type"],"answered_at":event["answered_at"],
            "mastery":{concept:round(float(mastery[concept]),6)
                       for concept in CONCEPT_IDS}
        })
    return {
        "learner_id":row["learner_id"],"arm":row["grp"],
        "status":row["status"],"stage":row["step"],
        "session":row["session_no"],"points":points,
        "concepts":list(CONCEPT_IDS),"observational_only":True,
        "metric":"Estimated BKT mastery, not measured knowledge",
    }
