"""Local demo API contract tests; no research participants."""

import pytest

from src.prototype.api import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def start(client):
    response = client.post("/api/v1/demo/sessions")
    assert response.status_code == 201
    return response.get_json()["session_id"]


def question(client, session_id):
    return client.get(
        f"/api/v1/demo/sessions/{session_id}/question"
    )


def submit(client, session_id, item_id, choice):
    return client.post(
        f"/api/v1/demo/sessions/{session_id}/responses",
        json={
            "item_id": item_id,
            "choice_id": choice,
        },
    )


def test_health(client):
    result = client.get("/api/v1/demo/health")

    assert result.status_code == 200
    assert result.get_json()["mode"] == "local_demo_only"


def test_question_does_not_disclose_answer(client):
    session_id = start(client)
    data = question(client, session_id).get_json()

    assert data["complete"] is False
    assert data["question"]["id"] == "demo_main_1"
    assert "correct_id" not in data["question"]
    assert "correct" not in data["question"]


def test_full_practice_to_probe_flow(client):
    session_id = start(client)

    first = question(client, session_id).get_json()
    assert first["question"]["kind"] == "practice"

    accepted = submit(
        client, session_id, "demo_main_1", "B"
    )

    assert accepted.status_code == 200
    assert accepted.get_json()["feedback"] == "withheld"
    assert accepted.get_json()["complete"] is False

    second = question(client, session_id).get_json()

    assert second["question"]["id"] == "demo_probe_1"
    assert second["question"]["kind"] == "independent_probe"
    assert "correct_id" not in second["question"]

    result = submit(
        client, session_id, "demo_probe_1", "A"
    )

    assert result.status_code == 200
    assert result.get_json()["complete"] is True

    final = question(client, session_id).get_json()
    assert final == {
        "complete": True,
        "question": None,
    }


def test_out_of_order_answer_is_rejected(client):
    session_id = start(client)

    result = submit(
        client, session_id, "demo_probe_1", "A"
    )

    assert result.status_code == 409
    assert question(
        client, session_id
    ).get_json()["question"]["id"] == "demo_main_1"


def test_invalid_choice_does_not_advance(client):
    session_id = start(client)

    result = submit(
        client, session_id, "demo_main_1", "Z"
    )

    assert result.status_code == 400
    assert question(
        client, session_id
    ).get_json()["question"]["id"] == "demo_main_1"


def test_duplicate_answer_is_rejected(client):
    session_id = start(client)

    submit(client, session_id, "demo_main_1", "B")

    duplicate = submit(
        client, session_id, "demo_main_1", "B"
    )

    assert duplicate.status_code == 409


def test_sessions_are_isolated(client):
    first = start(client)
    second = start(client)

    assert first != second

    submit(client, first, "demo_main_1", "B")

    assert question(
        client, second
    ).get_json()["question"]["id"] == "demo_main_1"


def test_unknown_session_is_rejected(client):
    result = question(client, "unknown_session")
    assert result.status_code == 404


def test_completed_session_rejects_more_answers(client):
    session_id = start(client)

    submit(client, session_id, "demo_main_1", "B")
    submit(client, session_id, "demo_probe_1", "A")

    result = submit(
        client, session_id, "demo_probe_1", "A"
    )

    assert result.status_code == 409
