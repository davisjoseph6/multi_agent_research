"""Read-only acceptance audit of the *fictional* three-arm browser database.

This does not approve or authorize a human study and never opens a database
for writing. It checks structural consistency, not educational validity,
security certification, content approval, or a statistical study outcome.

The auditor deliberately does NOT import the browser runner, initialize an
engine, seed participants, or advance any visit.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3

from .pilot_three_arm_store_draft import POLICY_VERSION
from .study_v2 import RECOVERY_ACTIONS


class FictionalAuditError(ValueError):
    """The proposed database is not a valid fictional-browser audit target."""


def _read_time(value):
    when = datetime.fromisoformat(value)
    if when.tzinfo is None or when.utcoffset() is None:
        raise FictionalAuditError("fixture timestamp is not timezone aware")
    return when


def audit_fictional_database(path: str | Path) -> dict:
    """Audit a complete A/B/C fictional three-visit rehearsal, read only.

    Returns a detailed fictional-only PASS/FAIL report, including failures;
    an invalid path, wrong database name, or malformed SQLite schema raises.
    No personal identifiers, question texts, or answer keys are exported.
    """
    path = Path(path)
    if (path.name != "fictional_browser_preview.sqlite3"
            or path.is_symlink() or not path.is_file()):
        raise FictionalAuditError(
            "acceptance audit requires an existing, nonsymlink fictional_browser_preview.sqlite3"
        )
    failures: list[str] = []
    arms: dict[str, dict] = {}
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")  # single consistent read snapshot
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            failures.append("SQLite integrity_check failed")
        fk_issues = db.execute("PRAGMA foreign_key_check").fetchall()
        if fk_issues:
            failures.append("SQLite foreign-key integrity_check failed")
        config_row = db.execute(
            "SELECT config FROM pilot_three_arm_config WHERE id=1"
        ).fetchone()
        if config_row is None:
            raise FictionalAuditError("no pinned synthetic three-arm configuration")
        config = json.loads(config_row["config"])
        if config.get("version") != POLICY_VERSION:
            failures.append("three-arm synthetic policy version mismatch")
        if config.get("resource_budget_each_session") != 2:
            failures.append("unexpected synthetic recovery budget")
        if config.get("practice_counts") != [20, 20, 15]:
            failures.append("unexpected synthetic practice schedule")
        if config.get("simulation_count") != 41:
            failures.append("browser preview must use 41 synthetic simulations")

        people = db.execute(
            "SELECT a.arm,a.pid,p.state,a.policy FROM pilot_three_arm_people a "
            "JOIN pilot_people p ON p.pid=a.pid ORDER BY a.arm"
        ).fetchall()
        total_people = db.execute("SELECT COUNT(*) FROM pilot_people").fetchone()[0]
        if len(people) != 3 or total_people != 3 \
                or [p["arm"] for p in people] != ["A", "B", "C"]:
            failures.append("expected exactly three fictional people, one per arm")
        if len({p["pid"] for p in people}) != len(people):
            failures.append("duplicate fictional participant identifier")

        for person in people:
            arm, pid = person["arm"], person["pid"]
            problems: list[str] = []
            if not pid.startswith("SYN_PILOT_"):
                problems.append("participant ID is not synthetic")
            state = json.loads(person["state"])
            policy = json.loads(person["policy"])
            if policy.get("arm") != arm:
                problems.append("assigned arm differs from stored policy")
            if state.get("stage") != "complete" or state.get("session") != 3:
                problems.append("all three visits are not complete")

            start_times = state.get("visit_started_at", [])
            finish_times = state.get("visit_finished_at", [])
            if len(start_times) != 3 or len(finish_times) != 3:
                problems.append("must have three started and finished visits")
            else:
                try:
                    starts = [_read_time(s) for s in start_times]
                    finishes = [_read_time(s) for s in finish_times]
                    if any(fin < beg for beg, fin in zip(starts, finishes)):
                        problems.append("visit finishes before start")
                    for i in (1, 2):
                        gap = starts[i] - finishes[i - 1]
                        if not timedelta(hours=72) <= gap <= timedelta(hours=120):
                            problems.append(f"visit {i + 1} gap outside 72–120 hours")
                except (TypeError, ValueError) as error:
                    problems.append(f"invalid virtual timestamps: {error}")

            rows = db.execute(
                "SELECT a.action_id,a.public,a.response,a.offered_at,"
                "a.rendered_at,a.completed_at,s.selected "
                "FROM pilot_actions a LEFT JOIN pilot_three_arm_selected s "
                "ON s.action_id=a.action_id WHERE a.pid=?",
                (pid,),
            ).fetchall()
            counts = Counter()
            practice_by_visit = Counter()
            recovery_by_visit = Counter()
            fatigue_by_visit = Counter()
            practiced_ids = []
            for row in rows:
                if (row["rendered_at"] is None or row["completed_at"] is None
                        or row["response"] is None or row["selected"] is None):
                    problems.append("incomplete/render-missing/unbound synthetic action")
                    continue
                try:
                    offered = _read_time(row["offered_at"])
                    rendered = _read_time(row["rendered_at"])
                    finished = _read_time(row["completed_at"])
                    if not offered <= rendered <= finished:
                        problems.append("action clock order is invalid")
                    public = json.loads(row["public"])
                    response = json.loads(row["response"])
                    selected = json.loads(row["selected"])
                    kind, stage, visit = (
                        public["action"], public["stage"], public["session"],
                    )
                except (ValueError, TypeError, KeyError) as error:
                    problems.append(f"invalid action audit record: {error}")
                    continue
                if selected.get("action") != kind:
                    problems.append("selected action does not match public action")
                if not public.get("synthetic_only") or \
                        not public.get("draft_content_not_approved"):
                    problems.append("missing synthetic/draft disclosure")
                if "answer_id" in public or "correct" in public:
                    problems.append("public action exposes an answer key or correctness")
                if "answer_id" in public.get("question", {}) or \
                        "correct" in public.get("question", {}):
                    problems.append("public question exposes answer or correctness")
                counts[kind] += 1
                if kind == "QUESTION":
                    question = public.get("question", {})
                    item_id = question.get("item_id")
                    if (not item_id or selected.get("item_id") != item_id
                            or response.get("item_id") != item_id
                            or type(response.get("correct")) is not bool):
                        problems.append("scored question/action identity mismatch")
                    if stage == "pretest":
                        if visit != 1:
                            problems.append("pretest outside first visit")
                        counts["pretest"] += 1
                    elif stage == "posttest":
                        if visit != 3:
                            problems.append("posttest outside third visit")
                        counts["posttest"] += 1
                    elif stage == "practice":
                        if visit not in (1, 2, 3):
                            problems.append("practice outside three visit windows")
                        practice_by_visit[visit] += 1
                        practiced_ids.append(item_id)
                    else:
                        problems.append("question in unexpected stage")
                elif kind == "MVAS":
                    if stage not in ("mvas_pre", "mvas_post") or \
                            visit not in (1, 2, 3):
                        problems.append("fatigue instrument outside valid window")
                    fatigue_by_visit[(visit, stage)] += 1
                    if type(response.get("rating")) is not int or \
                            not 0 <= response["rating"] <= 100:
                        problems.append("invalid 0–100 M-VAS rating")
                elif kind in RECOVERY_ACTIONS:
                    if arm != "A" or stage != "practice" or \
                            visit not in (1, 2, 3):
                        problems.append("recovery offered to wrong arm/window")
                    if not public.get("resource", {}).get("resource_id"):
                        problems.append("recovery resource identity missing")
                    recovery_by_visit[visit] += 1
                    if kind == "DROP_2":
                        question = public.get("question", {})
                        if (not question or selected.get("item_id")
                                != question.get("item_id")
                                or type(response.get("correct")) is not bool):
                            problems.append("DROP_2 response or question mismatched")
                    elif response.get("status") not in ("completed", "skipped"):
                        problems.append("invalid recovery completion response")
                else:
                    problems.append("unknown synthetic action type")

            if counts["pretest"] != 16 or counts["posttest"] != 16:
                problems.append("pretest/posttest must contain exactly 16 scored questions")
            if tuple(practice_by_visit[v] for v in (1, 2, 3)) != (20, 20, 15):
                problems.append("expected 20,20,15 practice questions by visit")
            if len(practiced_ids) != 55 or len(set(practiced_ids)) != 55:
                problems.append("practice item IDs must be 55 distinct entries")
            if set(practiced_ids) != set(policy.get("used", [])):
                problems.append("private practice history does not match recorded actions")
            if any(recovery_by_visit[v] > 2 for v in (1, 2, 3)):
                problems.append("recovery budget exceeded two per visit")
            if arm != "A" and sum(recovery_by_visit.values()):
                problems.append("greedy/fixed arm received recovery resources")
            for visit in (1, 2, 3):
                for stage in ("mvas_pre", "mvas_post"):
                    if fatigue_by_visit[(visit, stage)] != 1:
                        problems.append(f"missing or duplicated {stage} in visit {visit}")
            ratings = state.get("ratings", [])
            if len(ratings) != 3 or any(
                len(pair) != 2 or any(
                    type(value) is not int or not 0 <= value <= 100
                    for value in pair
                ) for pair in ratings
            ):
                problems.append("state must have six valid M-VAS recordings")
            elif len(rows):
                # Cross-check that response values correspond to persisted
                # immutable state, not just six arbitrary form counts.
                for visit in (1, 2, 3):
                    for point, stage in enumerate(("mvas_pre", "mvas_post")):
                        matching = [
                            json.loads(row["response"])["rating"]
                            for row in rows if row["response"] and
                            json.loads(row["public"])["action"] == "MVAS" and
                            json.loads(row["public"])["stage"] == stage and
                            json.loads(row["public"])["session"] == visit
                        ]
                        if len(matching) != 1 or matching[0] != ratings[visit - 1][point]:
                            problems.append("fatigue response disagrees with saved state")
            expected_actions = 93 + sum(recovery_by_visit.values())
            if len(rows) != expected_actions:
                problems.append("action total inconsistent with 87 MCQs + six M-VAS + recovery")
            arms[arm] = {
                "result": "PASS" if not problems else "FAIL",
                "completed_actions": len(rows),
                "pretest_questions": counts["pretest"],
                "practice_by_visit": [practice_by_visit[v] for v in (1, 2, 3)],
                "posttest_questions": counts["posttest"],
                "mvas_responses": counts["MVAS"],
                "recovery_by_visit": [recovery_by_visit[v] for v in (1, 2, 3)],
                "fatigue_pairs": ratings,
                "fatigue_delta_by_visit": [
                    pair[1] - pair[0] for pair in ratings
                ] if len(ratings) == 3 and all(len(pair) == 2 for pair in ratings)
                else [],
                "issues": problems,
            }
            failures.extend(f"Arm {arm}: {issue}" for issue in problems)
        db.commit()
    except (sqlite3.DatabaseError, KeyError, ValueError, TypeError) as error:
        raise FictionalAuditError(
            "could not structurally inspect the fictional SQLite database"
        ) from error
    finally:
        db.close()
    return {
        "result": "PASS_SYNTHETIC_ONLY" if not failures else "FAIL_SYNTHETIC",
        "human_enrollment_authorized": False,
        "fictional_only": True,
        "virtual_time_only": True,
        "not_scientific_validation": True,
        "sqlite_integrity": integrity,
        "policy_version": config.get("version"),
        "arms": arms,
        "issues": failures,
    }
