"""Step 22: browser assets and full fixed-summary HTTP contract."""

from src.prototype.durable_api import create_durable_app
from src.prototype.item_bank import (
    INSTRUCTIONAL_DEMO_ITEMS,
    INSTRUCTIONAL_DEMO_VERSION,
)


def fixed(tmp_path):
    app = create_durable_app(
        tmp_path / "fixed_browser.sqlite3",
        items=INSTRUCTIONAL_DEMO_ITEMS,
        bank_version=INSTRUCTIONAL_DEMO_VERSION,
        fixed_summary=True,
    )
    app.config["TESTING"] = True
    return app


def url(sid, suffix):
    return f"/api/v1/durable/sessions/{sid}/{suffix}"


def submit(client, sid, position):
    return client.post(
        url(sid, "responses"),
        json={
            "item_id": INSTRUCTIONAL_DEMO_ITEMS[position].item_id,
            "choice_id": "A",
            "request_id": f"browser-step22-{position}",
        },
    )


def test_fixed_demo_page_renders(tmp_path):
    response = fixed(tmp_path).test_client().get("/demo")
    assert response.status_code == 200
    assert b"FIXED-SUMMARY DEVELOPMENT DEMO" in response.data
    assert b"fixed_summary_quiz.js" in response.data
    assert b"accept-assistance" in response.data
    assert b"decline-assistance" in response.data
    assert b"view-assistance" in response.data
    assert b"resource-body" in response.data


def test_unassisted_demo_remains_separate(tmp_path):
    app = create_durable_app(tmp_path / "plain_browser.sqlite3")
    response = app.test_client().get("/demo")
    assert response.status_code == 200
    assert b"durable_quiz.js" in response.data
    assert b"fixed_summary_quiz.js" not in response.data


def test_fixed_demo_reuses_restrictive_headers(tmp_path):
    response = fixed(tmp_path).test_client().get("/demo")
    assert response.headers["Cache-Control"] == "no-store"
    csp = response.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp
    assert "connect-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_new_browser_assets_are_served(tmp_path):
    client = fixed(tmp_path).test_client()
    js = client.get("/static/fixed_summary_quiz.js")
    css = client.get("/static/fixed_summary_quiz.css")
    assert js.status_code == 200
    assert css.status_code == 200
    assert b"assistance/" in js.data
    assert b"request_id" in js.data
    assert b"sessionStorage" in js.data
    assert b"textContent" in js.data
    assert b"innerHTML" not in js.data


def test_offer_content_is_not_embedded_in_initial_html(tmp_path):
    from src.prototype.assistance import DEMO_SUMMARY

    response = fixed(tmp_path).test_client().get("/demo")
    assert DEMO_SUMMARY.body.encode("utf-8") not in response.data
    assert b"correct_id" not in response.data


def test_offer_requires_explicit_acceptance_and_delivery(tmp_path):
    app = fixed(tmp_path)
    client = app.test_client()
    created = client.post("/api/v1/durable/sessions")
    assert created.status_code == 201
    sid = created.get_json()["session_id"]
    assert submit(client, sid, 0).status_code == 200

    before = client.get(url(sid, "assistance")).get_json()["offer"]
    assert before["status"] == "offered"
    assert before["body"] is None
    assert client.get(url(sid, "question")).get_json()["question"] is None
    assert submit(client, sid, 1).status_code == 409

    accepted = client.post(
        url(sid, "assistance/decision"),
        json={"source_position": 0, "accept": True},
    ).get_json()["offer"]
    assert accepted["status"] == "accepted"
    assert accepted["body"] is None
    assert submit(client, sid, 1).status_code == 409

    delivered = client.post(
        url(sid, "assistance/delivery"),
        json={"source_position": 0},
    ).get_json()["offer"]
    assert delivered["status"] == "delivered"
    assert delivered["body"]
    assert client.get(url(sid, "question")).get_json()["question"]["id"] == "demo_main_2"
    assert client.get(url(sid, "assistance")).get_json()["offer"]["body"] == delivered["body"]


def test_decline_then_probe_never_requires_assistance(tmp_path):
    client = fixed(tmp_path).test_client()
    sid = client.post("/api/v1/durable/sessions").get_json()["session_id"]
    for position in (0, 1):
        assert submit(client, sid, position).status_code == 200
        current = client.get(url(sid, "assistance")).get_json()["offer"]
        assert current["status"] == "offered"
        assert client.post(
            url(sid, "assistance/decision"),
            json={"source_position": position, "accept": False},
        ).status_code == 200
    assert submit(client, sid, 2).status_code == 200
    assert client.get(url(sid, "assistance")).get_json()["offer"] is None
    assert submit(client, sid, 3).get_json()["complete"] is True


def test_restart_recovers_summary_body_only_after_delivery(tmp_path):
    database = tmp_path / "recovered.sqlite3"
    def app():
        return create_durable_app(
            database,
            items=INSTRUCTIONAL_DEMO_ITEMS,
            bank_version=INSTRUCTIONAL_DEMO_VERSION,
            fixed_summary=True,
        )
    first = app().test_client()
    sid = first.post("/api/v1/durable/sessions").get_json()["session_id"]
    assert submit(first, sid, 0).status_code == 200
    assert first.post(
        url(sid, "assistance/decision"),
        json={"source_position": 0, "accept": True},
    ).status_code == 200

    second = app().test_client()
    accepted = second.get(url(sid, "assistance")).get_json()["offer"]
    assert accepted["status"] == "accepted"
    assert accepted["body"] is None
    assert second.get(url(sid, "question")).get_json()["question"] is None
    assert second.post(
        url(sid, "assistance/delivery"),
        json={"source_position": 0},
    ).status_code == 200

    third = app().test_client()
    delivered = third.get(url(sid, "assistance")).get_json()["offer"]
    assert delivered["status"] == "delivered"
    assert delivered["body"]
    assert third.get(url(sid, "question")).get_json()["question"]["id"] == "demo_main_2"


def test_loading_demo_does_not_create_sessions(tmp_path):
    app = fixed(tmp_path)
    client = app.test_client()
    assert client.get("/demo").status_code == 200
    assert client.get("/demo").status_code == 200
    sid = client.post("/api/v1/durable/sessions").get_json()["session_id"]
    assert client.get(url(sid, "question")).get_json()["position"] == 0
