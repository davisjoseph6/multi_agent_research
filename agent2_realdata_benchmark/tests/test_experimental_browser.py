"""Experimental browser and API smoke tests."""

import pytest

from src.prototype.experimental_api import (
    PREFIX,
    create_experimental_app,
)

from src.prototype.item_bank import (
    INSTRUCTIONAL_DEMO_ITEMS,
)


@pytest.fixture
def app(tmp_path):
    instance = create_experimental_app(
        tmp_path / "experimental_browser.sqlite3",
        block_sizes=(6,),
    )
    instance.config["TESTING"] = True
    return instance


@pytest.fixture
def client(app):
    return app.test_client()


def enroll(client, identifier):
    response = client.post(
        f"{PREFIX}/enroll",
        json={
            "enrollment_request_id": identifier,
        },
    )
    assert response.status_code in (200, 201)
    return response.get_json()["session_id"]


def endpoint(sid, suffix):
    return f"{PREFIX}/sessions/{sid}/{suffix}"


def answer(client, sid, pos, choice):
    return client.post(
        endpoint(sid, "responses"),
        json={
            "item_id": INSTRUCTIONAL_DEMO_ITEMS[
                pos
            ].item_id,
            "choice_id": choice,
            "request_id": f"test-{sid}-{pos}",
        },
    )


def sessions_by_policy(client, app):
    sessions = {}
    repository = app.extensions["trial_dev_quiz"]

    for i in range(6):
        sid = enroll(client, f"synthetic-browser-{i}")
        policy = repository.read_policy(sid)
        sessions.setdefault(policy, sid)

    assert set(sessions) == {
        "control",
        "fixed_summary",
        "adaptive_threshold",
    }

    return sessions


def test_experimental_browser_route(client):
    response = client.get("/trial-dev")

    assert response.status_code == 200
    assert b"experimental_quiz.js" in response.data
    assert b"EXPERIMENTAL DEVELOPMENT DEMO" in response.data
    assert b"fixed demonstration policy" not in response.data


def test_browser_security_headers(client):
    response = client.get("/trial-dev")

    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers[
        "X-Content-Type-Options"
    ] == "nosniff"

    csp = response.headers["Content-Security-Policy"]

    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp


def test_experimental_javascript_is_served(client):
    response = client.get(
        "/static/experimental_quiz.js"
    )

    assert response.status_code == 200

    source = response.get_data(as_text=True)

    assert '/api/v1/trial-dev' in source
    assert 'enrollment_request_id' in source
    assert '${API}/enroll' in source
    assert '/api/v1/durable' not in source


def test_enrollment_recovers_same_session(client):
    first = enroll(client, "browser-recovery")
    second = enroll(client, "browser-recovery")

    assert first == second


def test_control_browser_api_completes(client, app):
    sid = sessions_by_policy(
        client, app
    )["control"]

    for pos, choice in enumerate(
        ("B", "B", "B", "A")
    ):
        response = answer(
            client, sid, pos, choice
        )
        assert response.status_code == 200

    state = client.get(
        endpoint(sid, "question")
    ).get_json()

    assert state["complete"] is True
    assert state["question"] is None


def test_fixed_assistance_sequence(client, app):
    sid = sessions_by_policy(
        client, app
    )["fixed_summary"]

    assert answer(
        client, sid, 0, "A"
    ).status_code == 200

    state = client.get(
        endpoint(sid, "question")
    ).get_json()

    assert state["assistance_pending"] is True
    assert state["question"] is None

    accepted = client.post(
        endpoint(sid, "assistance/decision"),
        json={
            "source_position": 0,
            "accept": True,
        },
    )

    assert accepted.status_code == 200
    assert accepted.get_json()["offer"]["body"] is None

    delivered = client.post(
        endpoint(sid, "assistance/delivery"),
        json={"source_position": 0},
    )

    assert delivered.status_code == 200
    assert delivered.get_json()["offer"]["body"]


def test_adaptive_correct_answer_skips_offer(client, app):
    sid = sessions_by_policy(
        client, app
    )["adaptive_threshold"]

    assert answer(
        client, sid, 0, "B"
    ).status_code == 200

    state = client.get(
        endpoint(sid, "question")
    ).get_json()

    assert state["assistance_pending"] is False
    assert state["question"]["id"] == "demo_main_2"


def test_previous_fixed_browser_still_served(client):
    response = client.get(
        "/static/fixed_summary_quiz.js"
    )

    assert response.status_code == 200
    assert b"/api/v1/durable" in response.data
