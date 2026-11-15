"""Pseudonymized per-student research archive for authenticated staff only.

Only measurements from the split RESEARCH database are exported. Contact
emails, names, private invitation tokens, API secrets, consent PDFs, IPs and
free-text reflections are excluded. Raw event rows remain untouched.

The archive deliberately distinguishes *estimated* BKT probabilities from
observed correct/incorrect answers. The overall mastery indicator is the
arithmetic mean across the eight per-concept BKT estimates, not an independent
psychometric measure.
"""
from __future__ import annotations

import csv
from datetime import datetime
from io import BytesIO, StringIO
import json
import re
import sqlite3
from zipfile import ZipFile, ZIP_DEFLATED

from .supervisor_recruitment_metrics import mastery_series, inter_answer_times
from .supervisor_trace_engine import CONCEPT_IDS


_EVENT_COLUMNS = (
    "event_id", "learner_id", "session_no", "shown_at", "answered_at",
    "response_time_ms", "phase", "block_index", "mode", "action_type",
    "question_id", "concept_id", "bloom_level", "options_shown",
    "answer_given", "is_correct", "content_id", "display_language",
    "mastery_before", "mastery_after", "D_before", "D_after", "bloom_after",
    "rule_tags", "trigger", "recovery_attempt", "recovery_outcome",
)
_TIMING_COLUMNS = (
    "learner_id", "session", "phase", "question_id", "event_id",
    "answered_at_utc", "response_latency_ms", "between_answers_ms",
    "between_answers_seconds", "between_answers_hours", "between_answers_days",
    "includes_breaks_and_interventions",
)
_SESSION_COLUMNS = (
    "learner_id", "arm", "session", "status", "scheduled_for_utc",
    "started_at_utc", "ended_at_utc", "session_elapsed_seconds",
    "gap_since_previous_session_end_seconds", "quiz_answer_count",
    "quiz_correct_count",
)
_MASTERY_COLUMNS = (
    "learner_id", "arm", "event_id", "index", "session", "action",
    "question_id", "answered_at_utc", "overall_bkt_mean",
    *CONCEPT_IDS,
)
_FATIGUE_COLUMNS = (
    "learner_id", "arm", "session", "submitted_at_utc", "time_ms",
    "Q1", "Q2", "Q3", "Q4", "Q5", "Q6",
)
_ASSESSMENT_COLUMNS = (
    "learner_id", "arm", "event_id", "session", "phase", "question_id",
    "concept_id", "bloom_level", "answer_given", "is_correct",
    "response_time_ms", "answered_at_utc",
)


def _safe(value):
    """Neutralize formula injection in string-valued downloaded CSV cells."""
    if value is None:
        return ""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _csv_bytes(columns, rows):
    out = StringIO(newline="")
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_safe(row.get(key)) for key in columns])
    return out.getvalue().encode("utf-8-sig")


def _elapsed(first, second):
    if not first or not second:
        return None
    return round((datetime.fromisoformat(second) -
                  datetime.fromisoformat(first)).total_seconds(), 6)


def build_student_research_archive(db: sqlite3.Connection, *, learner_id: str) -> bytes:
    """Build non-identifying, seven-file CSV+JSON ZIP from a read-only DB.

    Authorization is the responsibility of the HTTP endpoint. Validation here
    prevents arbitrary SQL/filename access even if invoked by another caller.
    The caller must not attach a contacts DB to the archive.
    """
    if type(learner_id) is not str or re.fullmatch(r"STUDY_P[0-9]{3,}", learner_id) is None:
        raise ValueError("invalid pseudonymous study participant ID")
    db.row_factory = sqlite3.Row
    person = db.execute(
        "SELECT learner_id,grp,status,registered_at,consent_version,"
        "consent_lang,study_language,screening_score,age,program,config_version,"
        "missed_sessions FROM participants WHERE learner_id=?",
        (learner_id,),
    ).fetchone()
    if person is None:
        raise ValueError("study participant not found")
    arm = person["grp"]
    if arm not in ("A", "B", "C"):
        raise ValueError("unknown randomized study arm")

    events = [dict(r) for r in db.execute(
        "SELECT " + ",".join(_EVENT_COLUMNS) + " FROM events "
        "WHERE learner_id=? ORDER BY event_id", (learner_id,),
    )]
    sessions = []
    previous_end = None
    for record in db.execute(
        "SELECT session_no,status,scheduled_for,started_at,ended_at "
        "FROM sessions WHERE learner_id=? ORDER BY session_no", (learner_id,),
    ):
        row = dict(record)
        session = row["session_no"]
        quiz = [event for event in events
                if event["session_no"] == session
                and event["phase"] == "QUIZ"
                and event["action_type"] == "QUESTION"]
        sessions.append(dict(
            learner_id=learner_id, arm=arm, session=session,
            status=row["status"], scheduled_for_utc=row["scheduled_for"],
            started_at_utc=row["started_at"], ended_at_utc=row["ended_at"],
            session_elapsed_seconds=_elapsed(row["started_at"], row["ended_at"]),
            gap_since_previous_session_end_seconds=(
                _elapsed(previous_end, row["started_at"])
                if previous_end and row["started_at"] else None
            ),
            quiz_answer_count=len(quiz),
            quiz_correct_count=sum(event["is_correct"] == 1 for event in quiz),
        ))
        if row["ended_at"]:
            previous_end = row["ended_at"]

    mastery = mastery_series(db, learner_id)
    trajectory = []
    for point in mastery["points"]:
        data = point["mastery"]
        if set(data) != set(CONCEPT_IDS):
            raise ValueError("historic mastery snapshot does not contain eight concepts")
        trajectory.append(dict(
            learner_id=learner_id, arm=arm, event_id=point.get("event_id"),
            index=point["index"], session=point["session"],
            action=point["action"], question_id=point.get("question_id"),
            answered_at_utc=point["answered_at"],
            overall_bkt_mean=round(
                sum(data[concept] for concept in CONCEPT_IDS)/len(CONCEPT_IDS),6
            ),
            **data,
        ))

    initial = db.execute(
        "SELECT h.state_json FROM state_history h "
        "JOIN events e ON e.event_id=h.event_id "
        "WHERE e.learner_id=? AND e.phase='PRETEST' "
        "ORDER BY e.event_id DESC LIMIT 1",
        (learner_id,),
    ).fetchone()
    initial_mastery = None
    if initial:
        model = json.loads(initial["state_json"]).get("engine")
        estimate = model.get("mastery") if isinstance(model,dict) else None
        if isinstance(estimate,dict) and set(CONCEPT_IDS) == set(estimate):
            initial_mastery = {key:round(float(estimate[key]),6)
                               for key in CONCEPT_IDS}
    fatigue = [
        dict(learner_id=learner_id,arm=arm,session=r["session_no"],
             submitted_at_utc=r["submitted_at"],time_ms=r["time_ms"],
             **{f"Q{i}":r[f"Q{i}"] for i in range(1,7)})
        for r in db.execute(
            "SELECT session_no,submitted_at,time_ms,Q1,Q2,Q3,Q4,Q5,Q6 "
            "FROM surveys WHERE learner_id=? ORDER BY session_no",(learner_id,),
        )
    ]
    assessments = [
        dict(learner_id=learner_id,arm=arm,event_id=r["event_id"],
             session=r["session_no"],phase=r["phase"],
             question_id=r["question_id"],concept_id=r["concept_id"],
             bloom_level=r["bloom_level"],answer_given=r["answer_given"],
             is_correct=r["is_correct"],response_time_ms=r["response_time_ms"],
             answered_at_utc=r["answered_at"])
        for r in events if r["phase"] in ("SCREENING", "PRETEST", "POSTTEST")
        and r["question_id"]
    ]
    timings = inter_answer_times(db,learner_id=learner_id)
    # A nonempty archive must not contain actual school or Gmail addresses,
    # direct identifiers, access tokens, raw written reflections or cookies.
    metadata = {
        "schema": "IJCAI_2027_PSEUDONYMIZED_STUDENT_EXPORT_V1",
        "learner_id": learner_id,
        "arm": arm,
        "arm_label": {"A":"Adaptive recovery","B":"Greedy","C":"Fixed sequence"}[arm],
        "status": person["status"],
        "registration_at_utc": person["registered_at"],
        "consent_version": person["consent_version"],
        "consent_language": person["consent_lang"],
        "current_study_language": person["study_language"],
        "screening_score": person["screening_score"],
        "age": person["age"],
        "program": person["program"],
        "configuration_version": person["config_version"],
        "missed_sessions": person["missed_sessions"],
        "initial_bkt_mastery": initial_mastery,
        "initial_overall_bkt_mean": (
            round(sum(initial_mastery.values())/len(CONCEPT_IDS),6)
            if initial_mastery else None
        ),
        "session_count_planned": 3,
        "session_sequence": {
            "1":["PRETEST","QUIZ","SURVEY"],
            "2":["QUIZ","SURVEY"],
            "3":["QUIZ","POSTTEST","SURVEY"],
        },
        "quiz_bkt_mastery_is_estimated_not_measured_knowledge": True,
        "overall_bkt_definition": "Arithmetic mean of eight concept BKT estimates",
        "question_interval_definition": (
            "Elapsed calendar time between consecutive scored assessment/practice "
            "QUESTION answers, including breaks and cross-session gaps. "
            "Not equivalent to item response latency."
        ),
        "free_text_reflections_omitted_for_pseudonymization": True,
        "direct_contact_data_omitted": True,
        "student_armed_blinding_retained": True,
        "file_rows": {
            "event_log.csv":len(events),
            "mastery_progression.csv":len(trajectory),
            "question_intervals.csv":len(timings),
            "session_timings.csv":len(sessions),
            "fatigue.csv":len(fatigue),
            "assessments.csv":len(assessments),
        },
    }
    archive = BytesIO()
    with ZipFile(archive,mode="w",compression=ZIP_DEFLATED,compresslevel=6) as zf:
        zf.writestr("research_metadata.json",json.dumps(metadata,indent=2,ensure_ascii=False))
        for name, columns, rows in (
            ("event_log.csv",_EVENT_COLUMNS,events),
            ("mastery_progression.csv",_MASTERY_COLUMNS,trajectory),
            ("question_intervals.csv",_TIMING_COLUMNS,timings),
            ("session_timings.csv",_SESSION_COLUMNS,sessions),
            ("fatigue.csv",_FATIGUE_COLUMNS,fatigue),
            ("assessments.csv",_ASSESSMENT_COLUMNS,assessments),
        ):
            zf.writestr(name,_csv_bytes(columns,rows))
    return archive.getvalue()
