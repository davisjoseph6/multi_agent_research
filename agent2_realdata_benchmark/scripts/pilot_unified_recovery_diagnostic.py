"""Read-only, private diagnostic for the EXISTING unified fictional port-8767 DB.

It does not contact port 8767 or 8077, change policy, alter a database,
reveal invitation tokens, export full responses or disclose correct answers.
Shows why a fictional learner saw no recovery actions: identify which alias
is Arm A and count incorrect practice responses vs selected POMCP resources.

Run on the VPS as the same user that owns the fictional DB:
  python -m scripts.pilot_unified_recovery_diagnostic \
    --db /home/davis/ijcai_unified_browser_20261110/state/fictional_admission.sqlite3

Optional PRIVATE operator-only alias mapping:
  ... --show-arm

Run only against synthetic, previously seeded fictional_admission.sqlite3.
This is not independent research, pedagogy, privacy or security certification.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

from src.prototype.study_v2 import RECOVERY_ACTIONS


class FictionalRecoveryDiagnosticError(ValueError):
    pass


def _required_json(value: str, label: str) -> dict:
    try:
        result = json.loads(value)
        if type(result) is not dict:
            raise ValueError("not an object")
        return result
    except (ValueError, TypeError) as exc:
        raise FictionalRecoveryDiagnosticError(
            "malformed synthetic " + label
        ) from exc


def inspect_fictional_recovery(db_path: Path, *, show_arm: bool = False) -> dict:
    db_path = Path(db_path)
    if (not db_path.is_absolute() or not db_path.is_file()
            or db_path.name != "fictional_admission.sqlite3"
            or any(part.is_symlink() for part in (db_path, *db_path.parents))):
        raise FictionalRecoveryDiagnosticError(
            "existing nonsymlink absolute fictional_admission.sqlite3 required"
        )
    db = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise FictionalRecoveryDiagnosticError("SQLite integrity failure")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise FictionalRecoveryDiagnosticError("foreign key violation")

        ac = db.execute("SELECT config FROM admission_config WHERE id=1").fetchone()
        uc = db.execute("SELECT value FROM unified_config WHERE id=1").fetchone()
        if ac is None or uc is None:
            raise FictionalRecoveryDiagnosticError("synthetic schema config missing")
        admission = _required_json(ac["config"], "admission config")
        unified = _required_json(uc["value"], "unified config")
        if (admission.get("schema") != "IJCAI2027_SYNTHETIC_ADMISSION_V1"
                or admission.get("synthetic_only") is not True
                or unified.get("version") != "SYNTHETIC_UNIFIED_SQLITE_V1_NOT_APPROVED"):
            raise FictionalRecoveryDiagnosticError("not the expected fictional unified schema")

        rows = db.execute(
            "SELECT r.fixture, t.arm, l.learning_pid, p.state "
            "FROM unified_demo_roster AS r "
            "JOIN unified_links AS l ON l.admission_pid=r.admission_pid "
            "JOIN pilot_three_arm_people AS t ON t.pid=l.learning_pid "
            "JOIN pilot_people AS p ON p.pid=l.learning_pid "
            "ORDER BY r.fixture"
        ).fetchall()
        if (len(rows) != 3
                or [r["fixture"] for r in rows] != ["F1", "F2", "F3"]
                or {r["arm"] for r in rows} != {"A", "B", "C"}
                or len({r["learning_pid"] for r in rows}) != 3):
            raise FictionalRecoveryDiagnosticError(
                "expected exactly three blinded F1/F2/F3 assignments, one of each arm"
            )

        per_fixture = {}
        aggregated = {}
        for row in rows:
            alias, arm, pid = row["fixture"], row["arm"], row["learning_pid"]
            state = _required_json(row["state"], "fictional learner state")
            actions = db.execute(
                "SELECT a.public,a.response,a.completed_at,s.selected "
                "FROM pilot_actions AS a "
                "JOIN pilot_three_arm_selected AS s ON s.action_id=a.action_id "
                "WHERE a.pid=? ORDER BY a.offered_at,a.action_id", (pid,),
            ).fetchall()
            offered = Counter()
            completed = Counter()
            wrong_practice = 0
            completed_practice = 0
            planner_normal_questions = 0
            planner_recovery_choices = 0
            for record in actions:
                public = _required_json(record["public"], "public action")
                selected = _required_json(record["selected"], "policy selection")
                kind = public.get("action")
                if kind != selected.get("action") or kind not in (
                    "QUESTION", "MVAS", *RECOVERY_ACTIONS,
                ):
                    raise FictionalRecoveryDiagnosticError(
                        "inconsistent or unknown synthetic action kind"
                    )
                offered[kind] += 1
                if record["completed_at"] is not None:
                    completed[kind] += 1
                if (kind == "QUESTION" and public.get("stage") == "practice"
                        and record["completed_at"] is not None):
                    completed_practice += 1
                    response = _required_json(record["response"], "practice response")
                    if response.get("correct") is False:
                        wrong_practice += 1
                if arm == "A" and selected.get("planning_trace") is not None:
                    if kind in RECOVERY_ACTIONS:
                        planner_recovery_choices += 1
                    elif kind == "QUESTION":
                        planner_normal_questions += 1

            offered_recoveries = {
                kind: offered[kind] for kind in RECOVERY_ACTIONS
            }
            completed_recoveries = {
                kind: completed[kind] for kind in RECOVERY_ACTIONS
            }
            detail = {
                "current_stage": state.get("stage"),
                "current_session": state.get("session"),
                "completed_practice_questions": completed_practice,
                "incorrect_practice_questions": wrong_practice,
                "recoveries_offered": offered_recoveries,
                "recoveries_completed": completed_recoveries,
                "planner_practice_choices_with_trace": planner_normal_questions,
                "planner_recovery_choices_with_trace": planner_recovery_choices,
                "no_recovery_offered": sum(offered_recoveries.values()) == 0,
            }
            if show_arm:
                detail["operator_private_arm"] = arm
            per_fixture[alias] = detail
            aggregated[arm] = {
                "completed_practice_questions": completed_practice,
                "incorrect_practice_questions": wrong_practice,
                "recovery_offered_total": sum(offered_recoveries.values()),
                "recovery_completed_total": sum(completed_recoveries.values()),
                "recovery_offered_by_type": offered_recoveries,
                "planner_practice_choices_with_trace": planner_normal_questions,
                "planner_recovery_choices_with_trace": planner_recovery_choices,
            }
        if set(aggregated) != {"A", "B", "C"}:
            raise FictionalRecoveryDiagnosticError("missing blinded treatment arm")
        db.rollback()
        return {
            "kind": "READ_ONLY_PRIVATE_UNIFIED_FICTIONAL_RECOVERY_DIAGNOSTIC",
            "result": "PASS_SYNTHETIC_INSPECTION",
            "application": "PORT_8767_UNIFIED_SYNTHETIC_SQLITE",
            "fictional_fixture_counts": per_fixture,
            "private_aggregate_by_arm": aggregated,
            "interpretation": (
                "Only Arm A may receive optional POMCP recovery. "
                "Arm B/C offer none by design. Even with practice errors "
                "Arm A can choose ordinary questions instead of resources."
            ),
            "all_three_have_zero_recoveries": all(
                summary["recovery_offered_total"] == 0
                for summary in aggregated.values()
            ),
            "human_enrollment_authorized": False,
            "operator_demo_8077_inspected": False,
            "no_study_record_or_secret_exported": True,
            "sqlite_read_only": True,
        }
    except sqlite3.Error as exc:
        raise FictionalRecoveryDiagnosticError(
            "failed to inspect expected synthetic database"
        ) from exc
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument(
        "--show-arm", action="store_true",
        help="operator only: print private F1/F2/F3 assignment",
    )
    args = parser.parse_args()
    try:
        report = inspect_fictional_recovery(args.db, show_arm=args.show_arm)
    except FictionalRecoveryDiagnosticError as exc:
        print(json.dumps({
            "result": "FAIL", "reason": str(exc),
            "human_enrollment_authorized": False,
        }))
        raise SystemExit(2) from None
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
