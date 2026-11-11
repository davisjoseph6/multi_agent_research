"""End-to-end opt-in fictional browser: source-bound incorrect-question help."""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import re
import uuid

import pytest

from scripts.pilot_unified_fictional_browser import open_synthetic_study
from src.prototype.pilot_unified_fictional_browser import (
    SYNTHETIC_EPOCH, create_unified_fictional_browser_app,
)
from src.prototype.pilot_session_flow_draft import PilotSequenceError


BASE = "http://127.0.0.1:8769"


def _post(client, nonce, path, payload):
    response = client.post(
        "/unified/api/" + path, json=payload, base_url=BASE,
        headers={"Origin": BASE, "X-Preview-Nonce": nonce},
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


@pytest.mark.parametrize("kind", [
    "SOCRATIC_HINT", "CONCEPT_SUMMARY", "WORKED_EXAMPLE", "DROP_2",
])
def test_candidate_recovers_latest_wrong_question_over_http(tmp_path, monkeypatch, kind):
    study, roster, operator, clock = open_synthetic_study(
        tmp_path / "fictional_admission.sqlite3",
        question_anchored_recovery=True,
    )
    fixture = next(
        f for f, pid in roster.items()
        if study.operator_lookup(operator, pid)[1] == "A"
    )
    learner, _ = study.operator_lookup(operator, roster[fixture])
    now = SYNTHETIC_EPOCH + timedelta(minutes=1)
    for _ in range(16):
        a = study.learning.next_action(learner, at=now)
        study.learning.mark_rendered(learner, a["action_id"], at=now)
        study.learning.submit(
            learner, a["action_id"], uuid.uuid4().hex,
            {"choice_id": a["question"]["options"][0][0]}, at=now,
        )
        now += timedelta(minutes=1)
    a = study.learning.next_action(learner, at=now)
    assert a["action"] == "MVAS"
    study.learning.mark_rendered(learner, a["action_id"], at=now)
    study.learning.submit(
        learner, a["action_id"], uuid.uuid4().hex,
        {"rating": 30}, at=now,
    )
    now += timedelta(minutes=1)
    a = study.learning.next_action(learner, at=now)
    assert a["action"] == "QUESTION" and a["stage"] == "practice"
    item = study.learning.policy_bank.by_id[a["question"]["item_id"]]
    wrong = next(x for x, _ in item.options if x != item.answer_id)
    study.learning.mark_rendered(learner, a["action_id"], at=now)
    assert not study.learning.submit(
        learner, a["action_id"], uuid.uuid4().hex,
        {"choice_id": wrong}, at=now,
    )["correct"]
    now += timedelta(minutes=1)

    def selected(state):
        assert state["last_incorrect_concept"] == item.concept
        return {"action": kind, "concept": item.concept, "item_id": None}
    monkeypatch.setattr(study.learning.selector, "_candidate", selected)

    app = create_unified_fictional_browser_app(
        study, operator, roster, port=8769,
    )
    client = app.test_client()
    html = client.get("/", base_url=BASE).get_data(as_text=True)
    nonce = re.search(
        r'<meta name="preview-nonce" content="([^"]+)">',
        html,
    ).group(1)
    recovered = _post(client, nonce, "next", {"fixture": fixture})
    assert recovered["action"] == kind
    assert recovered["resource"]["question_anchor"]["target_item_id"] == item.item_id
    assert recovered["resource"]["question_anchor"]["prior_selected_option"]["id"] == wrong
    assert recovered["resource"]["question_anchor"]["target_question"] == item.prompt
    assert not recovered["resource"]["question_anchor"]["content_independently_reviewed"]
    assert "answer_id" not in recovered["resource"]
    assert _post(client, nonce, "next", {"fixture": fixture}) == recovered
    if kind == "DROP_2":
        assert len(recovered["question"]["options"]) == 2
        assert {x for x, _ in recovered["question"]["options"]} == {wrong, item.answer_id}
    frontend = (
        Path(__file__).resolve().parents[1]
        / "src/prototype/static/pilot_unified_fictional_browser.js"
    ).read_text(encoding="utf-8")
    assert "resource.question_anchor" in frontend
    assert "anchor.target_question" in frontend
    assert "anchor.prior_selected_option.text" in frontend
    assert ".textContent" in frontend


def test_original_browser_mode_not_opted_in(tmp_path):
    study, roster, operator, clock = open_synthetic_study(
        tmp_path / "fictional_admission.sqlite3",
    )
    assert study.learning.question_anchored_recovery is False
    assert len(roster) == 3
