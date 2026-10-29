"""Development-only simulated-trial integrity audit.

Uses synthetic enrollment identifiers and scripted answers.
Does not estimate intervention effects or use real participants.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from src.prototype.experimental_api import PREFIX, create_experimental_app
from src.prototype.item_bank import INSTRUCTIONAL_DEMO_ITEMS

ARMS = ("control", "fixed_summary", "adaptive_threshold")
PRIVATE_FIELDS = (
    "policy_mode", "participant_id", "mastery_belief",
    "correct_id", "simulated_action",
)


def _public(response, expected_status=200):
    assert response.status_code == expected_status, (
        response.status_code, response.get_data(as_text=True)
    )
    payload = response.get_json()
    assert isinstance(payload, dict)
    serialized = json.dumps(payload, sort_keys=True)
    assert all(field not in serialized for field in PRIVATE_FIELDS)
    return payload


def _endpoint(session_id, suffix):
    return f"{PREFIX}/sessions/{session_id}/{suffix}"


def _enroll(client, index, expected_status=201):
    return _public(
        client.post(
            f"{PREFIX}/enroll",
            json={"enrollment_request_id": f"step62-synthetic-{index:04d}"},
        ), expected_status,
    )["session_id"]


def _answer(client, session_id, position, choice):
    item_id = INSTRUCTIONAL_DEMO_ITEMS[position].item_id
    payload = {
        "item_id": item_id,
        "choice_id": choice,
        "request_id": f"step62-response-{session_id}-{position}",
    }
    response = _public(
        client.post(_endpoint(session_id, "responses"), json=payload)
    )
    return response


def _resolve_offers(client, session_id, index):
    """Resolve the current server-authorized offer, if any."""
    while True:
        progress = _public(client.get(_endpoint(session_id, "question")))
        if not progress["assistance_pending"]:
            return progress

        assert progress["question"] is None
        offer = _public(client.get(_endpoint(session_id, "assistance")))["offer"]
        assert offer is not None and offer["status"] == "offered"
        assert offer["body"] is None
        source = offer["source_position"]
        accept = (index + source) % 2 == 0
        decision = _public(
            client.post(
                _endpoint(session_id, "assistance/decision"),
                json={"source_position": source, "accept": accept},
            )
        )["offer"]
        assert decision["status"] == ("accepted" if accept else "declined")
        assert decision["body"] is None
        if accept:
            delivered = _public(
                client.post(
                    _endpoint(session_id, "assistance/delivery"),
                    json={"source_position": source},
                )
            )["offer"]
            assert delivered["status"] == "delivered"
            assert isinstance(delivered["body"], str) and delivered["body"]


def _choose(index, position):
    if position == 0:
        return "A" if index % 2 == 0 else "B"
    if position == 1:
        return "B" if index % 3 == 0 else "A"
    if position == 2:
        return "B" if index % 5 else "A"
    return "A" if index % 4 else "B"


def run_audit(database: Path, *, completed: int = 60,
              incomplete: int = 6) -> dict:
    """Run complete and deliberately interrupted synthetic sessions."""
    if (
        type(completed) is not int or type(incomplete) is not int
        or completed < 6 or incomplete < 6
        or completed % 6 or incomplete % 6
    ):
        raise ValueError("Counts must be positive multiples of six")
    database = Path(database)
    if database.exists():
        raise FileExistsError("Audit refuses to reuse an existing database")
    database.parent.mkdir(parents=True, exist_ok=True)

    app = create_experimental_app(database, block_sizes=(6,))
    app.config["TESTING"] = True
    client = app.test_client()
    quiz = app.extensions["trial_dev_quiz"]
    restarted = 0

    for index in range(completed + incomplete):
        sid = _enroll(client, index)
        assert _enroll(client, index, expected_status=200) == sid
        arm = quiz.read_policy(sid)  # Backend-only audit access.
        assert arm in ARMS
        limit = 4 if index < completed else 1

        for position in range(limit):
            progress = _resolve_offers(client, sid, index)
            assert progress["position"] == position
            assert progress["question"]["id"] == (
                INSTRUCTIONAL_DEMO_ITEMS[position].item_id
            )
            choice = _choose(index, position)
            first = _answer(client, sid, position, choice)
            assert first["accepted"] is True and first["replayed"] is False
            if position == 0:
                again = _answer(client, sid, position, choice)
                assert again["replayed"] is True

                if index % 10 == 0:
                    # Restart Flask and recover the same enrolled session.
                    app = create_experimental_app(database, block_sizes=(6,))
                    app.config["TESTING"] = True
                    client = app.test_client()
                    quiz = app.extensions["trial_dev_quiz"]
                    assert _enroll(client, index, expected_status=200) == sid
                    assert quiz.read_policy(sid) == arm
                    restarted += 1

        progress = _public(client.get(_endpoint(sid, "question")))
        assert progress["position"] == limit
        assert progress["complete"] == (limit == 4)
        decisions = quiz.read_policy_decisions(sid)
        assert len(decisions) == (2 if limit == 4 else 1)
        assert all(d.policy_mode == arm for d in decisions)
        if arm == "control":
            assert not any(d.offer_summary for d in decisions)
        if arm == "fixed_summary":
            assert all(d.offer_summary for d in decisions)

    with sqlite3.connect(database) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT a.policy_mode AS arm,
                   COUNT(*) AS assigned,
                   SUM(CASE WHEN s.position=4 THEN 1 ELSE 0 END)
                       AS completed,
                   SUM(CASE WHEN s.position<4 THEN 1 ELSE 0 END)
                       AS missing_probe
            FROM trial_allocations a
            JOIN experimental_session_policies ep
                ON ep.participant_id=a.participant_id
            JOIN sessions s ON s.session_id=ep.session_id
            GROUP BY a.policy_mode
        """).fetchall()
        by_arm = {
            row["arm"]: {
                "assigned": row["assigned"],
                "completed": row["completed"],
                "missing_probe": row["missing_probe"],
            } for row in rows
        }
        n_responses = con.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
        n_decisions = con.execute(
            "SELECT COUNT(*) FROM experimental_policy_decisions"
        ).fetchone()[0]
        n_offers = con.execute("SELECT COUNT(*) FROM assistance_offers").fetchone()[0]
        n_positive_decisions = con.execute(
            "SELECT COUNT(*) FROM experimental_policy_decisions WHERE offer_summary=1"
        ).fetchone()[0]
        events = dict(con.execute(
            "SELECT event_type, COUNT(*) FROM assistance_events GROUP BY event_type"
        ).fetchall())
        n_pending_offers = con.execute(
            "SELECT COUNT(*) FROM assistance_offers WHERE status='offered'"
        ).fetchone()[0]
        n_unmatched = con.execute("""
            SELECT COUNT(*)
            FROM assistance_offers o
            LEFT JOIN experimental_policy_decisions d
                ON d.session_id=o.session_id
                AND d.source_position=o.source_position
            WHERE d.session_id IS NULL OR d.offer_summary != 1
        """).fetchone()[0]

    assert set(by_arm) == set(ARMS)
    assert all(
        row == {
            "assigned": (completed + incomplete) // 3,
            "completed": completed // 3,
            "missing_probe": incomplete // 3,
        }
        for row in by_arm.values()
    )
    assert n_responses == completed * 4 + incomplete
    assert n_decisions == completed * 2 + incomplete
    assert n_offers == n_positive_decisions
    assert n_unmatched == 0
    assert events.get("proposed", 0) == n_offers
    assert events.get("offered", 0) == n_offers
    assert (
        events.get("accepted", 0) + events.get("declined", 0)
        == n_offers - n_pending_offers
    )
    assert events.get("delivered", 0) == events.get("accepted", 0)

    return {
        "audit": "step62_synthetic_development_only",
        "causal_evidence": False,
        "real_participants": 0,
        "assignment_unit": "synthetic enrollment ID",
        "completed_sessions": completed,
        "deliberately_incomplete_sessions": incomplete,
        "restart_recoveries_checked": restarted,
        "by_arm": by_arm,
        "responses": n_responses,
        "policy_decisions": n_decisions,
        "offers": n_offers,
        "unresolved_offers_from_incomplete_sessions": n_pending_offers,
        "assistance_events": events,
        "invariants": "passed",
        "caution": (
            "Scripted answers are not educational outcomes. "
            "No intervention effects or statistical treatment estimates "
            "may be inferred from this audit."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--completed", type=int, default=60)
    parser.add_argument("--incomplete", type=int, default=6)
    args = parser.parse_args()
    report = run_audit(
        args.database, completed=args.completed,
        incomplete=args.incomplete,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as file:
        json.dump(report, file, indent=2, sort_keys=True)
        file.write("\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
