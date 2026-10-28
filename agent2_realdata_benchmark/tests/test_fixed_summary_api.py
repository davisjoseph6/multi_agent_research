"""HTTP integration tests for the fixed-summary assistance demo."""

import pytest

from src.prototype.durable_api import create_durable_app
from src.prototype.item_bank import (
    INSTRUCTIONAL_DEMO_ITEMS,
    INSTRUCTIONAL_DEMO_VERSION,
)
from src.prototype.sqlite_store import RepositoryModeMismatch


def fixed_app(database):
    app = create_durable_app(
        database,
        items=INSTRUCTIONAL_DEMO_ITEMS,
        bank_version=INSTRUCTIONAL_DEMO_VERSION,
        fixed_summary=True,
    )
    app.config["TESTING"] = True
    return app


def start(client):
    response = client.post("/api/v1/durable/sessions")
    assert response.status_code == 201
    return response.get_json()["session_id"]


def url(sid, suffix):
    return f"/api/v1/durable/sessions/{sid}/{suffix}"


def answer(client, sid, position, request_id=None):
    return client.post(
        url(sid, "responses"),
        json={
            "item_id": INSTRUCTIONAL_DEMO_ITEMS[position].item_id,
            "choice_id": "A",
            "request_id": request_id or f"answer-{position}",
        },
    )


def assistance(client, sid):
    return client.get(url(sid, "assistance"))


def decide(client, sid, position, accept):
    return client.post(
        url(sid, "assistance/decision"),
        json={"source_position": position, "accept": accept},
    )


def deliver(client, sid, position):
    return client.post(
        url(sid, "assistance/delivery"),
        json={"source_position": position},
    )


def progress(client, sid):
    return client.get(url(sid, "question"))


def test_unassisted_mode_keeps_existing_behavior(tmp_path):
    app = create_durable_app(tmp_path / "plain.sqlite3")
    client = app.test_client()
    sid = start(client)
    assert client.get("/demo").status_code == 200
    assert assistance(client, sid).status_code == 404
    assert decide(client, sid, 0, True).status_code == 404
    assert deliver(client, sid, 0).status_code == 404
    assert answer(client, sid, 0).status_code == 200
    assert progress(client, sid).get_json()["question"]["id"] == "demo_probe_1"


def test_offer_is_automatic_and_hides_next_question(tmp_path):
    app = fixed_app(tmp_path / "automatic.sqlite3")
    client = app.test_client()
    sid = start(client)
    first = answer(client, sid, 0)
    assert first.status_code == 200
    assert first.get_json()["next_action"] == "assistance_pending"
    state = progress(client, sid).get_json()
    assert state["position"] == 1
    assert state["question"] is None
    assert state["assistance_pending"] is True
    offer = assistance(client, sid).get_json()["offer"]
    assert offer["status"] == "offered"
    assert offer["body"] is None
    assert "correct_id" not in str(offer)


def test_pending_offer_blocks_direct_post(tmp_path):
    app = fixed_app(tmp_path / "blocked.sqlite3")
    client = app.test_client()
    sid = start(client)
    answer(client, sid, 0)
    response = answer(client, sid, 1)
    assert response.status_code == 409
    assert response.get_json()["error"] == "assistance_pending"
    repository = app.extensions["durable_quiz_repository"]
    assert len(repository.read_responses(sid)) == 1


def test_accept_then_deliver_in_distinct_http_steps(tmp_path):
    app = fixed_app(tmp_path / "accepted.sqlite3")
    client = app.test_client()
    sid = start(client)
    answer(client, sid, 0)
    assert deliver(client, sid, 0).status_code == 409
    accepted = decide(client, sid, 0, True).get_json()["offer"]
    assert accepted["status"] == "accepted"
    assert accepted["body"] is None
    assert progress(client, sid).get_json()["question"] is None
    assert answer(client, sid, 1).status_code == 409
    delivered = deliver(client, sid, 0).get_json()["offer"]
    assert delivered["status"] == "delivered"
    assert delivered["body"]
    assert progress(client, sid).get_json()["question"]["id"] == "demo_main_2"
    assert app.extensions["durable_quiz_repository"].read_events(
        session_id=sid, source_position=0
    ) == ("proposed", "offered", "accepted", "delivered")


def test_decline_unlocks_and_probe_remains_independent(tmp_path):
    client = fixed_app(tmp_path / "declined.sqlite3").test_client()
    sid = start(client)
    answer(client, sid, 0)
    refusal = decide(client, sid, 0, False).get_json()["offer"]
    assert refusal["status"] == "declined"
    assert refusal["body"] is None
    assert deliver(client, sid, 0).status_code == 409
    assert answer(client, sid, 1).status_code == 200
    assert assistance(client, sid).get_json()["offer"]["status"] == "offered"
    assert decide(client, sid, 1, False).status_code == 200
    assert answer(client, sid, 2).status_code == 200
    assert assistance(client, sid).get_json()["offer"] is None
    assert answer(client, sid, 3).get_json()["complete"] is True


def test_idempotent_retries_do_not_duplicate_events(tmp_path):
    app = fixed_app(tmp_path / "retry.sqlite3")
    client = app.test_client()
    sid = start(client)
    assert answer(client, sid, 0).status_code == 200
    assert answer(client, sid, 0).get_json()["replayed"] is True
    assert decide(client, sid, 0, True).status_code == 200
    assert decide(client, sid, 0, True).status_code == 200
    assert deliver(client, sid, 0).status_code == 200
    assert deliver(client, sid, 0).status_code == 200
    assert app.extensions["durable_quiz_repository"].read_events(
        session_id=sid, source_position=0
    ) == ("proposed", "offered", "accepted", "delivered")


def test_restart_recovers_accepted_pending_offer(tmp_path):
    path = tmp_path / "restart.sqlite3"
    first = fixed_app(path).test_client()
    sid = start(first)
    answer(first, sid, 0)
    second = fixed_app(path).test_client()
    assert progress(second, sid).get_json()["assistance_pending"] is True
    assert decide(second, sid, 0, True).status_code == 200
    third = fixed_app(path).test_client()
    assert assistance(third, sid).get_json()["offer"]["status"] == "accepted"
    assert deliver(third, sid, 0).status_code == 200
    assert progress(third, sid).get_json()["question"]["id"] == "demo_main_2"


def test_malformed_assistance_payloads_are_rejected(tmp_path):
    client = fixed_app(tmp_path / "malformed.sqlite3").test_client()
    sid = start(client)
    answer(client, sid, 0)
    for payload in (
        {"source_position": 0, "accept": "yes"},
        {"source_position": True, "accept": True},
        {"source_position": -1, "accept": True},
        {"accept": True},
    ):
        assert client.post(url(sid, "assistance/decision"), json=payload).status_code == 400
    assert client.post(url(sid, "assistance/delivery"), json={}).status_code == 400
    assert assistance(client, sid).get_json()["offer"]["status"] == "offered"


def test_unknown_sessions_return_404(tmp_path):
    client = fixed_app(tmp_path / "missing.sqlite3").test_client()
    assert assistance(client, "unknown").status_code == 404
    assert decide(client, "unknown", 0, True).status_code == 404
    assert deliver(client, "unknown", 0).status_code == 404


def test_repository_mode_cannot_be_bypassed(tmp_path):
    path = tmp_path / "mode.sqlite3"
    fixed_app(path)
    with pytest.raises(RepositoryModeMismatch):
        create_durable_app(
            path,
            items=INSTRUCTIONAL_DEMO_ITEMS,
            bank_version=INSTRUCTIONAL_DEMO_VERSION,
        )


def test_browser_disabled_until_step22(tmp_path):
    client = fixed_app(tmp_path / "browser.sqlite3").test_client()
    response = client.get("/demo")
    assert response.status_code == 409
    assert response.get_json()["error"] == "fixed_summary_browser_not_yet_supported"
