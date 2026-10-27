"""Integration tests for the local durable Flask quiz."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from src.prototype import durable_api
from src.prototype.item_bank import BANK_VERSION, DEMO_ITEMS
from src.prototype.sqlite_store import SQLiteQuizRepository


@pytest.fixture
def database(tmp_path):
    return tmp_path / "durable_demo.sqlite3"


@pytest.fixture
def app(database):
    instance = durable_api.create_durable_app(database)
    instance.config["TESTING"] = True
    return instance


@pytest.fixture
def client(app):
    return app.test_client()


def start(client):
    response = client.post("/api/v1/durable/sessions")
    assert response.status_code == 201
    return response.get_json()["session_id"]


def question(client, sid):
    return client.get(
        f"/api/v1/durable/sessions/{sid}/question"
    )


def submit(
    client,
    sid,
    *,
    item="demo_main_1",
    choice="B",
    request_id="submission-1",
):
    return client.post(
        f"/api/v1/durable/sessions/{sid}/responses",
        json={
            "item_id": item,
            "choice_id": choice,
            "request_id": request_id,
        },
    )


def test_health(client):
    response = client.get("/api/v1/durable/health")

    assert response.status_code == 200
    assert response.get_json()["mode"] == "local_demo_only"


def test_create_session_and_hide_answer_key(client):
    sid = start(client)
    response = question(client, sid)

    assert response.status_code == 200

    data = response.get_json()

    assert data["position"] == 0
    assert data["bank_version"] == BANK_VERSION
    assert data["complete"] is False
    assert data["question"]["id"] == "demo_main_1"
    assert "correct_id" not in data["question"]


def test_full_durable_two_question_flow(client):
    sid = start(client)

    first = submit(client, sid)

    assert first.status_code == 200
    assert first.get_json()["accepted"] is True
    assert first.get_json()["replayed"] is False
    assert first.get_json()["next_action"] == "no_offer"

    next_question = question(client, sid).get_json()

    assert next_question["position"] == 1
    assert next_question["question"]["id"] == "demo_probe_1"

    second = submit(
        client,
        sid,
        item="demo_probe_1",
        choice="A",
        request_id="submission-2",
    )

    assert second.status_code == 200
    assert second.get_json()["complete"] is True

    final = question(client, sid).get_json()

    assert final["complete"] is True
    assert final["question"] is None


def test_old_retry_is_stable_after_completion(client):
    sid = start(client)

    submit(client, sid)
    submit(
        client,
        sid,
        item="demo_probe_1",
        choice="A",
        request_id="submission-2",
    )

    retry = submit(client, sid)

    assert retry.status_code == 200

    data = retry.get_json()

    assert data["replayed"] is True
    assert data["complete"] is False

    assert question(client, sid).get_json()["complete"] is True


def test_conflicting_retry_is_rejected(client):
    sid = start(client)

    submit(client, sid)

    conflicting = submit(
        client,
        sid,
        choice="A",
    )

    assert conflicting.status_code == 409
    assert question(client, sid).get_json()["position"] == 1


def test_invalid_submission_does_not_advance(client):
    sid = start(client)

    invalid = submit(client, sid, choice="Z")

    assert invalid.status_code == 400
    assert question(client, sid).get_json()["position"] == 0


def test_missing_request_id_is_rejected(client):
    sid = start(client)

    response = client.post(
        f"/api/v1/durable/sessions/{sid}/responses",
        json={
            "item_id": "demo_main_1",
            "choice_id": "B",
        },
    )

    assert response.status_code == 400
    assert question(client, sid).get_json()["position"] == 0


def test_unknown_session_returns_404(client):
    assert question(
        client, "unknown"
    ).status_code == 404

    assert submit(
        client, "unknown"
    ).status_code == 404


def test_restart_recovers_persisted_progress(database):
    first_app = durable_api.create_durable_app(database)
    first_client = first_app.test_client()

    sid = start(first_client)
    submit(first_client, sid)

    reopened_app = durable_api.create_durable_app(database)
    reopened_client = reopened_app.test_client()

    state = question(reopened_client, sid).get_json()

    assert state["position"] == 1
    assert state["question"]["id"] == "demo_probe_1"

    retry = submit(reopened_client, sid)

    assert retry.status_code == 200
    assert retry.get_json()["replayed"] is True


def test_two_item_bank_has_no_phantom_shadow_target(app, client):
    sid = start(client)

    response = submit(client, sid)

    assert response.status_code == 200

    # The next item is an independent probe, not practice.
    assert app.extensions[
        "durable_quiz_shadow_events"
    ] == []


def test_real_next_practice_triggers_shadow_once(
    tmp_path,
    monkeypatch,
):
    next_practice = replace(
        DEMO_ITEMS[0],
        item_id="synthetic_main_2",
        prompt="A second synthetic practice fixture",
    )

    items = (
        DEMO_ITEMS[0],
        next_practice,
        DEMO_ITEMS[1],
    )

    observed = []

    def fake_planner(tracker, **kwargs):
        observed.append({
            "mastery": tracker.mastery,
            **kwargs,
        })
        return {"mode": "test_only_shadow"}

    monkeypatch.setattr(
        durable_api,
        "propose_shadow_recovery",
        fake_planner,
    )

    database = tmp_path / "three_items.sqlite3"

    app = durable_api.create_durable_app(
        database,
        items=items,
        bank_version="synthetic_three_item_v1",
    )

    client = app.test_client()
    sid = start(client)

    first = submit(client, sid)

    assert first.status_code == 200
    assert len(observed) == 1

    assert observed[0]["mastery"] == pytest.approx(
        0.5263157894736842
    )

    assert observed[0]["source_row"] == 0

    events = app.extensions[
        "durable_quiz_shadow_events"
    ]

    assert len(events) == 1
    assert events[0]["next_item_id"] == "synthetic_main_2"
    assert events[0]["status"] == "ok"

    # Replaying the same committed response never replans.
    retry = submit(client, sid)

    assert retry.get_json()["replayed"] is True
    assert len(observed) == 1

    # The second practice is followed by a probe.
    # It must not generate another shadow proposal.
    second = submit(
        client,
        sid,
        item="synthetic_main_2",
        choice="A",
        request_id="submission-2",
    )

    assert second.status_code == 200
    assert len(observed) == 1

    probe = submit(
        client,
        sid,
        item="demo_probe_1",
        choice="A",
        request_id="submission-3",
    )

    assert probe.status_code == 200
    assert len(observed) == 1


def test_shadow_failure_does_not_lose_committed_answer(
    tmp_path,
    monkeypatch,
):
    next_practice = replace(
        DEMO_ITEMS[0],
        item_id="synthetic_main_2",
        prompt="Second synthetic practice question",
    )

    items = (
        DEMO_ITEMS[0],
        next_practice,
        DEMO_ITEMS[1],
    )

    attempts = []

    def failing_planner(*args, **kwargs):
        attempts.append(True)
        raise RuntimeError("Injected shadow failure")

    monkeypatch.setattr(
        durable_api,
        "propose_shadow_recovery",
        failing_planner,
    )

    database = tmp_path / "planner_failure.sqlite3"

    app = durable_api.create_durable_app(
        database,
        items=items,
        bank_version="shadow_failure_fixture_v1",
    )

    client = app.test_client()
    sid = start(client)

    first = submit(client, sid)

    assert first.status_code == 200
    assert first.get_json()["accepted"] is True

    state = question(client, sid).get_json()

    assert state["position"] == 1

    retry = submit(client, sid)

    assert retry.get_json()["replayed"] is True
    assert len(attempts) == 1

    events = app.extensions[
        "durable_quiz_shadow_events"
    ]

    assert len(events) == 1
    assert events[0]["status"] == "failed"

    reopened = SQLiteQuizRepository(
        database,
        items=items,
        bank_version="shadow_failure_fixture_v1",
    )

    assert len(reopened.read_responses(sid)) == 1


def test_concurrent_http_requests_do_not_double_advance(
    app,
):
    client = app.test_client()
    sid = start(client)

    def attempt(request_id):
        with app.test_client() as thread_client:
            return submit(
                thread_client,
                sid,
                request_id=request_id,
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(
            attempt,
            ("different-request-1", "different-request-2"),
        ))

    assert sorted(codes) == [200, 409]

    progress = question(client, sid).get_json()

    assert progress["position"] == 1


def test_other_concept_does_not_contaminate_shadow_bkt(
    tmp_path,
    monkeypatch,
):
    """Shadow belief uses only the target concept's history."""

    from src.prototype.belief import DemoBeliefTracker

    other = replace(
        DEMO_ITEMS[0],
        item_id="synthetic_other_1",
        concept_id="anchoring",
        prompt="Synthetic other-concept practice fixture",
    )

    target_second = replace(
        DEMO_ITEMS[0],
        item_id="synthetic_target_2",
        prompt="Synthetic second target-concept practice",
    )

    target_third = replace(
        DEMO_ITEMS[0],
        item_id="synthetic_target_3",
        prompt="Synthetic third target-concept practice",
    )

    items = (
        DEMO_ITEMS[0],
        other,
        target_second,
        target_third,
        DEMO_ITEMS[1],
    )

    captured = []

    def fake_planner(tracker, **kwargs):
        captured.append({
            "mastery": tracker.mastery,
            "source_row": kwargs["source_row"],
        })
        return {"mode": "test_only_shadow"}

    monkeypatch.setattr(
        durable_api,
        "propose_shadow_recovery",
        fake_planner,
    )

    app = durable_api.create_durable_app(
        tmp_path / "cross_concept.sqlite3",
        items=items,
        bank_version="synthetic_cross_concept_v1",
    )

    client = app.test_client()
    sid = start(client)

    # Correct answer for the target concept.
    assert submit(
        client,
        sid,
        item="demo_main_1",
        choice="B",
        request_id="cross-1",
    ).status_code == 200

    # Incorrect answer for an unrelated concept.
    assert submit(
        client,
        sid,
        item="synthetic_other_1",
        choice="A",
        request_id="cross-2",
    ).status_code == 200

    # Correct answer for the target concept.
    # Another target-concept practice item follows.
    assert submit(
        client,
        sid,
        item="synthetic_target_2",
        choice="B",
        request_id="cross-3",
    ).status_code == 200

    assert len(captured) == 1
    assert captured[0]["source_row"] == 2

    expected = DemoBeliefTracker()
    expected.observe_practice(correct=True)
    expected.observe_practice(correct=True)

    assert captured[0]["mastery"] == pytest.approx(
        expected.mastery
    )

    # The incorrect other-concept response must not
    # enter the target concept's BKT update history.
    contaminated = DemoBeliefTracker()
    contaminated.observe_practice(correct=True)
    contaminated.observe_practice(correct=False)
    contaminated.observe_practice(correct=True)

    assert captured[0]["mastery"] != pytest.approx(
        contaminated.mastery
    )


def test_real_pomcp_shadow_planner_executes(
    tmp_path,
):
    """Verify the real planner, not just a mocked function."""

    next_practice = replace(
        DEMO_ITEMS[0],
        item_id="synthetic_next_practice",
        prompt="Synthetic next practice opportunity",
    )

    items = (
        DEMO_ITEMS[0],
        next_practice,
        DEMO_ITEMS[1],
    )

    app = durable_api.create_durable_app(
        tmp_path / "real_shadow.sqlite3",
        items=items,
        bank_version="synthetic_real_shadow_v1",
    )

    client = app.test_client()
    sid = start(client)

    response = submit(
        client,
        sid,
        item="demo_main_1",
        choice="A",
        request_id="real-shadow-1",
    )

    assert response.status_code == 200

    public = response.get_json()

    assert public["accepted"] is True
    assert public["next_action"] == "no_offer"
    assert "simulated_action" not in public

    events = app.extensions[
        "durable_quiz_shadow_events"
    ]

    assert len(events) == 1
    assert events[0]["status"] == "ok"
    assert events[0]["next_item_id"] == (
        "synthetic_next_practice"
    )

    diagnostic = events[0]["diagnostic"]

    assert diagnostic.mode == "hypothetical_shadow_only"
    assert diagnostic.source_row == 0
    assert diagnostic.simulated_action in (
        diagnostic.allowed_actions
    )

    assert diagnostic.mastery_belief == pytest.approx(
        0.12903225806451613
    )
