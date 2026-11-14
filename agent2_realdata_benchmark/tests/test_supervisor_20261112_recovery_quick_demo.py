"""HTTP integration: actual Group A recovery using a fictional-only quick fixture."""
from pathlib import Path
import json
import re

from src.prototype.supervisor_recovery_content import (
    CONTENT_VERSION, REVIEW_STATUS, recovery_resource,
)

from scripts.supervisor_fictional_browser import new_supervisor_fictional_runtime
from src.prototype.supervisor_fictional_web import make_supervisor_fictional_app


PORT = 8783
BASE = f"http://127.0.0.1:{PORT}"


def client_and_runtime(tmp_path):
    runtime = new_supervisor_fictional_runtime(tmp_path)
    app = make_supervisor_fictional_app(runtime, port=PORT)
    client = app.test_client()
    home = client.get("/", base_url=BASE).get_data(as_text=True)
    nonce = re.search(r'data-preview-nonce="([^"]+)"', home).group(1)
    assert 'id="quick-recovery"' in home
    def post(route, data=None, fixture="F1"):
        return client.post(
            "/supervisor/api/" + route,
            json={"fixture": fixture, **(data or {})},
            headers={"X-Preview-Nonce": nonce, "Origin": BASE},
            base_url=BASE,
        )
    return runtime, client, post


def test_one_click_primes_actual_four_stage_recovery(tmp_path):
    runtime, _, post = client_and_runtime(tmp_path)
    prepared = post("demo/prime-recovery")
    assert prepared.status_code == 200, prepared.json
    assert prepared.json["group"] == "A"
    assert prepared.json["regular_questions_answered"] == 3
    assert prepared.json["next_action"] == "CONCEPT_SUMMARY"
    assert post("status").json["phase"] == "QUIZ"

    actions = []
    for step_index, expected in enumerate(
        ("CONCEPT_SUMMARY", "DROP_2", "WORKED_EXAMPLE", "SOCRATIC_HINT")
    ):
        current = post("item")
        assert current.status_code == 200, current.json
        item = current.json
        assert item["kind"] == "recovery" and item["action"] == expected
        actions.append(expected)
        if expected in ("CONCEPT_SUMMARY", "WORKED_EXAMPLE"):
            resource=item["resource"]
            assert len(resource["paragraphs"])>=2
            assert all(len(p)>75 for p in resource["paragraphs"])
            assert resource["review_status"]==REVIEW_STATUS
        if expected == "SOCRATIC_HINT":
            resource=item["resource"]
            assert len(resource["prompts"])==2
            assert all(len(p)>30 for p in resource["prompts"])
            assert resource["original_question"]==item["question_text"]
            assert "correct_answer" not in str(item)
        if expected in ("DROP_2", "SOCRATIC_HINT"):
            answer = runtime.store.bank.get(item["question_id"], form="practice")
            if expected == "DROP_2":
                assert len(item["options"]) == 2
                assert answer.correct_answer in item["options"]
            choice = answer.correct_answer
            question_id = item["question_id"]
        else:
            choice = question_id = None
        payload = {
            "question_id": question_id,
            "choice": choice,
            "request_id": f"quick_demo_{step_index:02d}",
        }
        if expected == "SOCRATIC_HINT":
            payload["reflection"] = [
                "Identify the concept and its reference point.",
                "Compare the candidate answers against that concept.",
            ]
        submitted = post("answer", payload)
        assert submitted.status_code == 200, submitted.json

    assert actions == [
        "CONCEPT_SUMMARY", "DROP_2", "WORKED_EXAMPLE", "SOCRATIC_HINT"
    ]
    nxt = post("item").json
    assert nxt["kind"] == "question"
    assert nxt["question_id"] == "QZ_C5_L1_01"

    ref, token = runtime.roster["F1"]
    with runtime.store._tx() as db:
        rows = db.execute(
            "SELECT action_type,block_index,content_id,free_text FROM events WHERE learner_id=? "
            "AND phase='QUIZ' ORDER BY event_id", (ref,)
        ).fetchall()
    assert [r["action_type"] for r in rows] == [
        "QUESTION", "QUESTION", "QUESTION", *actions,
    ]
    assert sum(r["block_index"] is not None for r in rows) == 3
    for r in rows[3:]:
        if r["action_type"]!="DROP_2":
            assert r["content_id"].startswith(CONTENT_VERSION)
    assert json.loads(rows[-1]["free_text"]) == [
        "Identify the concept and its reference point.",
        "Compare the candidate answers against that concept.",
    ]


def test_quick_recovery_rejects_non_f1_and_existing_roster(tmp_path):
    _, _, post = client_and_runtime(tmp_path)
    wrong_fixture = post("demo/prime-recovery", fixture="F2")
    assert wrong_fixture.status_code == 409
    assert post("demo/prime-recovery").status_code == 200
    assert post("demo/prime-recovery").status_code == 409


def test_all_eight_concepts_have_visible_draft_teaching_resources():
    for i in range(1,9):
        concept=f"C{i}"
        for action in ("CONCEPT_SUMMARY","WORKED_EXAMPLE"):
            text=recovery_resource(concept,action)
            assert text["content_id"]==f"{CONTENT_VERSION}_{concept}_{action}"
            assert text["review_status"]==REVIEW_STATUS
            assert len(text["paragraphs"])==2
            assert all(len(p)>75 for p in text["paragraphs"])
        hints=recovery_resource(
            concept,"SOCRATIC_HINT",
            question_text="A concept-specific failed practice question?",
        )
        assert len(hints["prompts"])==2
        assert all(hints["prompts"])
        assert "correct_answer" not in hints


def test_staged_browser_controls_and_no_placeholder_display(tmp_path):
    runtime,client,post=client_and_runtime(tmp_path)
    html=client.get("/",base_url=BASE).get_data(as_text=True)
    js=client.get("/supervisor-fake.js",base_url=BASE).get_data(as_text=True)
    for marker in ('id="recovery-content"','id="hint-guidance"',
                   'id="hint-reflection"','id="hint-next"'):
        assert marker in html
    assert "function showSocraticPrompt()" in js
    assert 'item.action==="SOCRATIC_HINT"' in js
    assert 'data.reflection=hintResponses.slice()' in js
    assert 'synthetic teaching resource; text requires academic review.' not in js


def test_staged_browser_refuses_unhinted_and_invalid_socratic_answers(tmp_path):
    runtime,_,post=client_and_runtime(tmp_path)
    assert post("demo/prime-recovery").status_code==200
    for i in range(3):
        item=post("item").json
        action=item["action"]
        if action=="DROP_2":
            question=runtime.store.bank.get(item["question_id"],form="practice")
            qid=item["question_id"]
            choice=question.correct_answer
        else:
            qid=choice=None
        answer=post("answer",{
            "question_id":qid,"choice":choice,
            "request_id":f"staged_skip_{i:02d}",
        })
        assert answer.status_code==200,answer.json
    current=post("item").json
    assert current["action"]=="SOCRATIC_HINT"
    qid=current["question_id"]
    correct=runtime.store.bank.get(qid,form="practice").correct_answer
    base={"question_id":qid,"choice":correct,
          "request_id":"staged_unhinted_rejected"}
    assert post("answer",base).status_code==409
    assert post("answer",{**base,"reflection":["one prompt only"]}).status_code==409
    assert post("answer",{**base,"reflection":["","valid"]}).status_code==409
    accepted=post("answer",{**base,"reflection":[
        "The first part makes me think about the decision-maker's reference point.",
        "The second prompt asks me to compare losses with corresponding gains.",
    ]})
    assert accepted.status_code==200,accepted.json
    with runtime.store._tx() as db:
        event=db.execute(
            "SELECT action_type,free_text,content_id FROM events "
            "WHERE action_type='SOCRATIC_HINT' ORDER BY event_id DESC LIMIT 1"
        ).fetchone()
    assert event["action_type"]=="SOCRATIC_HINT"
    assert len(json.loads(event["free_text"]))==2
    assert event["content_id"].startswith(CONTENT_VERSION)
