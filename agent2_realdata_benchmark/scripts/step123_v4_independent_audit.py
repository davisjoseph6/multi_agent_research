"""Read-only independent audit of a completed SYNTHETIC v3 SQLite rehearsal.

Does not use the trial runtime, any learner simulator, or a generated summary.
Cannot validate educational outcomes, model calibration, trial authorization,
real identities, privacy controls, or causal effects.

Usage: python -m scripts.step123_v4_independent_audit PATH_TO_SYNTHETIC_DB
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sqlite3

CONCEPTS = (
    "Utility", "Loss Aversion", "Anchoring", "Sunk Cost", "Framing",
    "Heuristics", "Prospect Theory", "Nudge Theory",
)
NORMAL_PER_SESSION = (20, 20, 15)
RECOVERY = frozenset(("CONCEPT_SUMMARY", "DROP_2", "WORKED_EXAMPLE", "SOCRATIC_HINT"))
TERMINAL = "COMPLETE"


class IntegrityError(ValueError):
    """A checked invariant is inconsistent with the synthetic protocol."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise IntegrityError(message)


def parse(value: str, context: str) -> dict:
    try:
        data = json.loads(value)
    except (ValueError, TypeError) as exc:
        raise IntegrityError(f"invalid JSON at {context}") from exc
    require(isinstance(data, dict), f"expected JSON object at {context}")
    return data


def _read(path: Path):
    if not path.is_file():
        raise IntegrityError("SQLite database does not exist")
    # Open in SQLite read-only mode. Avoid connecting through the engine.
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        required = {
            "synthetic_participants", "synthetic_responses",
            "synthetic_protocol_events", "synthetic_v3_config",
        }
        tables = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        require(required <= tables, "v3 synthetic schema is incomplete")
        config = db.execute("SELECT json FROM synthetic_v3_config WHERE id=1").fetchone()
        require(config is not None, "missing protocol configuration lock")
        config = parse(config[0], "synthetic_v3_config")
        require(config.get("protocol") == "synthetic_pomcp_v3_2026-10-29",
                "unexpected protocol version")
        require(config.get("pretest_bkt") == "posterior_only_v3",
                "baseline BKT model is not the corrected version")
        require(type(config.get("max_resources_per_session")) is int and
                0 <= config["max_resources_per_session"] <= 10,
                "invalid resource budget in config")
        participants = db.execute(
            "SELECT participant_id,arm,stage,session,index_in_stage,mastery_json,"
            "used_json,recovery_json,pending_json,item_bank_hash "
            "FROM synthetic_participants ORDER BY participant_id"
        ).fetchall()
        raw_events = db.execute(
            "SELECT seq,participant_id,event_json FROM synthetic_protocol_events ORDER BY seq"
        ).fetchall()
        raw_responses = db.execute(
            "SELECT request_id,participant_id,request_payload,response_payload "
            "FROM synthetic_responses ORDER BY participant_id,request_id"
        ).fetchall()
        foreign_key_errors = db.execute("PRAGMA foreign_key_check").fetchall()
    require(not foreign_key_errors, "foreign-key integrity violation")
    return config, participants, raw_events, raw_responses


def audit_database(path: str | Path) -> dict:
    """Verify per-person chronological protocol invariants, read-only.

    This verifies internal consistency, not authenticity: an adversary able to
    rewrite all database records can still fabricate a consistent database.
    """
    config, participants, raw_events, raw_responses = _read(Path(path))
    require(bool(participants), "database contains no synthetic participants")
    events = defaultdict(list)
    last_seq = 0
    for seq, pid, encoded in raw_events:
        require(seq > last_seq, "event sequence is not strictly increasing")
        last_seq = seq
        events[pid].append(parse(encoded, f"event seq {seq}"))
    response_counts = Counter()
    for rid, pid, encoded_payload, encoded_response in raw_responses:
        require(isinstance(rid, str) and rid, "empty request id")
        require(parse(encoded_payload, f"request {rid}") is not None, "invalid request")
        response = parse(encoded_response, f"response {rid}")
        require(response.get("accepted") is True, "rejected response in committed ledger")
        require("replayed" not in response, "replay marker stored as primary result")
        response_counts[pid] += 1

    results = Counter()
    per_arm = Counter()
    checked = set()
    total_resources = Counter()
    for pid, arm, stage, session, index, mastery_json, used_json, recovery_json, pending, bank_hash in participants:
        require(isinstance(pid, str) and pid.startswith("SYN_"), "non-synthetic participant found")
        require(pid not in checked, "duplicate participant")
        checked.add(pid)
        require(arm in {"A", "B", "C"}, f"invalid arm for {pid}")
        require(stage == "complete" and session == 3 and index == 0,
                f"{pid}: unfinished or invalid terminal state")
        if pending is not None:
            pending_action = parse(pending, f"pending {pid}")
            require(pending_action.get("action") == "COMPLETE",
                    f"{pid}: nonterminal pending action after completion")
        require(bank_hash == config["item_bank_hash"], f"{pid}: bank hash mismatch")
        mastery = parse(mastery_json, f"mastery {pid}")
        require(set(mastery) == set(CONCEPTS), f"{pid}: incorrect mastery dimensions")
        require(all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1
                    for v in mastery.values()), f"{pid}: invalid mastery probability")
        used = json.loads(used_json)
        require(isinstance(used, list) and len(used) == len(set(used)) == 55,
                f"{pid}: normal practice ID list incorrect")
        require(all(isinstance(item, str) and item.startswith("SYN_practice_") for item in used),
                f"{pid}: non-practice item in used list")
        require(isinstance(parse(recovery_json, f"recovery {pid}"), dict),
                f"{pid}: invalid recovery object")

        timeline = events.get(pid, [])
        require(len(timeline) >= 2 and timeline[0].get("type") == "enrolled",
                f"{pid}: missing enrollment event")
        require(timeline[0].get("arm") == arm, f"{pid}: enrollment arm mismatch")
        seen = {"pretest": set(), "posttest": set(), "practice": set()}
        normal = Counter()
        fatigue_sessions = Counter()
        resource_sessions = Counter()
        stages = []
        i = 1
        counted_responses = 0
        complete_seen = False
        while i < len(timeline):
            selected = timeline[i]
            require(selected.get("type") == "action_selected", f"{pid}: broken event pairing at {i}")
            kind = selected.get("action")
            form = selected.get("stage")
            sess = selected.get("session")
            require(form in {"pretest", "practice", "fatigue", "posttest", "complete"},
                    f"{pid}: invalid stage in action")
            if kind == TERMINAL:
                require(form == "complete" and i == len(timeline) - 1,
                        f"{pid}: terminal event is not last")
                complete_seen = True
                i += 1
                break
            require(i + 1 < len(timeline), f"{pid}: selected action without outcome")
            outcome = timeline[i + 1]
            recorded_type = outcome.get("type")
            if kind == "QUESTION":
                require(form in seen and recorded_type == "answer_recorded",
                        f"{pid}: wrong event for normal question")
                require(outcome.get("stage") == form and outcome.get("item_id") == selected.get("item_id"),
                        f"{pid}: selected-answer mismatch")
                item_id = outcome["item_id"]
                require(isinstance(item_id, str) and item_id.startswith(f"SYN_{form}_"),
                        f"{pid}: question form mismatch")
                require(item_id not in seen[form], f"{pid}: repeated {form} question")
                seen[form].add(item_id)
                normal[(form, sess)] += 1
            elif kind == "FATIGUE":
                require(form == "fatigue" and recorded_type == "fatigue_recorded" and outcome.get("session") == sess,
                        f"{pid}: fatigue event mismatch")
                values = outcome.get("values")
                require(isinstance(values, list) and len(values) == 6 and
                        all(type(x) is int and 1 <= x <= 5 for x in values),
                        f"{pid}: invalid fatigue answers")
                fatigue_sessions[sess] += 1
            elif kind in RECOVERY:
                require(arm == "A" and form == "practice", f"{pid}: recovery action in non-A arm")
                require(sess in (1, 2, 3), f"{pid}: invalid resource session")
                if kind == "DROP_2":
                    require(recorded_type == "answer_recorded" and
                            outcome.get("item_id") == selected.get("item_id") and
                            outcome.get("action_type") == "DROP_2",
                            f"{pid}: DROP_2 answer mismatch")
                else:
                    require(recorded_type == "synthetic_resource_acknowledged" and
                            outcome.get("action") == kind,
                            f"{pid}: recovery acknowledgement mismatch")
                resource_sessions[sess] += 1
                total_resources[arm] += 1
            else:
                raise IntegrityError(f"{pid}: unknown action {kind}")
            # Valid stages can recur across steps but not move backward.
            phase = {"pretest": 0, "practice": sess * 2 - 1,
                     "fatigue": sess * 2, "posttest": 7}[form]
            stages.append(phase)
            counted_responses += 1
            i += 2
        require(complete_seen, f"{pid}: terminal COMPLETE action missing")
        require(stages == sorted(stages), f"{pid}: session phases out of order")
        require(normal[("pretest", 0)] == 16 and normal[("posttest", 3)] == 16,
                f"{pid}: pre/post assessment counts incorrect")
        require(len(seen["pretest"] & seen["posttest"]) == 0,
                f"{pid}: assessment item overlap")
        for sess, expected in enumerate(NORMAL_PER_SESSION, 1):
            require(normal[("practice", sess)] == expected,
                    f"{pid}: incorrect practice count session {sess}")
            require(fatigue_sessions[sess] == 1, f"{pid}: fatigue missing or duplicated in session {sess}")
            require(resource_sessions[sess] <= config["max_resources_per_session"],
                    f"{pid}: excess resources in session {sess}")
        require(seen["practice"] == set(used), f"{pid}: used list does not match practice events")
        require(counted_responses == response_counts[pid],
                f"{pid}: response/event count mismatch")
        per_arm[arm] += 1
        results["pretest"] += 16
        results["posttest"] += 16
        results["practice"] += 55
        results["fatigue"] += 3

    require(set(events) == checked and set(response_counts) == checked,
            "orphan event or response participant")
    require(set(per_arm) == {"A", "B", "C"} and len(set(per_arm.values())) == 1,
            "incomplete or unbalanced synthetic mock allocation")
    return {
        "audit_version": "independent_sqlite_v4",
        "synthetic_only": True,
        "human_evidence": False,
        "passed": True,
        "participants": len(checked),
        "per_arm": dict(sorted(per_arm.items())),
        "normal_question_counts": dict(results),
        "resource_actions_by_arm": dict(sorted(total_resources.items())),
        "events": len(raw_events),
        "committed_requests": len(raw_responses),
        "model_hash": config["model_hash"],
        "bank_hash": config["item_bank_hash"],
        "limitations": (
            "Synthetic database consistency only; no tamper-proof provenance, "
            "no real participant outcomes, no clinical or educational validity."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    try:
        report = audit_database(args.database)
    except (IntegrityError, sqlite3.DatabaseError) as exc:
        parser.exit(2, f"AUDIT FAILED: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
