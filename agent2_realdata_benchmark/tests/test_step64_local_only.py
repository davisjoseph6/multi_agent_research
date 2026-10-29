"""Loopback-only development API security regression tests.

These checks do not constitute participant authentication.
"""

import pytest

from src.prototype.experimental_api import (
    PREFIX,
    create_experimental_app,
)


@pytest.fixture
def client(tmp_path):

    app = create_experimental_app(
        tmp_path / "step64_local_only.sqlite3",
        block_sizes=(6,),
    )

    app.config["TESTING"] = True

    return app.test_client()


def test_local_health_is_accessible(client):

    response = client.get(f"{PREFIX}/health")

    assert response.status_code == 200

    assert response.get_json()["mode"] == (
        "trial_development_only"
    )


def test_remote_health_is_rejected(client):

    response = client.get(
        f"{PREFIX}/health",
        environ_overrides={
            "REMOTE_ADDR": "203.0.113.20"
        },
    )

    assert response.status_code == 403

    assert response.get_json()["error"] == (
        "development_local_only"
    )


def test_remote_enrollment_is_rejected(client):

    data = {
        "enrollment_request_id":
            "synthetic-remote-request"
    }

    denied = client.post(
        f"{PREFIX}/enroll",
        json=data,
        environ_overrides={
            "REMOTE_ADDR": "203.0.113.20"
        },
    )

    assert denied.status_code == 403

    # A rejected request must not allocate a participant.
    accepted = client.post(
        f"{PREFIX}/enroll",
        json=data,
    )

    assert accepted.status_code == 201
    assert accepted.get_json()["replayed"] is False


def test_remote_browser_is_rejected(client):

    response = client.get(
        "/trial-dev",
        environ_overrides={
            "REMOTE_ADDR": "203.0.113.20"
        },
    )

    assert response.status_code == 403


def test_remote_javascript_is_rejected(client):

    response = client.get(
        "/static/experimental_quiz.js",
        environ_overrides={
            "REMOTE_ADDR": "203.0.113.20"
        },
    )

    assert response.status_code == 403


def test_nonlocal_hostname_is_rejected(client):

    response = client.get(
        f"{PREFIX}/health",
        base_url="http://trial.example:5057",
        environ_overrides={
            "REMOTE_ADDR": "127.0.0.1"
        },
    )

    assert response.status_code == 403


def test_forwarded_header_does_not_bypass_guard(client):

    response = client.get(
        f"{PREFIX}/health",
        headers={
            "X-Forwarded-For": "127.0.0.1",
            "X-Forwarded-Host": "localhost",
        },
        environ_overrides={
            "REMOTE_ADDR": "203.0.113.20"
        },
    )

    assert response.status_code == 403


def test_ipv6_loopback_is_accepted(client):

    response = client.get(
        f"{PREFIX}/health",
        base_url="http://[::1]:5057",
        environ_overrides={
            "REMOTE_ADDR": "::1"
        },
    )

    assert response.status_code == 200
