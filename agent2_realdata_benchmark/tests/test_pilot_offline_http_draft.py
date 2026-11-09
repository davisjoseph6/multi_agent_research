"""In-process HTTP contract tests. No network listener or participant data."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid

import pytest

from src.prototype.pilot_offline_http_draft import create_offline_test_client
from src.prototype.pilot_three_arm_store_draft import SyntheticThreeArmPilotStore
from src.prototype.study_v2 import RECOVERY_ACTIONS

ROOT = Path(__file__).resolve().parents[1] / "docs/rct_candidate_v1"
ITEMS = ROOT / "items.csv"
RESOURCES = ROOT / "resources.csv"
T0 = datetime(2026, 11, 20, 9, tzinfo=timezone.utc)
AUTH = dict(offline_staff_authorized=True, synthetic_release_authorized=True)


def engine(db):
    return SyntheticThreeArmPilotStore(
        db, items_path=ITEMS, resources_path=RESOURCES, simulations=41,
    )


def post(client, endpoint, payload, expected=200):
    response = client.post("/_offline/" + endpoint, json=payload)
    assert response.status_code == expected, (response.status_code, response.get_json())
    return response.get_json()


def one(client, pid, at):
    clock = at.isoformat()
    action = post(client, "next", dict(pid=pid, at=clock))
    assert action == post(client, "next", dict(pid=pid, at=clock))
    assert action["synthetic_only"]
    assert "answer_id" not in action.get("question", {})
    assert post(client, "rendered", dict(
        pid=pid, action_id=action["action_id"], at=clock
    ))["accepted"]
    kind = action["action"]
    if kind in ("QUESTION", "DROP_2"):
        payload = dict(choice_id=action["question"]["options"][0][0])
    elif kind == "MVAS":
        assert action["instrument_proposed_version"].startswith("MVAS_")
        payload = dict(rating=33 if action["stage"] == "mvas_post" else 12)
    else:
        assert kind in RECOVERY_ACTIONS
        assert action["resource"]["text"]
        payload = dict(status="completed")
    submission = dict(pid=pid, at=clock, action_id=action["action_id"],
                      request_id=uuid.uuid4().hex, response=payload)
    result = post(client, "act", submission)
    assert result["accepted"] and not result["replayed"]
    assert post(client, "act", submission)["replayed"]
    return action


def test_no_human_enrollment_or_network_or_app_factory(tmp_path):
    with pytest.raises(TypeError):
        create_offline_test_client(object())
    store = engine(tmp_path / "synthetic.sqlite3")
    client = create_offline_test_client(store)
    health = client.get("/_offline/health")
    assert health.status_code == 200
    assert health.json == dict(
        synthetic_only=True, human_enrollment_authorized=False,
        http_test_client_only=True
    )
    assert health.headers["X-Synthetic-Only"] == "1"
    assert health.headers["Cache-Control"] == "no-store"
    assert client.post("/api/rct/enroll", json={}).status_code == 404
    assert client.post("/_offline/enroll", json={}).status_code == 404
    assert client.post("/_offline/start", json={}).status_code == 404
    assert client.get("/").status_code == 404
    assert client.get("/_offline/next").status_code == 405


def test_reject_browser_cross_origin_and_nonlocal_clients(tmp_path):
    client = create_offline_test_client(engine(tmp_path / "synthetic.sqlite3"))
    assert client.get("/_offline/health", headers={
        "Origin": "https://example.org"
    }).status_code == 403
    assert client.get("/_offline/health", headers={
        "Host": "demo.selfhealing-edu.fr"
    }).status_code == 403
    assert client.get("/_offline/health", environ_overrides={
        "REMOTE_ADDR": "192.0.2.12"
    }).status_code == 403


def test_http_schema_and_cross_participant_rejection(tmp_path):
    store = engine(tmp_path / "synthetic.sqlite3")
    client = create_offline_test_client(store)
    a = store.new_synthetic_participant(arm="A", at=T0)
    b = store.new_synthetic_participant(arm="B", at=T0)
    store.start_supervised_visit(a, visit=1, at=T0, **AUTH)
    t = T0.isoformat()
    assert post(client, "next", dict(pid=a, at=t, extra=True), 409)["error"]
    assert post(client, "next", dict(pid="REAL_PERSON", at=t), 409)["error"]
    assert post(client, "next", dict(pid=a, at="not-a-date"), 409)["error"]
    action = post(client, "next", dict(pid=a, at=t))
    assert post(client, "rendered", dict(
        pid=b, action_id=action["action_id"], at=t
    ), 409)["error"]
    assert post(client, "act", dict(
        pid=a, action_id=action["action_id"], at=t,
        request_id="r", response=dict(choice_id="A")
    ), 409)["error"]
    assert post(client, "rendered", dict(
        pid=a, action_id=action["action_id"], at=t
    ))["accepted"]
    assert post(client, "act", dict(
        pid=a, action_id=action["action_id"], at=t,
        request_id="invalid", response=dict(choice_id="Z")
    ), 409)["error"]
    assert post(client, "next", dict(pid=a, at=t)) == action


def test_http_mvas_rejects_invalid_response_and_keeps_pending(tmp_path):
    store = engine(tmp_path / "synthetic.sqlite3")
    client = create_offline_test_client(store)
    pid = store.new_synthetic_participant(arm="C", at=T0)
    store.start_supervised_visit(pid, visit=1, at=T0, **AUTH)
    for index in range(16):
        one(client, pid, T0 + timedelta(seconds=index+1))
    when = (T0 + timedelta(seconds=17)).isoformat()
    action = post(client, "next", dict(pid=pid, at=when))
    assert action["action"] == "MVAS"
    post(client, "rendered", dict(pid=pid, action_id=action["action_id"], at=when))
    for invalid in (-1, 101, True, 3.5, "25", None):
        response = client.post("/_offline/act", json=dict(
            pid=pid, action_id=action["action_id"],
            request_id=uuid.uuid4().hex, response=dict(rating=invalid), at=when
        ))
        assert response.status_code in (409, 422)
        assert post(client, "next", dict(pid=pid, at=when)) == action
    assert post(client, "act", dict(
        pid=pid, action_id=action["action_id"],
        request_id="valid", response=dict(rating=0), at=when
    ))["stage"] == "practice"
    assert store.snapshot(pid)["ratings"][0][0] == 0


def test_all_three_arms_complete_through_in_process_http(tmp_path):
    store = engine(tmp_path / "synthetic.sqlite3")
    client = create_offline_test_client(store)
    by_arm = {}
    for arm in "ABC":
        pid = store.new_synthetic_participant(arm=arm, at=T0)
        done = Counter()
        for visit in (1, 2, 3):
            start = T0 + timedelta(days=4*(visit-1))
            store.start_supervised_visit(pid, visit=visit, at=start, **AUTH)
            tick = start + timedelta(seconds=1)
            if visit == 1:
                for _ in range(16):
                    a = one(client, pid, tick)
                    assert a["stage"] == "pretest"
                    tick += timedelta(seconds=1)
            a = one(client, pid, tick)
            assert a["action"] == "MVAS" and a["stage"] == "mvas_pre"
            tick += timedelta(seconds=1)
            within = Counter()
            for _ in range(30):
                if store.snapshot(pid)["stage"] != "practice":
                    break
                a = one(client, pid, tick)
                assert a["stage"] == "practice"
                within[a["action"]] += 1
                done[a["action"]] += 1
                tick += timedelta(seconds=1)
            else:
                raise AssertionError("practice stage failed to terminate")
            assert within["QUESTION"] == (15 if visit == 3 else 20)
            assert sum(within[action] for action in RECOVERY_ACTIONS) <= 2
            a = one(client, pid, tick)
            assert a["action"] == "MVAS" and a["stage"] == "mvas_post"
            tick += timedelta(seconds=1)
            if visit == 3:
                for _ in range(16):
                    a = one(client, pid, tick)
                    assert a["stage"] == "posttest"
                    tick += timedelta(seconds=1)
        assert post(client, "next", dict(
            pid=pid, at=(T0+timedelta(days=9)).isoformat()
        ))["action"] == "COMPLETE"
        final = store.snapshot(pid)
        assert final["stage"] == "complete"
        assert final["fatigue_deltas"] == (21, 21, 21)
        assert final["unique_practice_used"] == 55
        assert store.scores(pid)["pretest"]["answered"] == 16
        assert store.scores(pid)["posttest"]["answered"] == 16
        assert store.scores(pid)["practice"]["answered"] == 55
        by_arm[arm] = done
    assert by_arm["A"]["QUESTION"] == by_arm["B"]["QUESTION"] == by_arm["C"]["QUESTION"] == 55
    for arm in "BC":
        assert all(by_arm[arm][action] == 0 for action in RECOVERY_ACTIONS)
    assert store.audit_arms()["allocated"] == {"A": 1, "B": 1, "C": 1}
