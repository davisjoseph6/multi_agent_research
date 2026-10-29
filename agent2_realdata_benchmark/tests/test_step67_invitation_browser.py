"""Step 67 invitation-browser integration tests."""

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
        tmp_path / "step67.sqlite3",
        block_sizes=(6,),
    )

    instance.config["TESTING"] = True
    return instance


@pytest.fixture
def client(app):
    return app.test_client()


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def enroll(client, app):
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


def answer(client, token, sid, position, choice):
    return client.post(
        endpoint(sid, "responses"),
        headers=headers(token),
        json={
            "item_id": INSTRUCTIONAL_DEMO_ITEMS[
                position
            ].item_id,
            "choice_id": choice,
            "request_id": f"step67-{sid}-{position}",
        },
    )


def selected_arms(client, app):
    selected = {}
    quiz = app.extensions["invitation_quiz"]

    for _ in range(6):
        token, sid = enroll(client, app)

        selected.setdefault(
            quiz.read_policy(sid),
            (token, sid),
        )

    assert set(selected) == {
        "control",
        "fixed_summary",
        "adaptive_threshold",
    }

    return selected


def test_browser_and_security_headers(client):
    response = client.get("/trial-invite")

    assert response.status_code == 200
    assert b'src="/trial-invite/app.js"' in response.data

    assert response.headers["Cache-Control"] == "no-store"

    csp = response.headers["Content-Security-Policy"]

    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_browser_does_not_embed_credentials(client):
    response = client.get("/trial-invite")

    html = response.get_data(as_text=True)

    assert 'type="password"' in html
    assert "token_digest" not in html
    assert "participant_id" not in html
    assert "policy_mode" not in html


def test_javascript_uses_authorization_header(client):
    response = client.get("/trial-invite/app.js")

    assert response.status_code == 200

    script = response.get_data(as_text=True)

    assert "Authorization" in script
    assert "Bearer" in script
    assert "/api/v1/trial-invite" in script

    assert "localStorage" not in script
    assert "sessionStorage" not in script
    assert "window.location.search" not in script


def test_stylesheets_are_served(client):
    assert client.get(
        "/trial-invite/base.css"
    ).status_code == 200

    assert client.get(
        "/trial-invite/assistance.css"
    ).status_code == 200


def test_legacy_routes_remain_unregistered(client):
    assert client.post(
        "/api/v1/trial-dev/enroll"
    ).status_code == 404

    assert client.get("/trial-dev").status_code == 404

    assert client.get(
        "/static/experimental_quiz.js"
    ).status_code == 404


def test_repeated_enrollment_recovers_session(
    client, app
):
    token, sid = enroll(client, app)

    response = client.post(
        f"{PREFIX}/enroll",
        headers=headers(token),
    )

    assert response.status_code == 200
    assert response.get_json()["session_id"] == sid


def test_control_completes_unassisted(client, app):
    token, sid = selected_arms(
        client, app
    )["control"]

    for pos, choice in enumerate(
        ("B", "B", "B", "A")
    ):
        assert answer(
            client, token, sid, pos, choice
        ).status_code == 200

    state = client.get(
        endpoint(sid, "question"),
        headers=headers(token),
    ).get_json()

    assert state["complete"] is True
    assert state["question"] is None


def test_fixed_assistance_is_protected(client, app):
    token, sid = selected_arms(
        client, app
    )["fixed_summary"]

    assert answer(
        client, token, sid, 0, "A"
    ).status_code == 200

    pending = client.get(
        endpoint(sid, "question"),
        headers=headers(token),
    ).get_json()

    assert pending["assistance_pending"] is True
    assert pending["question"] is None

    accepted = client.post(
        endpoint(sid, "assistance/decision"),
        headers=headers(token),
        json={
            "source_position": 0,
            "accept": True,
        },
    )

    assert accepted.status_code == 200

    delivered = client.post(
        endpoint(sid, "assistance/delivery"),
        headers=headers(token),
        json={"source_position": 0},
    )

    assert delivered.status_code == 200
    assert delivered.get_json()["offer"]["body"]


def test_adaptive_abstains_after_correct(client, app):
    token, sid = selected_arms(
        client, app
    )["adaptive_threshold"]

    assert answer(
        client, token, sid, 0, "B"
    ).status_code == 200

    state = client.get(
        endpoint(sid, "question"),
        headers=headers(token),
    ).get_json()

    assert state["assistance_pending"] is False
    assert state["question"]["id"] == "demo_main_2"


def test_remote_browser_is_rejected(client):
    response = client.get(
        "/trial-invite",
        environ_overrides={
            "REMOTE_ADDR": "203.0.113.20"
        },
    )

    assert response.status_code == 403
