"""Loopback-only integration tests: blinded synthetic roster to real V3 actions.

These do not authorize a human study or test an external production browser.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import re
import secrets
import uuid
from pathlib import Path

import pytest

from src.prototype.pilot_admission_controls_draft import AdmissionDenied
from src.prototype.pilot_session_flow_draft import PilotSequenceError
from src.prototype.pilot_unified_fictional_browser import (
    FIXTURE_IDS, FixtureClock, advance_unified_fictional_visit,
    create_unified_fictional_browser_app, ensure_unified_fictional_roster,
)
from src.prototype.pilot_unified_sqlite_synthetic import (
    UnifiedSyntheticError, UnifiedSyntheticStudyStore,
)
from src.prototype.study_v2 import RECOVERY_ACTIONS

ROOT = Path(__file__).resolve().parents[1] / "docs" / "rct_candidate_v1"
BASE = "http://127.0.0.1:8767"
CONSENT = sha256(b"UNAPPROVED_SYNTHETIC_BROWSER_INFORMATION").hexdigest()
SCREENING = "UNIFIED_BROWSER_SYNTHETIC_SCREENING_V1"


def setup(tmp_path):
    clock = FixtureClock()
    operator = secrets.token_bytes(32)
    auditor = secrets.token_bytes(32)
    params = dict(
        consent_sha256=CONSENT, screening_version=SCREENING,
        operator_key=operator, auditor_key=auditor,
        clock=clock, items_path=ROOT / "items.csv",
        resources_path=ROOT / "resources.csv", simulations=41,
    )
    store = UnifiedSyntheticStudyStore(
        tmp_path / "fictional_admission.sqlite3", **params,
    )
    roster = ensure_unified_fictional_roster(
        store, operator, screening_version=SCREENING,
        information_sha256=CONSENT,
    )
    app = create_unified_fictional_browser_app(
        store, operator, roster, port=8767,
    )
    client = app.test_client()
    page = client.get("/", base_url=BASE)
    assert page.status_code == 200
    nonce = re.search(
        r'<meta name="preview-nonce" content="([^"]+)">',
        page.get_data(as_text=True),
    ).group(1)
    return store, roster, operator, auditor, clock, client, nonce, params


def post(client, nonce, route, body, expected=200):
    response = client.post(
        "/unified/api/" + route, base_url=BASE, json=body,
        headers={"Origin": BASE, "X-Preview-Nonce": nonce},
    )
    assert response.status_code == expected, (
        route, response.status_code, response.get_json(),
    )
    return response.get_json()


def act_once(client, nonce, fixture):
    action = post(client, nonce, "next", {"fixture": fixture})
    if action["action"] in ("COMPLETE", "AWAITING_SUPERVISOR"):
        return action
    assert post(client, nonce, "next", {"fixture": fixture}) == action
    assert post(client, nonce, "rendered", {
        "fixture": fixture, "action_id": action["action_id"],
    })["accepted"]
    if action["action"] in ("QUESTION", "DROP_2"):
        assert "answer_id" not in action["question"]
        reply = {"choice_id": action["question"]["options"][0][0]}
    elif action["action"] == "MVAS":
        reply = {"rating": 30}
    else:
        assert action["action"] in RECOVERY_ACTIONS
        reply = {"status": "completed"}
    submission = {
        "fixture": fixture, "action_id": action["action_id"],
        "request_id": uuid.uuid4().hex, "response": reply,
    }
    result = post(client, nonce, "act", submission)
    assert result["accepted"] and not result["replayed"]
    assert post(client, nonce, "act", submission)["replayed"]
    return action


def test_three_blinded_server_allocations_and_browser_assets(tmp_path):
    store, roster, operator, auditor, clock, client, nonce, params = setup(tmp_path)
    assert tuple(roster) == FIXTURE_IDS
    assert len(set(roster.values())) == 3
    assert all(pid.startswith("SYN_ADMISSION_") for pid in roster.values())
    assert ensure_unified_fictional_roster(
        store, operator, screening_version=SCREENING,
        information_sha256=CONSENT,
    ) == roster
    assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"
    for fixture in FIXTURE_IDS:
        status = post(client, nonce, "status", {"fixture": fixture})
        assert status["fixture"] == fixture
        assert status["session"] == 1
        assert status["stage"] == "pretest"
        assert not status["human_enrollment_authorized"]
        assert not any(k in status for k in (
            "arm", "pid", "private_invitation", "operator_key", "token",
        ))
    page = client.get("/", base_url=BASE)
    html = page.get_data(as_text=True)
    assert nonce in html
    assert "SYNTHETIC-ONLY" in html
    assert 'id="fixture-select"' in html
    assert 'src="/unified.js"' in html
    assert page.headers["X-Synthetic-Only"] == "1"
    assert "default-src 'none'" in page.headers["Content-Security-Policy"]
    assert client.get("/unified.js", base_url=BASE).status_code == 200
    assert client.get("/unified.css", base_url=BASE).status_code == 200
    displayed_arms = set()
    for pid in roster.values():
        learner, arm = store.operator_lookup(operator, pid)
        assert learner.startswith("SYN_PILOT_")
        assert arm in "ABC"
        displayed_arms.add(arm)
    assert displayed_arms == {"A", "B", "C"}
    with store.admission._transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM admission_people").fetchone()[0] == 9
        assert db.execute("SELECT COUNT(*) FROM unified_demo_roster").fetchone()[0] == 3


def test_unguarded_and_public_enrollment_routes_fail_closed(tmp_path):
    store, roster, operator, auditor, clock, client, nonce, params = setup(tmp_path)
    for route in ("enroll", "consent", "start", "admin", "withdraw"):
        response = post(client, nonce, route, {"fixture": "F1"}, expected=404)
        assert response is None
    for route in ("/api/rct/enroll", "/api/rct/consent", "/staff", "/health"):
        response = client.get(route, base_url=BASE)
        assert response.status_code == 404
    assert client.post(
        "/unified/api/status", json={"fixture": "F1"}, base_url=BASE,
    ).status_code == 403
    assert client.post(
        "/unified/api/status", json={"fixture": "F1"}, base_url=BASE,
        headers={"Origin": BASE},
    ).status_code == 403
    assert client.post(
        "/unified/api/status", json={"fixture": "F1"}, base_url=BASE,
        headers={"Origin": "https://other.example", "X-Preview-Nonce": nonce},
    ).status_code == 403
    assert client.get("/", base_url="http://evil.example:8767").status_code == 403
    assert client.get("/", base_url=BASE, environ_overrides={
        "REMOTE_ADDR": "192.0.2.10",
    }).status_code == 403
    assert post(client, nonce, "status", {"fixture": "X"}, 409)["error"]
    assert post(client, nonce, "status", {"fixture": "F1", "arm": "A"}, 409)["error"]
    assert post(client, nonce, "next", {"fixture": "F1", "arm": "B"}, 409)["error"]
    assert post(client, nonce, "next", {"fixture": "F1", "at": "fake"}, 409)["error"]


def test_offline_visit_advance_and_one_complete_three_visit_journey(tmp_path):
    store, roster, operator, auditor, clock, client, nonce, params = setup(tmp_path)
    with pytest.raises(UnifiedSyntheticError):
        advance_unified_fictional_visit(
            store, operator, "F1", roster, clock,
        )
    fixture = "F1"
    pid = roster[fixture]
    learner, private_arm = store.operator_lookup(operator, pid)
    counts = {"QUESTION": 0, "MVAS": 0}
    for visit in (1, 2, 3):
        if visit > 1:
            advance = advance_unified_fictional_visit(
                store, operator, fixture, roster, clock,
            )
            assert advance["visit_started"] == visit
        for step in range(65):
            status = post(client, nonce, "status", {"fixture": fixture})
            if status["stage"] in ("awaiting_visit", "complete"):
                break
            action = act_once(client, nonce, fixture)
            counts[action["action"]] = counts.get(action["action"], 0) + 1
        else:
            pytest.fail("the fictional V3 learning visit never ended")
        assert post(client, nonce, "status", {
            "fixture": fixture,
        })["visits_finished"] == visit
    finish = advance_unified_fictional_visit(
        store, operator, fixture, roster, clock, finish_final=True,
    )
    assert finish["visits_finished"] == 3
    assert counts["QUESTION"] == 87
    assert counts["MVAS"] == 6
    assert store.learning.scores(learner)["practice"]["answered"] == 55
    assert store.operator_lookup(operator, pid) == (learner, private_arm)
    with store.admission._transaction() as db:
        learning = store.learning._load(db, learner)
        attendance = db.execute(
            "SELECT finished_at FROM admission_visits WHERE pid=? "
            "ORDER BY visit", (pid,),
        ).fetchall()
    assert len(attendance) == len(learning.visit_finished_at) == 3
    for recorded, completed in zip(attendance, learning.visit_finished_at):
        assert datetime.fromisoformat(recorded["finished_at"]) >= completed
    assert store.audit(auditor)["result"] == "PASS_SYNTHETIC_ONLY"
    assert post(client, nonce, "next", {"fixture": fixture})["action"] == "COMPLETE"


def test_restart_changes_nonce_without_changing_pending_question(tmp_path):
    store, roster, operator, auditor, clock, client, nonce, params = setup(tmp_path)
    action = post(client, nonce, "next", {"fixture": "F2"})
    reopened = UnifiedSyntheticStudyStore(store.path, **params)
    roster2 = ensure_unified_fictional_roster(
        reopened, operator, screening_version=SCREENING,
        information_sha256=CONSENT,
    )
    app = create_unified_fictional_browser_app(
        reopened, operator, roster2, port=8767,
    )
    new_client = app.test_client()
    html = new_client.get("/", base_url=BASE).get_data(as_text=True)
    nonce2 = re.search(
        r'<meta name="preview-nonce" content="([^"]+)">', html,
    ).group(1)
    assert nonce2 != nonce
    assert post(new_client, nonce, "status", {"fixture": "F2"}, 403)["error"]
    assert post(new_client, nonce2, "next", {"fixture": "F2"}) == action


def test_frontend_reuses_request_id_and_never_requests_arm():
    js = (
        Path(__file__).resolve().parents[1]
        / "src/prototype/static/pilot_unified_fictional_browser.js"
    ).read_text(encoding="utf-8")
    assert js.count("window.crypto.randomUUID()") == 1
    assert "submissionAttempt.fixture === currentFixture()" in js
    assert "const result = await requestPreview(\"act\", submission);" in js
    assert "/unified/api/" in js
    assert "fixture: currentFixture()" in js
    assert "arm:" not in js
    assert "state.arm" not in js
