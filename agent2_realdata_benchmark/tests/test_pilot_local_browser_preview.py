"""Loopback-only Flask browser-preview contracts; no network listener or humans."""
import re
import uuid
from pathlib import Path

import pytest

from src.prototype.pilot_local_browser_preview import (
    advance_fictional_visit,
    create_fictional_preview_app,
    ensure_three_fictional_records,
)
from src.prototype.pilot_session_flow_draft import PilotSequenceError
from src.prototype.pilot_three_arm_store_draft import SyntheticThreeArmPilotStore
from src.prototype.study_v2 import RECOVERY_ACTIONS

ROOT = Path(__file__).resolve().parents[1] / "docs/rct_candidate_v1"
BASE = "http://127.0.0.1:8765"


def create_store(tmp_path):
    return SyntheticThreeArmPilotStore(
        tmp_path / "fictional_browser_preview.sqlite3",
        items_path=ROOT / "items.csv",
        resources_path=ROOT / "resources.csv",
        simulations=41,
    )


def setup(tmp_path):
    store = create_store(tmp_path)
    app = create_fictional_preview_app(store, port=8765)
    client = app.test_client()
    html = client.get("/", base_url=BASE)
    assert html.status_code == 200
    nonce = re.search(
        r'<meta name="preview-nonce" content="([^"]+)">',
        html.get_data(as_text=True),
    ).group(1)
    return store, client, nonce


def post(client, nonce, route, body, expected=200):
    response = client.post(
        "/preview/api/" + route, json=body, base_url=BASE,
        headers={
            "Origin": BASE,
            "X-Preview-Nonce": nonce,
        },
    )
    assert response.status_code == expected, (route, response.get_json())
    return response.get_json()


def act_once(client, nonce, arm, *, rating=20):
    action = post(client, nonce, "next", dict(arm=arm))
    if action["action"] in ("COMPLETE", "AWAITING_SUPERVISOR"):
        return action
    assert action == post(client, nonce, "next", dict(arm=arm))
    assert post(client, nonce, "rendered", dict(
        arm=arm, action_id=action["action_id"]
    ))["accepted"]
    kind = action["action"]
    if kind in ("QUESTION", "DROP_2"):
        assert "answer_id" not in action["question"]
        response = dict(choice_id=action["question"]["options"][0][0])
    elif kind == "MVAS":
        response = dict(rating=rating)
    else:
        assert kind in RECOVERY_ACTIONS
        response = dict(status="completed")
    submission = dict(
        arm=arm, action_id=action["action_id"],
        request_id=uuid.uuid4().hex, response=response,
    )
    assert post(client, nonce, "act", submission)["accepted"]
    assert post(client, nonce, "act", submission)["replayed"]
    return action


def test_seed_exact_three_synthetic_and_preview_assets(tmp_path):
    store, client, nonce = setup(tmp_path)
    pids = ensure_three_fictional_records(store)
    assert list(pids) == ["A", "B", "C"]
    assert len(set(pids.values())) == 3
    assert all(value.startswith("SYN_PILOT_") for value in pids.values())
    assert all(store.snapshot(pid)["session"] == 1 for pid in pids.values())
    assert ensure_three_fictional_records(store) == pids

    page = client.get("/", base_url=BASE)
    body = page.get_data(as_text=True)
    assert nonce in body
    assert "FICTIONAL DATA ONLY" in body
    assert 'id="arm-select"' in body
    assert 'id="answer-form"' in body
    assert 'src="/preview.js"' in body
    assert 'href="/preview.css"' in body
    assert "default-src 'none'" in page.headers["Content-Security-Policy"]
    assert page.headers["X-Synthetic-Only"] == "1"
    assert page.headers["Cache-Control"] == "no-store"
    assert client.get("/preview.js", base_url=BASE).status_code == 200
    assert client.get("/preview.css", base_url=BASE).status_code == 200


def test_no_enrollment_and_loopback_nonce_origin_restrictions(tmp_path):
    _, client, nonce = setup(tmp_path)
    assert client.post("/api/rct/enroll", base_url=BASE, json={}).status_code == 403
    assert client.post("/preview/api/enroll", base_url=BASE, json={}).status_code == 403
    assert client.post("/preview/api/start", base_url=BASE, json={}).status_code == 403
    assert client.get("/admin", base_url=BASE).status_code == 404
    # No origin or nonce means rejected, including unknown routes on POST.
    assert client.post("/preview/api/status", base_url=BASE,
                       json={"arm": "A"}).status_code == 403
    assert client.post("/preview/api/status", base_url=BASE,
                       json={"arm": "A"},
                       headers={"Origin": BASE}).status_code == 403
    assert client.post("/preview/api/status", base_url=BASE,
                       json={"arm": "A"},
                       headers={"Origin": "https://evil.example",
                                "X-Preview-Nonce": nonce}).status_code == 403
    assert client.get("/", base_url="http://evil.example:8765").status_code == 403
    assert client.get("/", base_url=BASE, environ_overrides={
        "REMOTE_ADDR": "192.0.2.27"
    }).status_code == 403
    assert post(client, nonce, "status", dict(arm="D"), 409)["error"]


def test_private_operator_advance_only_after_completed_visit(tmp_path):
    store, client, nonce = setup(tmp_path)
    with pytest.raises(PilotSequenceError):
        advance_fictional_visit(store, "A")
    with pytest.raises(PilotSequenceError):
        advance_fictional_visit(store, "X")
    pid = ensure_three_fictional_records(store)["C"]
    assert post(client, nonce, "status", dict(arm="C"))["stage"] == "pretest"
    count = 0
    for _ in range(45):
        state = post(client, nonce, "status", dict(arm="C"))
        if state["stage"] == "awaiting_visit":
            break
        act_once(client, nonce, "C", rating=17)
        count += 1
    else:
        raise AssertionError("first fictional visit did not finish")
    assert count == 38
    assert store.snapshot(pid)["visits_finished"] == 1
    assert post(client, nonce, "next", dict(arm="C"))["action"] == "AWAITING_SUPERVISOR"
    assert advance_fictional_visit(store, "C")["visit"] == 2
    assert post(client, nonce, "status", dict(arm="C"))["stage"] == "mvas_pre"
    assert post(client, nonce, "next", dict(arm="C"))["action"] == "MVAS"
    with pytest.raises(PilotSequenceError):
        advance_fictional_visit(store, "C")


def test_mvas_bad_rating_keeps_pending_and_pretest_no_feedback(tmp_path):
    store, client, nonce = setup(tmp_path)
    # Arm C uses only questions, so after 16 baseline answers we see M-VAS.
    for _ in range(16):
        q = act_once(client, nonce, "C")
        assert q["action"] == "QUESTION" and q["stage"] == "pretest"
    action = post(client, nonce, "next", dict(arm="C"))
    assert action["stage"] == "mvas_pre"
    post(client, nonce, "rendered", dict(
        arm="C", action_id=action["action_id"]
    ))
    bad = dict(
        arm="C", action_id=action["action_id"], request_id="bad",
        response=dict(rating=101),
    )
    assert post(client, nonce, "act", bad, 422)["error"]
    assert post(client, nonce, "next", dict(arm="C")) == action
    good = dict(
        arm="C", action_id=action["action_id"], request_id="good",
        response=dict(rating=0),
    )
    assert post(client, nonce, "act", good)["stage"] == "practice"
    assert store.snapshot(ensure_three_fictional_records(store)["C"])["ratings"][0][0] == 0


def test_restarted_fictional_app_preserves_pending_question(tmp_path):
    store, client, nonce = setup(tmp_path)
    first = post(client, nonce, "next", dict(arm="A"))
    app2 = create_fictional_preview_app(store, port=8765)
    second_client = app2.test_client()
    page = second_client.get("/", base_url=BASE).get_data(as_text=True)
    nonce2 = re.search(
        r'<meta name="preview-nonce" content="([^"]+)">', page
    ).group(1)
    assert nonce2 != nonce
    assert post(second_client, nonce2, "next", dict(arm="A")) == first
    # Old preview page nonce cannot submit after server restarts.
    assert post(second_client, nonce, "status", dict(arm="A"), 403)["error"]
