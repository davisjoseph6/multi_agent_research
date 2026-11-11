"""HTTP integration of private fictional V2 browser with durable crossover."""
from datetime import datetime, timezone
from pathlib import Path
import re

import pytest

from scripts.research_v2_fictional_browser import new_fictional_runtime
from src.prototype.research_v2_fictional_browser import (
    fictional_item, make_fictional_v2_app, FIXTURES,
)

NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)
PORT = 8774


@pytest.fixture
def harness(tmp_path):
    runtime = new_fictional_runtime(tmp_path, clock=lambda: NOW)
    app = make_fictional_v2_app(runtime, port=PORT)
    app.config["TESTING"] = True
    client = app.test_client()
    index = client.get("/", base_url=f"http://127.0.0.1:{PORT}")
    assert index.status_code == 200
    html = index.get_data(as_text=True)
    nonce = re.search(r'data-preview-nonce="([^"]+)"', html).group(1)
    return runtime, client, nonce


def post(h, route, obj=None, *, include_nonce=True, include_origin=True):
    runtime, client, nonce = h
    headers = {}
    if include_nonce:
        headers["X-Preview-Nonce"] = nonce
    if include_origin:
        headers["Origin"] = f"http://127.0.0.1:{PORT}"
    return client.post(
        f"/research-v2/api/{route}",
        json={"fixture": "F1", **(obj or {})},
        headers=headers,
        base_url=f"http://127.0.0.1:{PORT}",
    )


def ok(h, route, obj=None):
    response = post(h, route, obj)
    assert response.status_code == 200, response.json
    return response.json


def synthetic_question(h, form, index, *, period=0, correct=True,
                       req_prefix="a"):
    q = fictional_item(period, form, index, "en")
    choice = q["correct_index"] if correct else (q["correct_index"] + 1) % 4
    result = ok(h, "answer", {
        "item_id": q["item_id"],
        "selected_index": choice,
        "request_id": f"{req_prefix}_{period}_{form}_{index:03d}",
    })
    return result


def test_localhost_origin_nonce_csp_no_human_enrollment_routes(harness):
    runtime, client, nonce = harness
    assert post(harness, "status", include_nonce=False).status_code == 403
    assert post(harness, "status", include_origin=False).status_code == 403
    assert client.get(
        "/", base_url=f"http://127.0.0.1:{PORT}",
        environ_overrides={"REMOTE_ADDR": "203.0.113.9"}
    ).status_code == 403
    assert client.get("/", base_url="http://example.invalid").status_code == 403
    home = client.get("/", base_url=f"http://127.0.0.1:{PORT}")
    assert home.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in home.headers["Content-Security-Policy"]
    assert home.headers["Cache-Control"] == "no-store"
    assert home.headers["X-Synthetic-Only"] == "1"
    for path in ("/enroll", "/consent", "/admin", "/api/enroll", "/v2/human"):
        assert client.post(path, base_url=f"http://127.0.0.1:{PORT}").status_code in (403,404)
    stat = ok(harness, "status")
    assert not stat["human_enrollment_authorized"]
    assert not stat["real_email_sent"]
    assert "arm" not in stat and "token" not in stat
    assert set(FIXTURES) == set(runtime.identities)


def test_bilingual_placeholder_is_explicitly_fake_and_answer_key_is_private(harness):
    item = ok(harness, "item", {"language": "fr"})
    assert item["kind"] == "question"
    assert "FICTIF" in item["prompt"]
    assert len(item["options"]) == 4
    assert "correct_index" not in item and "answer_key" not in item
    assert item["form"] == "pretest"
    mastery = ok(harness, "mastery")
    assert mastery["independent_scores"] == {"pretest": None, "posttest": None}
    assert "email" not in str(mastery).lower()


def test_wrong_item_and_forged_scores_cannot_advance(harness):
    item = ok(harness, "item", {"language": "en"})
    forged = post(harness, "answer", {
        "item_id": "SYN_P0_pretest_005",
        "selected_index": 0, "request_id": "forged_00001",
    })
    assert forged.status_code == 409
    assert post(harness, "answer", {
        "item_id": item["item_id"], "selected_index": True,
        "request_id": "forged_00002",
    }).status_code == 409
    assert post(harness, "answer", {
        "item_id": item["item_id"], "selected_index": 0,
        "request_id": "forged_00003", "correct": True,
    }).status_code == 409
    q = fictional_item(0, "pretest", 0, "en")
    payload = {"item_id": q["item_id"], "selected_index": q["correct_index"],
               "request_id": "idempotent_00001"}
    first = ok(harness, "answer", payload)
    second = ok(harness, "answer", payload)
    assert first["correct"] and second["replayed"]
    altered = post(harness, "answer", payload | {
        "selected_index": (q["correct_index"] + 1) % 4
    })
    assert altered.status_code == 409
    assert ok(harness, "status")["counts"]["pretest"] == 1


def test_two_wrong_intervention_is_anchored_before_next_question(harness):
    for i in range(16):
        synthetic_question(harness, "pretest", i)
    synthetic_question(harness, "practice", 0, correct=False)
    result = synthetic_question(harness, "practice", 1, correct=False)
    assert result["recovery_required"] == "CONCEPT_SUMMARY"
    rec = ok(harness, "item", {"language": "en"})
    assert rec["kind"] == "recovery" and rec["action"] == "CONCEPT_SUMMARY"
    assert rec["item_id"] == "SYN_P0_practice_001"
    assert "counting both groups" in rec["prompt"]
    assert post(harness, "answer", {
        "item_id": "SYN_P0_practice_002", "selected_index": 0,
        "request_id": "bad_during_recovery",
    }).status_code == 409
    assert post(harness, "recovery/drop2", {
        "item_id": rec["item_id"], "selected_index": 0,
        "request_id": "bad_wrong_action",
    }).status_code == 409
    ok(harness, "recovery/ack", {"request_id": "ack_00001"})
    assert ok(harness, "item", {"language": "en"})["kind"] == "awaiting_continue"
    assert post(harness, "answer", {
        "item_id": "SYN_P0_practice_002", "selected_index": 0,
        "request_id": "bad_skip_continue",
    }).status_code == 409
    ok(harness, "decision", {"decision": "continue"})
    synthetic_question(harness, "practice", 2, correct=False)
    assert synthetic_question(harness, "practice", 3, correct=False)[
        "recovery_required"] == "DROP_2"
    drop = ok(harness, "item", {"language": "fr"})
    assert len(drop["options"]) == 2
    expected = fictional_item(0, "practice", 3, "en")
    indices = {i["choice_index"] for i in drop["options"]}
    assert indices == {expected["correct_index"],
                       (expected["correct_index"] + 1) % 4}
    bad = ok(harness, "recovery/drop2", {
        "item_id": drop["item_id"],
        "selected_index": (expected["correct_index"] + 1) % 4,
        "request_id": "bad_drop2_choice",
    })
    assert bad["retry_required"] and not bad["accepted"]
    completion = ok(harness, "recovery/drop2", {
        "item_id": drop["item_id"],
        "selected_index": expected["correct_index"],
        "request_id": "correct_drop2_choice",
    })
    assert completion["accepted"] and not completion["counted"]
    assert ok(harness, "item", {"language": "en"})["kind"] == "awaiting_continue"
    ok(harness, "decision", {"decision": "pause"})
    assert ok(harness, "status")["paused"]
    assert ok(harness, "item", {"language": "en"})["kind"] == "paused"
    ok(harness, "resume")
    assert not ok(harness, "status")["paused"]
    assert ok(harness, "item", {"language": "en"})["kind"] == "question"
    trace = ok(harness, "mastery")
    assert trace["points"][-1]["answered"] == 20


def test_all_three_periods_without_repeat_or_cross_participant_leak(harness):
    # F1 maps to one synthetic sequence; no policy assignment is exposed.
    for period in range(3):
        for form in ("pretest", "practice", "posttest"):
            for i in range({"pretest":16,"practice":55,"posttest":16}[form]):
                synthetic_question(harness, form, i, period=period)
        mastery = ok(harness, "mastery")
        assert mastery["independent_scores"]["pretest"] == 16
        assert mastery["independent_scores"]["posttest"] == 16
        assert len(mastery["points"]) == 88
        assert ok(harness, "item", {"language":"en"})["kind"] == "period_complete"
        outcome = ok(harness, "finish")
        assert outcome["periods_finished"] == period + 1
        assert ok(harness, "status")["counts"] == {
            "pretest":16,"practice":55,"posttest":16
        }
        if period < 2:
            assert ok(harness, "item", {"language":"fr"})["kind"] == "between_periods"
            ok(harness, "start-next")
        else:
            assert ok(harness, "item", {"language":"en"})["kind"] == "finished"
    # F2 has not answered anything; the cohort shares no scored state.
    other = post(harness, "status", {"fixture": "F2"})
    assert other.json["counts"] == {"pretest": 0, "practice": 0, "posttest": 0}
    assert ok(harness, "status")["finished"]


def test_no_script_inline_or_unprotected_browser_asset(harness):
    runtime, client, nonce = harness
    home = client.get("/", base_url=f"http://127.0.0.1:{PORT}").get_data(as_text=True)
    assert '<script src="/research-v2.js" defer></script>' in home
    assert "<script>" not in home and "onclick=" not in home
    for asset in ("/research-v2.js","/research-v2.css"):
        r = client.get(asset,base_url=f"http://127.0.0.1:{PORT}")
        assert r.status_code==200 and r.headers["Cache-Control"]=="no-store"
    assert "fetch(" in client.get("/research-v2.js",
        base_url=f"http://127.0.0.1:{PORT}").get_data(as_text=True)
