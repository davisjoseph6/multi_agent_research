"""Read-only aggregate integrity audit for Step 62 synthetic databases.

No causal treatment estimates. No human-participant data.
"""

from __future__ import annotations

import argparse
import json
import sqlite3

from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path


ARMS = {
    "control",
    "fixed_summary",
    "adaptive_threshold",
}

EXPECTED_EVENTS = {
    "offered": ("proposed", "offered"),
    "accepted": ("proposed", "offered", "accepted"),
    "declined": ("proposed", "offered", "declined"),
    "delivered": (
        "proposed", "offered", "accepted", "delivered"
    ),
}


def audit(database: Path) -> dict:
    database = Path(database)

    if not database.is_file():
        raise FileNotFoundError(database)

    uri = database.resolve().as_uri() + "?mode=ro"

    # Read-only connection and consistent database snapshot.
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")

        allocations = db.execute(
            "SELECT participant_id, enrollment_request_id, "
            "policy_mode FROM trial_allocations"
        ).fetchall()

        bindings = db.execute(
            "SELECT participant_id, session_id, policy_mode "
            "FROM experimental_session_policies"
        ).fetchall()

        sessions = db.execute(
            "SELECT session_id, position FROM sessions"
        ).fetchall()

        responses = db.execute(
            "SELECT session_id, position, kind "
            "FROM responses ORDER BY position"
        ).fetchall()

        decisions = db.execute(
            "SELECT session_id, source_position, policy_mode, "
            "offer_summary FROM experimental_policy_decisions "
            "ORDER BY source_position"
        ).fetchall()

        offers = db.execute(
            "SELECT session_id, source_position, "
            "target_position, status FROM assistance_offers"
        ).fetchall()

        events = db.execute(
            "SELECT session_id, source_position, event_type "
            "FROM assistance_events ORDER BY event_id"
        ).fetchall()

        db.rollback()

    def check(condition, message):
        if not condition:
            raise AssertionError(message)

    check(bool(allocations), "No synthetic allocations")

    check(
        len(allocations) == len(bindings) == len(sessions),
        "Missing or duplicated session bindings",
    )

    assigned = {
        row["participant_id"]: row
        for row in allocations
    }

    links = {
        row["participant_id"]: row
        for row in bindings
    }

    position = {
        row["session_id"]: row["position"]
        for row in sessions
    }

    check(
        len(assigned) == len(allocations)
        and len(links) == len(bindings)
        and len(position) == len(sessions),
        "Duplicate identifiers",
    )

    counts = {
        arm: Counter()
        for arm in sorted(ARMS)
    }

    session_arms = {}

    for participant_id, assignment in assigned.items():

        check(
            assignment["enrollment_request_id"].startswith(
                "step62-synthetic-"
            ),
            "Database is not a Step 62 synthetic fixture",
        )

        arm = assignment["policy_mode"]

        check(
            arm in ARMS and participant_id in links,
            "Invalid or unbound allocation",
        )

        binding = links[participant_id]

        check(
            binding["policy_mode"] == arm
            and binding["session_id"] in position,
            "Session policy differs from allocation",
        )

        session_arms[binding["session_id"]] = arm
        counts[arm]["assigned"] += 1

    check(
        len(session_arms) == len(sessions),
        "Multiple allocations bound to one session",
    )

    response_history = defaultdict(list)
    decision_history = defaultdict(list)
    offer_records = {}
    event_history = defaultdict(list)

    for row in responses:
        response_history[row["session_id"]].append(row)

    for row in decisions:
        decision_history[row["session_id"]].append(row)

    for row in offers:
        key = (
            row["session_id"],
            row["source_position"],
        )

        check(key not in offer_records, "Duplicate offer")
        offer_records[key] = row

    for row in events:
        key = (
            row["session_id"],
            row["source_position"],
        )

        event_history[key].append(row["event_type"])

    check(
        set(response_history) <= set(session_arms)
        and set(decision_history) <= set(session_arms),
        "Unbound responses or decisions",
    )

    for session_id, arm in session_arms.items():

        progress = position[session_id]
        history = response_history[session_id]
        choices = decision_history[session_id]

        check(
            0 <= progress <= 4
            and [r["position"] for r in history]
            == list(range(progress)),
            "Invalid response sequence",
        )

        check(
            [d["source_position"] for d in choices]
            == list(range(min(progress, 2))),
            "Missing policy decision",
        )

        check(
            all(d["policy_mode"] == arm for d in choices),
            "Decision policy mismatch",
        )

        if arm == "control":
            check(
                not any(d["offer_summary"] for d in choices),
                "Control condition received assistance",
            )

        if arm == "fixed_summary":
            check(
                all(d["offer_summary"] for d in choices),
                "Fixed policy failed to offer assistance",
            )

        check(
            all(
                r["kind"] == "practice"
                for r in history[:3]
            ),
            "Unexpected practice item",
        )

        if progress == 4:
            check(
                history[3]["kind"] == "independent_probe",
                "Missing independent probe",
            )

            counts[arm]["completed"] += 1
            counts[arm]["probe_observed"] += 1

        else:
            counts[arm]["missing_probe"] += 1

        counts[arm]["responses"] += progress
        counts[arm]["decisions"] += len(choices)

        for decision in choices:
            key = (
                session_id,
                decision["source_position"],
            )

            check(
                bool(decision["offer_summary"])
                == (key in offer_records),
                "Offer differs from recorded policy decision",
            )

    positive_decisions = {
        (
            decision["session_id"],
            decision["source_position"],
        )
        for decision in decisions
        if decision["offer_summary"] == 1
    }

    check(
        set(offer_records) == positive_decisions,
        "Offer/decision correspondence failed",
    )

    check(
        len(event_history) == len(offer_records),
        "Missing or orphaned assistance events",
    )

    for key, offer in offer_records.items():

        status = offer["status"]

        check(
            key in event_history
            and status in EXPECTED_EVENTS,
            "Unknown offer or missing events",
        )

        check(
            tuple(event_history[key])
            == EXPECTED_EVENTS[status],
            "Assistance event ordering inconsistent",
        )

        check(
            offer["target_position"]
            == offer["source_position"] + 1,
            "Invalid assistance target",
        )

        if status in ("offered", "accepted"):
            check(
                position[key[0]] == offer["target_position"],
                "Unresolved offer was bypassed",
            )

        arm = session_arms[key[0]]

        counts[arm]["offers"] += 1
        counts[arm]["status_" + status] += 1

    return {
        "audit": "step63_synthetic_readonly_v1",
        "invariants": "passed",
        "real_participants": 0,
        "causal_evidence": False,
        "privacy": (
            "aggregate_only_no_raw_identifiers_or_answers"
        ),
        "totals": {
            "assigned": len(allocations),
            "responses": len(responses),
            "policy_decisions": len(decisions),
            "offers": len(offers),
            "assistance_events": len(events),
        },
        "by_arm": {
            arm: dict(sorted(counter.items()))
            for arm, counter in counts.items()
        },
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--database",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--report",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    result = audit(args.database)

    args.report.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Refuse accidental overwriting of an earlier report.
    with args.report.open("x", encoding="utf-8") as file:
        json.dump(
            result,
            file,
            indent=2,
            sort_keys=True,
        )
        file.write("\n")

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
