"""HTTP integration: actual Group A recovery using a fictional-only quick fixture."""
from pathlib import Path
import re

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
        if expected in ("DROP_2", "SOCRATIC_HINT"):
            answer = runtime.store.bank.get(item["question_id"], form="practice")
            if expected == "DROP_2":
                assert len(item["options"]) == 2
                assert answer.correct_answer in item["options"]
            choice = answer.correct_answer
            question_id = item["question_id"]
        else:
            choice = question_id = None
        submitted = post("answer", {
            "question_id": question_id,
            "choice": choice,
            "request_id": f"quick_demo_{step_index:02d}",
        })
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
            "SELECT action_type,block_index FROM events WHERE learner_id=? "
            "AND phase='QUIZ' ORDER BY event_id", (ref,)
        ).fetchall()
    assert [r["action_type"] for r in rows] == [
        "QUESTION", "QUESTION", "QUESTION", *actions,
    ]
    assert sum(r["block_index"] is not None for r in rows) == 3


def test_quick_recovery_rejects_non_f1_and_existing_roster(tmp_path):
    _, _, post = client_and_runtime(tmp_path)
    wrong_fixture = post("demo/prime-recovery", fixture="F2")
    assert wrong_fixture.status_code == 409
    assert post("demo/prime-recovery").status_code == 200
    assert post("demo/prime-recovery").status_code == 409
