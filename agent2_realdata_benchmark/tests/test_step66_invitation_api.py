"""Invitation-protected development API tests.

No human participants or actual research data.
"""

import pytest

from src.prototype.invitation_api import (
    PREFIX,
    create_invitation_app,
)

from src.prototype.item_bank import (
    INSTRUCTIONAL_DEMO_ITEMS,
)


@pytest.fixture
def app(tmp_path):
    instance = create_invitation_app(
        tmp_path / "step66.sqlite3",
        block_sizes=(6,),
    )

    instance.config["TESTING"] = True
    return instance


@pytest.fixture
def client(app):
    return app.test_client()


def headers(token):
    return {
        "Authorization": f"Bearer {token}"
    }


def create_enrollment(client, app):
    store = app.extensions["invitation_enrollment"]

    token = store.issue_invitation()

    response = client.post(
        f"{PREFIX}/enroll",
        headers=headers(token),
    )

    assert response.status_code == 201

    return token, response.get_json()["session_id"]


def endpoint(sid, suffix):
    return f"{PREFIX}/sessions/{sid}/{suffix}"


def answer(client, token, sid, position, choice="A"):
    return client.post(
        endpoint(sid, "responses"),
        headers=headers(token),
        json={
            "item_id": INSTRUCTIONAL_DEMO_ITEMS[
                position
            ].item_id,
            "choice_id": choice,
            "request_id": f"step66-{sid}-{position}",
        },
    )


def test_local_health(client):
    response = client.get(f"{PREFIX}/health")

    assert response.status_code == 200
    assert response.get_json()["mode"] == (
        "invitation_development_only"
    )


def test_missing_invitation_is_rejected(client):
    response = client.post(f"{PREFIX}/enroll")

    assert response.status_code == 401


def test_unknown_invitation_is_rejected(client):
    response = client.post(
        f"{PREFIX}/enroll",
        headers=headers("inv1_" + "f" * 64),
    )

    assert response.status_code == 401


def test_valid_invitation_recovers_same_session(
    client, app
):
    token, sid = create_enrollment(client, app)

    replay = client.post(
        f"{PREFIX}/enroll",
        headers=headers(token),
    )

    assert replay.status_code == 200
    assert replay.get_json()["session_id"] == sid
    assert replay.get_json()["replayed"] is True


def test_no_unauthenticated_legacy_routes(client):
    assert client.post(
        "/api/v1/trial-dev/enroll"
    ).status_code == 404

    assert client.post(
        "/api/v1/durable/sessions"
    ).status_code == 404

    assert client.get("/trial-dev").status_code == 404


def test_session_requires_credential(client, app):
    token, sid = create_enrollment(client, app)

    unauthenticated = client.get(
        endpoint(sid, "question")
    )

    authenticated = client.get(
        endpoint(sid, "question"),
        headers=headers(token),
    )

    assert unauthenticated.status_code == 401
    assert authenticated.status_code == 200


def test_cross_session_access_is_blocked(client, app):
    token_a, sid_a = create_enrollment(client, app)
    token_b, sid_b = create_enrollment(client, app)

    assert sid_a != sid_b

    forbidden = [
        client.get(
            endpoint(sid_b, "question"),
            headers=headers(token_a),
        ),
        client.get(
            endpoint(sid_b, "assistance"),
            headers=headers(token_a),
        ),
        answer(
            client, token_a, sid_b, 0
        ),
        client.post(
            endpoint(sid_b, "assistance/decision"),
            headers=headers(token_a),
            json={
                "source_position": 0,
                "accept": False,
            },
        ),
        client.post(
            endpoint(sid_b, "assistance/delivery"),
            headers=headers(token_a),
            json={"source_position": 0},
        ),
    ]

    assert all(
        response.status_code == 403
        for response in forbidden
    )

    own = client.get(
        endpoint(sid_b, "question"),
        headers=headers(token_b),
    )

    assert own.status_code == 200
    assert own.get_json()["position"] == 0


def test_control_and_assisted_policies(client, app):
    store = app.extensions["invitation_enrollment"]
    quiz = app.extensions["invitation_quiz"]

    sessions = {}

    for _ in range(6):
        token = store.issue_invitation()

        response = client.post(
            f"{PREFIX}/enroll",
            headers=headers(token),
        )

        assert response.status_code == 201

        sid = response.get_json()["session_id"]

        mode = quiz.read_policy(sid)

        sessions.setdefault(mode, (token, sid))

    assert set(sessions) == {
        "control",
        "fixed_summary",
        "adaptive_threshold",
    }

    for mode, (token, sid) in sessions.items():

        response = answer(
            client, token, sid, 0, "A"
        )

        assert response.status_code == 200

        state = client.get(
            endpoint(sid, "question"),
            headers=headers(token),
        ).get_json()

        expected = mode != "control"

        assert state["assistance_pending"] == expected

        assert (
            state["question"] is None
        ) == expected


def test_pending_assistance_cannot_be_bypassed(
    client, app
):
    store = app.extensions["invitation_enrollment"]
    quiz = app.extensions["invitation_quiz"]

    selected = None

    for _ in range(6):
        token = store.issue_invitation()

        result = client.post(
            f"{PREFIX}/enroll",
            headers=headers(token),
        )

        sid = result.get_json()["session_id"]

        if quiz.read_policy(sid) == "fixed_summary":
            selected = (token, sid)
            break

    assert selected is not None

    token, sid = selected

    assert answer(
        client, token, sid, 0, "A"
    ).status_code == 200

    assert answer(
        client, token, sid, 1, "A"
    ).status_code == 409

    decision = client.post(
        endpoint(sid, "assistance/decision"),
        headers=headers(token),
        json={
            "source_position": 0,
            "accept": False,
        },
    )

    assert decision.status_code == 200

    assert answer(
        client, token, sid, 1, "A"
    ).status_code == 200


def test_sensitive_fields_not_exposed(client, app):
    token, sid = create_enrollment(client, app)

    responses = [
        client.post(
            f"{PREFIX}/enroll",
            headers=headers(token),
        ),
        client.get(
            endpoint(sid, "question"),
            headers=headers(token),
        ),
    ]

    for response in responses:
        text = response.get_data(as_text=True)

        for field in (
            "policy_mode",
            "participant_id",
            "mastery_belief",
            "correct_id",
            "token_digest",
        ):
            assert field not in text


def test_restart_preserves_authorization(tmp_path):
    database = tmp_path / "restart.sqlite3"

    app_a = create_invitation_app(
        database,
        block_sizes=(6,),
    )

    client_a = app_a.test_client()

    store = app_a.extensions["invitation_enrollment"]
    token = store.issue_invitation()

    enrolled = client_a.post(
        f"{PREFIX}/enroll",
        headers=headers(token),
    )

    assert enrolled.status_code == 201

    sid = enrolled.get_json()["session_id"]

    app_b = create_invitation_app(
        database,
        block_sizes=(6,),
    )

    client_b = app_b.test_client()

    restored = client_b.get(
        endpoint(sid, "question"),
        headers=headers(token),
    )

    assert restored.status_code == 200

    recovered_enrollment = client_b.post(
        f"{PREFIX}/enroll",
        headers=headers(token),
    )

    assert recovered_enrollment.status_code == 200
    assert (
        recovered_enrollment.get_json()["session_id"]
        == sid
    )


def test_remote_access_denied(client, app):
    token, sid = create_enrollment(client, app)

    response = client.get(
        endpoint(sid, "question"),
        headers=headers(token),
        environ_overrides={
            "REMOTE_ADDR": "203.0.113.20"
        },
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == (
        "development_local_only"
    )
