"""HTTP tests for development-only experimental quiz API."""

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
        tmp_path / "trial_api.sqlite3",
        block_sizes=(6,),
    )
    instance.config["TESTING"] = True
    return instance


@pytest.fixture
def client(app):
    return app.test_client()


def enroll(client, name):
    response = client.post(
        f"{PREFIX}/enroll",
        json={"enrollment_request_id": name},
    )
    assert response.status_code in (200, 201)
    return response.get_json()["session_id"]


def endpoint(sid, suffix):
    return f"{PREFIX}/sessions/{sid}/{suffix}"


def answer(client, sid, pos, choice="A"):
    return client.post(
        endpoint(sid, "responses"),
        json={
            "item_id": INSTRUCTIONAL_DEMO_ITEMS[pos].item_id,
            "choice_id": choice,
            "request_id": f"answer-{sid}-{pos}",
        },
    )


def sessions_by_arm(app, client):
    result = {}
    quiz = app.extensions["trial_dev_quiz"]

    for i in range(6):
        sid = enroll(client, f"synthetic-participant-{i}")
        arm = quiz.read_policy(sid)
        result.setdefault(arm, sid)

    assert set(result) == {
        "control",
        "fixed_summary",
        "adaptive_threshold",
    }

    return result


def test_health_and_no_public_arm_selection(client):
    response = client.get(f"{PREFIX}/health")

    assert response.status_code == 200
    assert response.get_json()["mode"] == (
        "trial_development_only"
    )

    assert client.post(
        f"{PREFIX}/sessions"
    ).status_code == 404


def test_enrollment_is_idempotent_and_private(client):
    first = client.post(
        f"{PREFIX}/enroll",
        json={"enrollment_request_id": "person-one"},
    )

    second = client.post(
        f"{PREFIX}/enroll",
        json={"enrollment_request_id": "person-one"},
    )

    assert first.status_code == 201
    assert second.status_code == 200

    assert (
        first.get_json()["session_id"]
        == second.get_json()["session_id"]
    )

    for response in (first, second):
        payload = response.get_json()
        assert "policy_mode" not in payload
        assert "participant_id" not in payload
        assert "mastery_belief" not in payload


def test_rejects_client_policy_override(client):
    response = client.post(
        f"{PREFIX}/enroll",
        json={
            "enrollment_request_id": "forged",
            "policy_mode": "fixed_summary",
        },
    )

    assert response.status_code == 400


def test_policies_control_offers(app, client):
    sessions = sessions_by_arm(app, client)

    for arm, sid in sessions.items():
        response = answer(client, sid, 0, "A")

        assert response.status_code == 200

        expected_offer = arm != "control"

        assert (
            response.get_json()["next_action"]
            == (
                "assistance_pending"
                if expected_offer else "no_offer"
            )
        )

        progress = client.get(
            endpoint(sid, "question")
        ).get_json()

        assert progress["assistance_pending"] == expected_offer

        assert (
            progress["question"] is None
        ) == expected_offer


def test_adaptive_abstains_after_correct(app, client):
    sid = sessions_by_arm(
        app, client
    )["adaptive_threshold"]

    assert answer(
        client, sid, 0, "B"
    ).status_code == 200

    progress = client.get(
        endpoint(sid, "question")
    ).get_json()

    assert progress["assistance_pending"] is False
    assert progress["question"]["id"] == "demo_main_2"


def test_pending_offer_cannot_be_skipped(app, client):
    sid = sessions_by_arm(
        app, client
    )["fixed_summary"]

    assert answer(
        client, sid, 0
    ).status_code == 200

    assert answer(
        client, sid, 1
    ).status_code == 409

    refusal = client.post(
        endpoint(sid, "assistance/decision"),
        json={
            "source_position": 0,
            "accept": False,
        },
    )

    assert refusal.status_code == 200

    assert answer(
        client, sid, 1
    ).status_code == 200


def test_accept_and_deliver_are_separate(app, client):
    sid = sessions_by_arm(
        app, client
    )["fixed_summary"]

    answer(client, sid, 0)

    accepted = client.post(
        endpoint(sid, "assistance/decision"),
        json={
            "source_position": 0,
            "accept": True,
        },
    )

    assert accepted.status_code == 200
    assert accepted.get_json()["offer"]["body"] is None

    assert answer(
        client, sid, 1
    ).status_code == 409

    delivered = client.post(
        endpoint(sid, "assistance/delivery"),
        json={"source_position": 0},
    )

    assert delivered.status_code == 200
    assert delivered.get_json()["offer"]["body"]


def test_control_completes_without_assistance(app, client):
    sid = sessions_by_arm(
        app, client
    )["control"]

    for pos, choice in enumerate(
        ("B", "B", "B", "A")
    ):
        assert answer(
            client, sid, pos, choice
        ).status_code == 200

    progress = client.get(
        endpoint(sid, "question")
    ).get_json()

    assert progress["complete"] is True
    assert progress["question"] is None


def test_response_does_not_expose_private_state(
    app,
    client,
):
    sid = sessions_by_arm(
        app, client
    )["adaptive_threshold"]

    response = answer(client, sid, 0, "A")

    text = response.get_data(as_text=True)

    for secret_field in (
        "correct_id",
        "mastery_belief",
        "policy_mode",
        "participant_id",
        "simulated_action",
    ):
        assert secret_field not in text


def test_invalid_submission_cannot_advance(client):
    sid = enroll(client, "invalid-submission")

    response = client.post(
        endpoint(sid, "responses"),
        json={
            "item_id": "demo_main_1",
            "choice_id": "INVALID",
            "request_id": "bad-answer",
        },
    )

    assert response.status_code == 400

    progress = client.get(
        endpoint(sid, "question")
    ).get_json()

    assert progress["position"] == 0
