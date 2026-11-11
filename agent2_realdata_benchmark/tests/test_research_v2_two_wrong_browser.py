"""End-to-end mandatory two-wrong recovery, consent-free FICTIONAL only.

Versioned and isolated. No exposed real participants, SMTP, TLS or 8767 changes.
"""
from datetime import timedelta
from pathlib import Path
import json
import re
import uuid

import pytest

from scripts.pilot_unified_fictional_browser import open_synthetic_study
from src.prototype.pilot_session_flow_draft import PilotSequenceError
from src.prototype.pilot_unified_fictional_browser import (
    SYNTHETIC_EPOCH, create_unified_fictional_browser_app,
)
from src.prototype.study_v2 import RECOVERY_ACTIONS


def _setup(tmp_path, mandatory=True):
    db = tmp_path / "fictional_admission.sqlite3"
    study, roster, operator, clock = open_synthetic_study(
        db, question_anchored_recovery=mandatory,
        mandatory_two_wrong_recovery=mandatory,
    )
    fixture = next(
        f for f, pid in roster.items()
        if study.operator_lookup(operator, pid)[1] == "A"
    )
    learner, _arm = study.operator_lookup(operator, roster[fixture])
    return study, roster, operator, fixture, learner


def _send(study, learner, response, moment):
    action = study.learning.next_action(learner, at=moment)
    assert action == study.learning.next_action(learner, at=moment)
    assert "arm" not in action
    assert study.learning.mark_rendered(
        learner, action["action_id"], at=moment,
    )["accepted"]
    rid = uuid.uuid4().hex
    result = study.learning.submit(
        learner, action["action_id"], rid, response, at=moment,
    )
    assert result["accepted"] and not result["replayed"]
    assert study.learning.submit(
        learner, action["action_id"], rid, response, at=moment,
    )["replayed"]
    return action, result


def _pretest(study, learner):
    t = SYNTHETIC_EPOCH + timedelta(minutes=1)
    for _ in range(16):
        question = study.learning.next_action(learner, at=t)
        assert question["stage"] == "pretest"
        _send(study, learner, {
            "choice_id": question["question"]["options"][0][0],
        }, t)
        t += timedelta(minutes=1)
    action, result = _send(study, learner, {"rating": 30}, t)
    assert action["action"] == "MVAS" and action["stage"] == "mvas_pre"
    return t + timedelta(minutes=1)


def _wrong(study, learner, t):
    q = study.learning.next_action(learner, at=t)
    assert q["action"] == "QUESTION" and q["stage"] == "practice"
    item = study.learning.policy_bank.by_id[q["question"]["item_id"]]
    wrong = next(k for k, _ in item.options if k != item.answer_id)
    result = _send(study, learner, {"choice_id": wrong}, t)[1]
    assert result["correct"] is False
    return q, item, wrong


def test_two_wrong_immediately_precedes_recovery_and_consent_to_continue(tmp_path):
    study, roster, operator, fixture, learner = _setup(tmp_path)
    t = _pretest(study, learner)
    _wrong(study, learner, t)
    t += timedelta(minutes=1)
    after_first = study.learning.next_action(learner, at=t)
    assert after_first["action"] == "QUESTION"  # no early intervention
    _wrong(study, learner, t)
    t += timedelta(minutes=1)
    next_one = study.learning.next_action(learner, at=t)
    assert next_one["action"] == "CONCEPT_SUMMARY"
    assert next_one["resource"]["question_anchor"]["source"] == (
        "MOST_RECENT_INCORRECT_PRACTICE_THIS_VISIT"
    )
    assert next_one["stage"] == "practice"
    _send(study, learner, {"status": "completed"}, t)
    assert study.learning.snapshot(learner)["recovery_completed"] == 1
    assert study.learning.next_action(learner, at=t)["action"] == "CONTINUE_OR_PAUSE"
    choice = study.learning.choose_after_forced_recovery(
        learner, decision="pause", at=t,
    )
    assert choice["paused"]
    assert study.learning.next_action(learner, at=t)["action"] == "PAUSED"
    study.learning.choose_after_forced_recovery(
        learner, decision="resume", at=t,
    )
    assert study.learning.next_action(learner, at=t)["action"] == "QUESTION"
    with pytest.raises(PilotSequenceError):
        study.learning.choose_after_forced_recovery(
            learner, decision="resume", at=t,
        )


def test_all_twenty_wrong_trigger_ten_interventions_including_before_post_fatigue(tmp_path):
    study, roster, operator, fixture, learner = _setup(tmp_path)
    t = _pretest(study, learner)
    received = []
    final_before_mvas = None
    last_wrong_option = None
    for qnumber in range(20):
        question, original, wrong = _wrong(study, learner, t)
        t += timedelta(minutes=1)
        last_wrong_option = wrong
        if qnumber % 2:
            intervention = study.learning.next_action(learner, at=t)
            assert intervention["action"] in RECOVERY_ACTIONS
            assert intervention["action"] == RECOVERY_ACTIONS[len(received) % 4]
            assert intervention["resource"]["question_anchor"]["target_item_id"] == (
                question["question"]["item_id"]
            )
            assert intervention["resource"]["question_anchor"][
                "prior_selected_option"
            ]["id"] == wrong
            if qnumber == 19:
                assert intervention["stage"] == "mvas_post"
                final_before_mvas = intervention
            if intervention["action"] == "DROP_2":
                assert intervention["question"]["item_id"] == original.item_id
                choices = {key for key, _ in intervention["question"]["options"]}
                assert choices == {original.answer_id, wrong}
                response = {"choice_id": original.answer_id}
            else:
                response = {"status": "completed"}
            _send(study, learner, response, t)
            received.append(intervention["action"])
            assert study.learning.next_action(learner, at=t)["action"] == "CONTINUE_OR_PAUSE"
            study.learning.choose_after_forced_recovery(
                learner, decision="continue", at=t,
            )
            t += timedelta(minutes=1)
    assert len(received) == 10
    assert final_before_mvas is not None
    assert study.learning.snapshot(learner)["recovery_completed"] == 10
    next_action = study.learning.next_action(learner, at=t)
    assert next_action["action"] == "MVAS"
    assert next_action["stage"] == "mvas_post"
    _send(study, learner, {"rating": 40}, t)
    assert study.learning.snapshot(learner)["stage"] == "awaiting_visit"


def test_second_wrong_rule_does_not_change_other_arms(tmp_path):
    study, roster, operator, fixture, learner = _setup(tmp_path)
    for f, pid in roster.items():
        other, arm = study.operator_lookup(operator, pid)
        if arm in ("B", "C"):
            state = study.learning.snapshot(other)
            assert state["stage"] == "pretest"
            assert state["recovery_offered"] == 0


def test_private_http_serve_mastery_curve_and_continue_choices(tmp_path):
    study, roster, operator, fixture, learner = _setup(tmp_path)
    t = _pretest(study, learner)
    _wrong(study, learner, t)
    t += timedelta(minutes=1)
    _wrong(study, learner, t)
    t += timedelta(minutes=1)
    intervention = study.learning.next_action(learner, at=t)
    _send(study, learner, {"status": "completed"}, t)
    app = create_unified_fictional_browser_app(
        study, operator, roster, port=8769,
    )
    base = "http://127.0.0.1:8769"
    client = app.test_client()
    html = client.get("/", base_url=base).get_data(as_text=True)
    nonce = re.search(
        r'<meta name="preview-nonce" content="([^"]+)">',
        html,
    ).group(1)
    headers = {"Origin": base, "X-Preview-Nonce": nonce}

    def post(route, data):
        result = client.post(
            "/unified/api/" + route, json=data,
            headers=headers, base_url=base,
        )
        assert result.status_code == 200, result.get_data(as_text=True)
        return result.get_json()

    trace = post("mastery", {"fixture": fixture})
    assert trace["synthetic_only"]
    assert trace["fixture"] == fixture
    assert trace["independent_scores"]["pretest"] is not None
    assert trace["independent_scores"]["posttest"] is None
    assert len(trace["concepts"]) == 8
    assert len(trace["points"]) == 19  # 16 pretest + 2 practice + baseline
    assert trace["points"][-1]["answered"] == 18
    assert "answer_id" not in json.dumps(trace)
    prompt = post("next", {"fixture": fixture})
    assert prompt["action"] == "CONTINUE_OR_PAUSE"
    assert post("continue", {
        "fixture": fixture, "decision": "pause",
    })["paused"]
    assert post("next", {"fixture": fixture})["action"] == "PAUSED"
    assert not post("continue", {
        "fixture": fixture, "decision": "resume",
    })["paused"]


def test_mandatory_mode_cannot_be_enabled_without_anchored_source(tmp_path):
    from src.prototype.pilot_three_arm_store_draft import SyntheticThreeArmPilotStore
    root = Path(__file__).resolve().parents[1] / "docs/rct_candidate_v1"
    with pytest.raises(ValueError, match="requires question-anchored"):
        SyntheticThreeArmPilotStore(
            tmp_path / "invalid.sqlite3",
            items_path=root / "items.csv",
            resources_path=root / "resources.csv",
            simulations=41,
            question_anchored_recovery=False,
            mandatory_two_wrong_recovery=True,
        )
