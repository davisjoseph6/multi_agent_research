"""HTTP-level smoke tests for the local browser interface."""

from src.prototype.durable_api import create_durable_app


def client(tmp_path):
    app = create_durable_app(
        tmp_path / "browser_test.sqlite3"
    )
    app.config["TESTING"] = True
    return app.test_client()


def test_demo_page_is_accessible(tmp_path):
    response = client(tmp_path).get("/demo")

    assert response.status_code == 200
    assert b"Behavioral Economics Quiz" in response.data
    assert b"Not an approved student study" in response.data


def test_demo_page_has_restrictive_headers(tmp_path):
    response = client(tmp_path).get("/demo")

    assert response.headers["Cache-Control"] == "no-store"

    policy = response.headers["Content-Security-Policy"]

    assert "script-src 'self'" in policy
    assert "connect-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy


def test_javascript_and_css_are_served(tmp_path):
    browser = client(tmp_path)

    javascript = browser.get(
        "/static/durable_quiz.js"
    )

    stylesheet = browser.get(
        "/static/durable_quiz.css"
    )

    assert javascript.status_code == 200
    assert stylesheet.status_code == 200

    assert b"request_id" in javascript.data
    assert b"sessionStorage" in javascript.data
    assert b"textContent" in javascript.data


def test_page_and_api_use_same_application(tmp_path):
    browser = client(tmp_path)

    assert browser.get("/demo").status_code == 200

    created = browser.post("/api/v1/durable/sessions")

    assert created.status_code == 201

    sid = created.get_json()["session_id"]

    question = browser.get(
        f"/api/v1/durable/sessions/{sid}/question"
    )

    assert question.status_code == 200
    assert question.get_json()["question"]["id"] == (
        "demo_main_1"
    )


def test_loading_page_does_not_create_session(tmp_path):
    browser = client(tmp_path)

    response = browser.get("/demo")

    assert response.status_code == 200

    # Rendering the page itself must not answer questions,
    # create sessions, or invoke the recovery planner.
    assert b"correct_id" not in response.data
    assert b"simulated_action" not in response.data
