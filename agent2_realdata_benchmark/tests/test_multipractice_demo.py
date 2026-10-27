"""Local-only multi-practice instructional demonstration tests."""

import pytest

from src.prototype.durable_api import create_durable_app
from src.prototype.item_bank import (
    BANK_VERSION,
    DEMO_ITEMS,
    INSTRUCTIONAL_DEMO_VERSION,
    INSTRUCTIONAL_DEMO_ITEMS,
    validate_item_bank,
)
from src.prototype.session_engine import FixedQuizSession
from src.prototype.sqlite_store import SQLiteQuizRepository


def make_app(database):
    app = create_durable_app(
        database,
        items=INSTRUCTIONAL_DEMO_ITEMS,
        bank_version=INSTRUCTIONAL_DEMO_VERSION,
    )
    app.config["TESTING"] = True
    return app


def create_session(client):
    response = client.post("/api/v1/durable/sessions")
    assert response.status_code == 201
    return response.get_json()["session_id"]


def get_question(client, session_id):
    return client.get(
        f"/api/v1/durable/sessions/{session_id}/question"
    )


def submit(client, session_id, item_id, choice_id, number):
    return client.post(
        f"/api/v1/durable/sessions/{session_id}/responses",
        json={
            "item_id": item_id,
            "choice_id": choice_id,
            "request_id": f"fixture-request-{number}",
        },
    )


def test_multipractice_bank_structure():
    validate_item_bank(INSTRUCTIONAL_DEMO_ITEMS)

    assert INSTRUCTIONAL_DEMO_VERSION != BANK_VERSION

    assert [
        item.item_id for item in INSTRUCTIONAL_DEMO_ITEMS
    ] == [
        "demo_main_1",
        "demo_main_2",
        "demo_main_3",
        "demo_probe_1",
    ]

    assert [
        item.kind for item in INSTRUCTIONAL_DEMO_ITEMS
    ] == [
        "practice",
        "practice",
        "practice",
        "independent_probe",
    ]


def test_multipractice_session_engine():
    session = FixedQuizSession(
        items=INSTRUCTIONAL_DEMO_ITEMS,
        bank_version=INSTRUCTIONAL_DEMO_VERSION,
    )

    for item_id, choice_id in (
        ("demo_main_1", "A"),
        ("demo_main_2", "B"),
        ("demo_main_3", "B"),
        ("demo_probe_1", "A"),
    ):
        question = session.current_public_question()

        assert question["id"] == item_id
        assert "correct_id" not in question

        session.submit(
            item_id=item_id,
            choice_id=choice_id,
        )

    assert session.completed
    assert len(session.responses) == 4


def test_multipractice_public_items_hide_answers():
    for item in INSTRUCTIONAL_DEMO_ITEMS:
        public = item.public_dict()

        assert "correct_id" not in public
        assert "correct" not in public
        assert "answer_key" not in public


def test_four_question_http_flow_runs_real_shadow_planner(
    tmp_path,
):
    app = make_app(tmp_path / "four_questions.sqlite3")
    client = app.test_client()
    sid = create_session(client)

    answers = (
        ("demo_main_1", "A"),
        ("demo_main_2", "B"),
        ("demo_main_3", "B"),
        ("demo_probe_1", "A"),
    )

    for number, (item_id, choice_id) in enumerate(
        answers, start=1
    ):
        current = get_question(client, sid).get_json()

        assert current["position"] == number - 1
        assert current["question"]["id"] == item_id

        response = submit(
            client,
            sid,
            item_id,
            choice_id,
            number,
        )

        assert response.status_code == 200

        public = response.get_json()

        assert public["accepted"] is True
        assert public["replayed"] is False
        assert public["next_action"] == "no_offer"
        assert "simulated_action" not in public
        assert "mastery_belief" not in public

    complete = get_question(client, sid).get_json()

    assert complete["complete"] is True
    assert complete["question"] is None
    assert complete["position"] == 4

    events = app.extensions[
        "durable_quiz_shadow_events"
    ]

    # Planning occurs after practice 1 and practice 2,
    # because a same-concept practice item follows.
    #
    # Practice 3 is followed by a probe, so no planning.
    assert len(events) == 2

    assert [
        event["source_position"] for event in events
    ] == [0, 1]

    assert [
        event["next_item_id"] for event in events
    ] == [
        "demo_main_2",
        "demo_main_3",
    ]

    assert all(
        event["status"] == "ok" for event in events
    )

    assert all(
        event["diagnostic"].mode
        == "hypothetical_shadow_only"
        for event in events
    )


def test_restart_recovers_four_question_progress(tmp_path):
    database = tmp_path / "restart.sqlite3"

    first_app = make_app(database)
    first = first_app.test_client()
    sid = create_session(first)

    assert submit(
        first, sid, "demo_main_1", "A", 1
    ).status_code == 200

    assert submit(
        first, sid, "demo_main_2", "B", 2
    ).status_code == 200

    reopened_app = make_app(database)
    reopened = reopened_app.test_client()

    progress = get_question(reopened, sid).get_json()

    assert progress["position"] == 2
    assert progress["question"]["id"] == "demo_main_3"

    repository = SQLiteQuizRepository(
        database,
        items=INSTRUCTIONAL_DEMO_ITEMS,
        bank_version=INSTRUCTIONAL_DEMO_VERSION,
    )

    assert len(repository.read_responses(sid)) == 2

    replay = submit(
        reopened, sid, "demo_main_1", "A", 1
    )

    assert replay.status_code == 200
    assert replay.get_json()["replayed"] is True
    assert len(repository.read_responses(sid)) == 2


def test_default_two_question_demo_remains_unchanged(tmp_path):
    app = create_durable_app(
        tmp_path / "original_demo.sqlite3"
    )

    client = app.test_client()
    sid = create_session(client)

    current = get_question(client, sid).get_json()

    assert current["bank_version"] == BANK_VERSION
    assert current["question"]["id"] == DEMO_ITEMS[0].item_id

    assert submit(
        client, sid, "demo_main_1", "B", 1
    ).status_code == 200

    next_item = get_question(client, sid).get_json()

    assert next_item["question"]["id"] == "demo_probe_1"


def test_bank_versions_cannot_silently_mix(tmp_path):
    database = tmp_path / "version_isolation.sqlite3"

    original = create_durable_app(database)
    sid = create_session(original.test_client())

    different_bank = make_app(database)

    response = get_question(
        different_bank.test_client(), sid
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == (
        "item_bank_mismatch"
    )
