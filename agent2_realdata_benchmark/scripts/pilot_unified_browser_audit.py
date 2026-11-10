"""Read-only, identifier-free completion audit for the fictional browser.

No Flask routes, randomization, consent, participant data collection, or
database writes. Only a preexisting unified synthetic SQLite database named
fictional_admission.sqlite3 is accepted. Safe to run while the 127.0.0.1:8767
fictional service is online (SQLite consistent snapshot).

Run from agent2_realdata_benchmark:
  python -m scripts.pilot_unified_browser_audit --db /absolute/path/to/fictional_admission.sqlite3
  python -m scripts.pilot_unified_browser_audit --db /absolute/path/to/fictional_admission.sqlite3 --require-complete

The report deliberately excludes internal IDs, treatment assignments,
tokens, answers, and content. This is NOT a production security/privacy audit.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sqlite3


class FictionalAuditError(ValueError):
    """The source is not a valid, internally consistent fictional study."""


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def _check_time(value: str) -> None:
    try:
        when = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise FictionalAuditError("fictional timestamp invalid") from exc
    if when.tzinfo is None or when.utcoffset() is None:
        raise FictionalAuditError("fictional timestamp must include timezone")


def _read_config(db) -> None:
    admission = db.execute(
        "SELECT config FROM admission_config WHERE id=1"
    ).fetchone()
    unified = db.execute(
        "SELECT value FROM unified_config WHERE id=1"
    ).fetchone()
    pilot = db.execute("SELECT version FROM pilot_meta WHERE id=1").fetchone()
    if admission is None or unified is None or pilot is None:
        raise FictionalAuditError("required synthetic configuration missing")
    try:
        ac = json.loads(admission["config"])
        uc = json.loads(unified["value"])
    except (TypeError, ValueError) as exc:
        raise FictionalAuditError("invalid fictional configuration JSON") from exc
    bank_prefix = "SYNTHETIC_ONLY_PILOT_FLOW_V1_NOT_APPROVED_95_ITEM_BANK_"
    bank_version = pilot["version"]
    if (ac.get("schema") != "IJCAI2027_SYNTHETIC_ADMISSION_V1"
            or ac.get("synthetic_only") is not True
            or uc.get("version") != "SYNTHETIC_UNIFIED_SQLITE_V1_NOT_APPROVED"
            or type(bank_version) is not str
            or not bank_version.startswith(bank_prefix)
            or len(bank_version[len(bank_prefix):]) != 64
            or any(c not in "0123456789abcdef"
                   for c in bank_version[len(bank_prefix):])):
        raise FictionalAuditError("not a recognized synthetic bank-bound schema")


def _event_integrity(db) -> int:
    previous = "0" * 64
    count = 0
    for event in db.execute(
        "SELECT pid,at,kind,payload,prev_hash,event_hash "
        "FROM admission_events ORDER BY seq"
    ):
        try:
            payload = json.loads(event["payload"])
            _check_time(event["at"])
        except (TypeError, ValueError) as exc:
            raise FictionalAuditError("synthetic audit event malformed") from exc
        digest = sha256(_json({
            "pid": event["pid"], "at": event["at"],
            "kind": event["kind"], "payload": payload,
            "prev_hash": previous,
        }).encode("utf-8")).hexdigest()
        if event["prev_hash"] != previous or event["event_hash"] != digest:
            raise FictionalAuditError("synthetic admission event chain invalid")
        previous = digest
        count += 1
    return count


def _audit_snapshot(db) -> dict:
    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise FictionalAuditError("fictional SQLite integrity check failed")
    if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise FictionalAuditError("fictional foreign key violation")
    _read_config(db)
    events = _event_integrity(db)
    counts = {}
    for table in ("admission_people", "pilot_people",
                  "unified_links", "unified_demo_roster"):
        counts[table] = db.execute(
            "SELECT COUNT(*) FROM " + table
        ).fetchone()[0]
    if counts != {
        "admission_people": 9, "pilot_people": 9,
        "unified_links": 9, "unified_demo_roster": 3,
    }:
        raise FictionalAuditError("expected only the nine-record fictional cohort")

    rows = db.execute(
        "SELECT r.fixture,r.admission_pid,l.learning_pid,l.arm,"
        "s.arm AS assigned,p.status,p.consent_at,"
        "a.arm AS policy_arm,a.policy,learning.state "
        "FROM unified_demo_roster AS r "
        "JOIN admission_people AS p ON p.pid=r.admission_pid "
        "JOIN unified_links AS l ON l.admission_pid=r.admission_pid "
        "JOIN admission_slots AS s ON s.pid=r.admission_pid "
        "JOIN pilot_three_arm_people AS a ON a.pid=l.learning_pid "
        "JOIN pilot_people AS learning ON learning.pid=l.learning_pid "
        "ORDER BY r.fixture"
    ).fetchall()
    if len(rows) != 3 or [x["fixture"] for x in rows] != ["F1", "F2", "F3"]:
        raise FictionalAuditError("fictional browser roster invalid")
    if len({row["arm"] for row in rows}) != 3:
        raise FictionalAuditError("browser fixtures do not represent three arms")

    output = {}
    all_complete = True
    questions_total = 0
    mvas_total = 0
    for row in rows:
        if (not row["admission_pid"].startswith("SYN_ADMISSION_")
                or not row["learning_pid"].startswith("SYN_PILOT_")
                or row["status"] != "active"
                or row["consent_at"] is None
                or row["arm"] not in ("A", "B", "C")
                or row["arm"] != row["assigned"]
                or row["arm"] != row["policy_arm"]):
            raise FictionalAuditError("fictional study link or consent inconsistency")
        try:
            stored_policy = json.loads(row["policy"])
            state = json.loads(row["state"])
        except (TypeError, ValueError) as exc:
            raise FictionalAuditError("fictional learning record malformed") from exc
        if stored_policy.get("arm") != row["arm"]:
            raise FictionalAuditError("concealed treatment assignment mismatch")
        if state.get("stage") not in (
            "pretest", "practice", "mvas_pre", "mvas_post",
            "posttest", "awaiting_visit", "complete",
        ):
            raise FictionalAuditError("fictional learning stage invalid")
        session = state.get("session")
        started = state.get("visit_started_at")
        finished = state.get("visit_finished_at")
        if (type(session) is not int or session not in (1, 2, 3)
                or type(started) is not list or type(finished) is not list
                or len(started) != session or len(finished) > len(started)):
            raise FictionalAuditError("fictional visit progression invalid")
        for timestamp in started + finished:
            _check_time(timestamp)
        attendance = db.execute(
            "SELECT visit,started_at,finished_at FROM admission_visits "
            "WHERE pid=? ORDER BY visit",
            (row["admission_pid"],),
        ).fetchall()
        if len(attendance) != len(started):
            raise FictionalAuditError("attendance and learning start counts disagree")
        attendance_done = 0
        for index, visit in enumerate(attendance):
            if visit["visit"] != index + 1 or visit["started_at"] != started[index]:
                raise FictionalAuditError("fictional attendance start mismatch")
            if visit["finished_at"] is not None:
                _check_time(visit["finished_at"])
                if (index >= len(finished)
                        or datetime.fromisoformat(visit["finished_at"])
                           < datetime.fromisoformat(finished[index])):
                    # Older fictional browser code incorrectly reused the
                    # cumulative action count as a per-visit time offset.
                    # Never silently certify such a chronological violation
                    # or rewrite its historical event chain.
                    raise FictionalAuditError(
                        "fictional attendance predates learning completion"
                    )
                attendance_done += 1
        if (attendance_done > len(finished)
                or (len(finished) == session and attendance_done < session - 1)):
            raise FictionalAuditError("fictional attendance completion inconsistent")

        actions = Counter()
        completed = db.execute(
            "SELECT public FROM pilot_actions "
            "WHERE pid=? AND completed_at IS NOT NULL",
            (row["learning_pid"],),
        ).fetchall()
        for action in completed:
            try:
                item = json.loads(action["public"])
                kind, stage = item["action"], item["stage"]
            except (TypeError, ValueError, KeyError) as exc:
                raise FictionalAuditError("fictional completed action invalid") from exc
            if item.get("synthetic_only") is not True:
                raise FictionalAuditError("nonfictional action found")
            if "answer_id" in item or "correct" in item:
                raise FictionalAuditError("answer key exposed in fictional public action")
            if kind == "QUESTION":
                actions[stage] += 1
            elif kind == "MVAS":
                actions["MVAS"] += 1
            else:
                actions["other"] += 1
        if (actions["pretest"] > 16 or actions["practice"] > 55
                or actions["posttest"] > 16 or actions["MVAS"] > 6
                or actions["other"] > 6):
            raise FictionalAuditError("fictional action count outside protocol")
        question_count = sum(actions[k] for k in ("pretest", "practice", "posttest"))
        full = (state["stage"] == "complete" and session == 3
                and len(finished) == 3 and attendance_done == 3
                and actions["pretest"] == 16
                and actions["practice"] == 55
                and actions["posttest"] == 16
                and actions["MVAS"] == 6)
        if (state["stage"] == "complete" and not full
                and attendance_done == 3):
            raise FictionalAuditError("fictional complete record missing outcomes")
        output[row["fixture"]] = {
            "learning_stage": state["stage"],
            "current_visit": session,
            "learning_visits_finished": len(finished),
            "attendance_visits_finished": attendance_done,
            "questions_completed": question_count,
            "mvas_completed": actions["MVAS"],
            "fully_finished": full,
        }
        all_complete = all_complete and full
        questions_total += question_count
        mvas_total += actions["MVAS"]
    return {
        "kind": "READ_ONLY_UNIFIED_FICTIONAL_BROWSER_AUDIT",
        "result": "PASS_SYNTHETIC_ONLY",
        "source": "SQLITE_READ_ONLY_CONSISTENT_SNAPSHOT",
        "fictional_roster": output,
        "displayed_fixtures": 3,
        "fictional_cohort": 9,
        "total_questions_completed": questions_total,
        "total_mvas_completed": mvas_total,
        "all_three_complete": all_complete,
        "admission_hash_chain_events_checked": events,
        "sqlite_integrity": "ok",
        "human_enrollment_authorized": False,
        "production_security_certification": False,
        "no_study_records_or_assignments_exported": True,
    }


def audit_fictional_browser(path: str | Path) -> dict:
    """Never create, modify, seed, or update the source database."""
    path = Path(path)
    if (not path.is_absolute()
            or path.name != "fictional_admission.sqlite3"
            or not path.is_file()
            or any(p.is_symlink() for p in (path, *path.parents))):
        raise FictionalAuditError(
            "existing absolute nonsymlink fictional_admission.sqlite3 required"
        )
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        report = _audit_snapshot(db)
        db.rollback()
        return report
    except (sqlite3.Error, KeyError, TypeError) as exc:
        raise FictionalAuditError("synthetic database read/audit failed") from exc
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    try:
        result = audit_fictional_browser(args.db)
    except FictionalAuditError as exc:
        print(json.dumps({
            "result": "FAIL_SYNTHETIC",
            "error": str(exc),
            "human_enrollment_authorized": False,
        }))
        raise SystemExit(2) from None
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.require_complete and not result["all_three_complete"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
