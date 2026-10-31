"""Tests use fictional invitations and draft content, never real approvals."""
import csv
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from scripts.rct_candidate_cli import DEFAULT_SETTINGS, load_settings, smoke
from src.prototype.rct_candidate import RCTCandidateEngine, policy_record
from src.prototype.rct_candidate_api import create_app
from src.prototype.rct_candidate_content import ContentBundle, release_report, canonical
from src.prototype.study_v2_runtime import ProtocolError
from src.prototype.study_v3_pomcp import EightConceptPOMCP
from src.prototype.study_v3_runtime import SyntheticPOMCPProtocolEngine


@pytest.fixture
def bundle():
    return load_settings(DEFAULT_SETTINGS)[1]


@pytest.fixture
def engine(tmp_path, bundle):
    return RCTCandidateEngine(tmp_path / "candidate.db", bundle, simulations=64)


def enrolled(engine):
    item = engine.issue_invitation()
    token = item["invitation"]
    engine.enroll(token, agreed=True, information_version=engine.bundle.hashes["information"])
    return item


def answer(engine, token, action, request_id="answer"):
    engine.rendered(token, action["action_id"])
    if "question" in action:
        response = {"choice_id": action["question"]["options"][0][0]}
    elif action["action"] == "FATIGUE":
        response = {"values": [3] * 6}
    else:
        response = {"status": "completed"}
    return engine.act(token, request_id, action["action_id"], response), response


def test_content_counts_and_actual_pending_reviews(bundle):
    assert len(bundle.items) == 95 and len(bundle.resources) == 32
    assert bundle.unreviewed_items == 95 and bundle.unreviewed_resources == 32
    assert not bundle.fatigue_reviewed


def test_draft_cannot_start_live(tmp_path, bundle):
    with pytest.raises(ProtocolError, match="Live enrollment blocked"):
        RCTCandidateEngine(tmp_path / "live.db", bundle, mode="live")
    assert not (tmp_path / "live.db").exists()


def test_missing_evidence_never_becomes_approval(bundle):
    report = release_report(bundle, policy_record())
    assert not report["mechanical_gate_passed"]
    assert len(report["blockers"]) >= 10


@pytest.mark.parametrize("value", [0, 1, 40, True, 3.0, 100001])
def test_planner_simulation_budget_validation(value):
    with pytest.raises(ValueError):
        policy_record(value)


def test_invitation_required_and_consent_version_bound(engine):
    token = engine.issue_invitation()["invitation"]
    with pytest.raises(ProtocolError, match="agreement required"):
        engine.next_action(token)
    with pytest.raises(ProtocolError):
        engine.enroll(token, agreed=True, information_version="old")
    with pytest.raises(ProtocolError):
        engine.enroll(token, agreed=1, information_version=engine.bundle.hashes["information"])
    with sqlite3.connect(engine.path) as db:
        assert db.execute("SELECT COUNT(*) FROM rct_allocation").fetchone()[0] == 0


def test_server_assignment_concurrent_and_repeated(engine):
    invitation = engine.issue_invitation()
    kwargs = dict(agreed=True, information_version=engine.bundle.hashes["information"])
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: engine.enroll(invitation["invitation"], **kwargs), range(4)))
    assert sum(r["created"] for r in results) == 1
    with sqlite3.connect(engine.path) as db:
        assert db.execute("SELECT COUNT(*) FROM rct_allocation WHERE pid IS NOT NULL").fetchone()[0] == 1


def test_concurrent_distinct_people_and_block_integrity(engine):
    invitations = [engine.issue_invitation() for _ in range(20)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda inv: engine.enroll(inv["invitation"], agreed=True,
                      information_version=engine.bundle.hashes["information"]), invitations))
    with sqlite3.connect(engine.path) as db:
        rows = db.execute("SELECT block,arm,pid FROM rct_allocation").fetchall()
    for block in {r[0] for r in rows}:
        counts = Counter(r[1] for r in rows if r[0] == block)
        assert counts["A"] == counts["B"] == counts["C"]
        assert counts["A"] in (2, 3)
    assert len({r[2] for r in rows if r[2]}) == 20


def test_pending_survives_restart_and_backup(engine, bundle, tmp_path):
    token = enrolled(engine)["invitation"]
    action = engine.next_action(token)
    restarted = RCTCandidateEngine(engine.path, bundle, simulations=64)
    assert restarted.next_action(token) == action
    target = tmp_path / "copy.db"
    engine.backup(target)
    copy = RCTCandidateEngine(target, bundle, simulations=64)
    assert copy.next_action(token) == action
    with pytest.raises(FileExistsError):
        engine.backup(target)


def test_exactly_once_concurrent_and_conflicting_payload(engine):
    token = enrolled(engine)["invitation"]
    action = engine.next_action(token)
    engine.rendered(token, action["action_id"])
    response = {"choice_id": action["question"]["options"][0][0]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: engine.act(token, "retry", action["action_id"], response), range(2)))
    assert sorted(r["replayed"] for r in results) == [False, True]
    different = {"choice_id": action["question"]["options"][1][0]}
    with pytest.raises(ProtocolError, match="reused"):
        engine.act(token, "retry", action["action_id"], different)
    assert engine.next_action(token)["index"] == 1


def test_stale_and_foreign_action_ids_rejected(engine):
    a, b = enrolled(engine)["invitation"], enrolled(engine)["invitation"]
    action = engine.next_action(a)
    engine.next_action(b)
    with pytest.raises(ProtocolError):
        engine.rendered(b, action["action_id"])
    _, response = answer(engine, a, action)
    engine.next_action(a)
    with pytest.raises(ProtocolError, match="stale"):
        engine.act(a, "new_stale_request", action["action_id"], response)


def test_render_required_and_reported_only_once(engine):
    token = enrolled(engine)["invitation"]
    action = engine.next_action(token)
    with pytest.raises(ProtocolError, match="render"):
        engine.act(token, "a", action["action_id"], {"choice_id": "A"})
    engine.rendered(token, action["action_id"])
    engine.rendered(token, action["action_id"])
    rows = engine.export_private()["events"]
    assert sum(r["kind"] == "client_reported_render" for r in rows) == 1


@pytest.mark.parametrize("choice", [None, [], {}, 1, True, "invalid"])
def test_invalid_choice_does_not_advance(engine, choice):
    token = enrolled(engine)["invitation"]
    action = engine.next_action(token)
    engine.rendered(token, action["action_id"])
    with pytest.raises(ProtocolError):
        engine.act(token, "bad", action["action_id"], {"choice_id": choice})
    assert engine.next_action(token) == action


def test_assessment_keys_and_correctness_are_not_public(engine):
    token = enrolled(engine)["invitation"]
    action = engine.next_action(token)
    for secret in ("answer_id", "correct_option_id", "mastery", "planning_trace", "arm"):
        assert secret not in canonical(action)
    result, _ = answer(engine, token, action)
    assert "correct" not in result
    export = engine.export_private()
    assert export["outcomes"][0]["pretest_score"] is None
    assert export["outcomes"][0]["posttest_score"] is None
    assert "token_hash" not in canonical(export) and token not in canonical(export)


@pytest.mark.parametrize("kind", ["CONCEPT_SUMMARY", "DROP_2", "WORKED_EXAMPLE", "SOCRATIC_HINT"])
def test_resource_delivery_payload_answer_and_provenance(engine, kind):
    """Forced-action fixture tests renderer contracts, not planner efficacy."""
    item = enrolled(engine)
    with engine._transaction() as db:
        row = db.execute("SELECT state FROM rct_people WHERE pid=?", (item["participant_id"],)).fetchone()
        state = json.loads(row[0]); state.update(stage="practice", session=1, index=1)
        db.execute("UPDATE rct_people SET state=? WHERE pid=?", (canonical(state), item["participant_id"]))
    concept = engine.bundle.items[0].concept
    drop2 = next(q for q in engine.bank.values() if q.form == "recovery_drop2" and q.concept == concept)
    engine._candidate = lambda s: dict(action=kind, concept=concept, item_id=drop2.item_id if kind == "DROP_2" else None)
    action = engine.next_action(item["invitation"])
    assert action["resource"]["text"] and len(action["resource"]["version_sha256"]) == 64
    if kind == "DROP_2":
        assert len(action["question"]["options"]) == 2
        engine.rendered(item["invitation"], action["action_id"])
        with pytest.raises(ProtocolError):
            engine.act(item["invitation"], "no_answer", action["action_id"], {"status": "completed"})
    answer(engine, item["invitation"], action)
    row = engine.export_private()["actions"][0]
    assert row["offered_at"] and row["rendered_at"] and row["completed_at"]


def test_stop_is_durable_and_does_not_pretend_to_delete(engine):
    token = enrolled(engine)["invitation"]
    engine.next_action(token)
    assert engine.withdraw(token)["stopped"]
    assert engine.withdraw(token)["stopped"]
    with pytest.raises(ProtocolError, match="stopped"):
        engine.next_action(token)
    assert engine.export_private()["outcomes"][0]["status"] == "withdrawn"


def test_expired_token_rejected(engine):
    token = engine.issue_invitation()["invitation"]
    with sqlite3.connect(engine.path) as db:
        db.execute("UPDATE rct_people SET expires=0")
    with pytest.raises(ProtocolError):
        engine.information(token)


def test_staff_credential_rotation_preserves_assignment_and_pending(engine):
    invitation = enrolled(engine)
    action = engine.next_action(invitation["invitation"])
    new = engine.rotate_invitation(invitation["participant_id"])
    with pytest.raises(ProtocolError):
        engine.next_action(invitation["invitation"])
    assert engine.next_action(new["invitation"]) == action
    engine.withdraw(new["invitation"])
    with pytest.raises(ProtocolError):
        engine.rotate_invitation(invitation["participant_id"])


def test_policy_change_and_old_database_rejected(engine, bundle, tmp_path):
    with pytest.raises(ProtocolError, match="changed"):
        RCTCandidateEngine(engine.path, bundle, simulations=65)
    old = tmp_path / "old.db"
    SyntheticPOMCPProtocolEngine(old, bundle.items)
    with pytest.raises(ProtocolError, match="fresh"):
        RCTCandidateEngine(old, bundle)


def test_content_change_freezes_existing_database(engine, tmp_path):
    content = tmp_path / "edited"
    shutil.copytree(DEFAULT_SETTINGS.parent, content)
    path = content / "participant_information_REHEARSAL_ONLY.txt"
    path.write_text(path.read_text() + "\nChanged version\n")
    changed = load_settings(content / "settings_rehearsal.json")[1]
    with pytest.raises(ProtocolError, match="changed"):
        RCTCandidateEngine(engine.path, changed, simulations=64)


def test_api_authorization_host_origin_body_and_arm_protection(engine):
    client = create_app(engine).test_client()
    token = engine.issue_invitation()["invitation"]
    h = {"Authorization": "Bearer " + token}
    assert client.post("/api/rct/next", json={}).status_code == 409
    assert client.post("/api/rct/information", json={}, headers={**h, "Host": "evil.example"}).status_code == 403
    assert client.post("/api/rct/information", json={}, headers={**h, "Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/rct/information", json={}, headers=h, environ_overrides={"REMOTE_ADDR": "192.0.2.1"}).status_code == 403
    data = dict(agreed=True, information_version=engine.bundle.hashes["information"], arm="A")
    assert client.post("/api/rct/enroll", json=data, headers=h).status_code == 409
    del data["arm"]
    assert client.post("/api/rct/enroll", json=data, headers=h).status_code == 200
    assert client.get("/docs/rct_candidate_v1/items.csv").status_code == 404
    page = client.get("/")
    assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]
    assert "LOCAL REHEARSAL" in page.text


@pytest.mark.parametrize("arm", ["A", "B", "C"])
def test_integrated_selector_and_belief_parity_with_existing_v3(engine, bundle, tmp_path, arm):
    """Full journey with identical answers: integration must not silently change V3."""
    item = enrolled(engine)
    with engine._transaction() as db:
        state = json.loads(db.execute("SELECT state FROM rct_people WHERE pid=?", (item["participant_id"],)).fetchone()[0])
        state["arm"] = arm
        db.execute("UPDATE rct_people SET state=? WHERE pid=?", (canonical(state), item["participant_id"]))
    old = SyntheticPOMCPProtocolEngine(tmp_path / "original.db", bundle.items, planner=EightConceptPOMCP(simulations=64))
    old.enroll("SYN_PARITY", arm)
    resource_counts = Counter()
    for k in range(110):
        new_action = engine.next_action(item["invitation"])
        old_action = old.next_action("SYN_PARITY")
        assert new_action["action"] == old_action["action"]
        if new_action["action"] == "COMPLETE":
            break
        assert canonical(new_action.get("question")) == canonical(old_action.get("question"))
        _, response = answer(engine, item["invitation"], new_action, str(k))
        if "question" in new_action:
            old_response = {**response, "item_id": old_action["item_id"]}
        elif new_action["action"] == "FATIGUE":
            old_response = response
        else:
            old_response = {"acknowledged": True}
        old.act("SYN_PARITY", str(k), old_response)
        with old._connect() as db:
            old_state = old._get(db, "SYN_PARITY")
        current = json.loads(engine.export_private()["people"][0]["state"])
        for key in ("stage", "session", "index", "mastery", "used", "recovery"):
            assert current[key] == old_state[key]
        if "resource" in new_action:
            resource_counts[new_action["session"]] += 1
    else:
        pytest.fail("journey did not terminate")
    assert all(c <= 2 for c in resource_counts.values())
    assert engine.export_private()["outcomes"][0]["posttest_answered"] == 16


def test_matched_control_never_delivers_recovery(tmp_path, bundle):
    engine = RCTCandidateEngine(tmp_path / "matched.db", bundle, simulations=64, control="pomcp_no_recovery")
    state = dict(arm="B", stage="practice", session=1, index=1, mastery={q.concept: .2 for q in bundle.items}, used=[], recovery={})
    chosen = engine._candidate(state)
    assert chosen["action"] == "QUESTION"
    assert chosen["control_variant"] == "matched_POMCP_recovery_disabled"
    assert state["recovery"] == {}


def test_complete_nine_person_http_smoke():
    report = smoke(DEFAULT_SETTINGS)
    assert report["software_rehearsal_passed"]
    assert not report["human_enrollment_authorized"]
    assert set(report["arm_counts"]) == {"A", "B", "C"}
    assert report["audit"]["pending_actions"] == 0
