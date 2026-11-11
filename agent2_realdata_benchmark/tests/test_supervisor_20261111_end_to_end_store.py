"""Full synthetic 3-visit/assessment/quiz/survey replay of 7 supervisor cases.

All scored answers go through the server bank grader and SQLite controller.
The controller does not receive expected action/question IDs from the oracle
when selecting. This is not an authorized human enrollment test.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore
from src.prototype.supervisor_trace_engine import CONCEPT_IDS

DATA = Path(__file__).resolve().parents[1] / "data" / "supervisor_20261111"
T0 = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)
INITIAL = {
    1: (.50,.20,.50,.50,.20,.20,.20,.50),
    2: (.75,.50,.75,.50,.75,.50,.20,.75),
    3: (.20,)*8,
    4: (.75,.50,.75,.50,.75,.50,.20,.75),
    5: (.50,.20,.50,.50,.20,.20,.20,.50),
    6: (.50,.20,.50,.50,.20,.20,.20,.50),
    7: (.50,.20,.50,.50,.20,.20,.20,.50),
}


def choose(bank, identifier, expected_correct, form):
    item = bank.get(identifier, form=form)
    if expected_correct:
        return item.correct_answer
    return next(choice for choice in "ABCD" if choice != item.correct_answer)


def replay_case(case: int, directory: Path) -> dict:
    bank = SupervisorBank(DATA)
    store = SupervisorSyntheticStore(directory, bank=bank)
    screening = {x.question_id:choose(
        bank,x.question_id,False,"screening")
        for x in bank.forms["screening"]}
    identity = store.register(
        contact_email=f"case{case}@example.test",
        econ_course=False, screening_answers=screening,
        consent_version="supervisor-synthetic-v1",
        consent_given=True, age=24, program="Fictional student", at=T0,
    )
    ref, token = identity["fictional_learner_id"], identity["fictional_private_token"]
    assert identity["eligible"] and identity["screening_score"] == 0
    for i, q in enumerate(bank.forms["pretest"]):
        prior = INITIAL[case][int(q.concept[1:]) - 1]
        first_or_second = q.level == 2
        right = (prior == .75 or (prior == .50 and first_or_second))
        item = store.next_item(ref, token)
        assert item["question_id"] == q.question_id
        store.answer_assessment(
            ref, token, request_id=f"case{case}_pretest_{i:03d}",
            item_id=q.question_id,
            choice=choose(bank, q.question_id, right, "pretest"),
            shown_at=T0, answered_at=T0,
        )
    with store._tx() as db:
        state = store._state(db, ref)
        assert tuple(state["engine"]["mastery"][c] for c in CONCEPT_IDS) == INITIAL[case]
        assert state["phase"] == "QUIZ"

    with (DATA / "scenario_traces.csv").open(
        newline="", encoding="utf-8-sig"
    ) as f:
        reference = [r for r in csv.DictReader(f) if r["case"] == str(case)]

    events_before = len(store.export_anonymous_events(ref=ref, token=token))
    assert events_before == 24
    cursor = 0
    for session, count in ((1, 20), (2, 20), (3, 15)):
        at = T0 + timedelta(days=4 * (session-1))
        rows = [r for r in reference if int(r["session"]) == session]
        n = 0
        for r in rows:
            step = store.next_item(ref, token)
            if r["action"] in ("QUESTION", "DROP_2", "SOCRATIC_HINT"):
                assert step["question_id"] == r["qid"], (case,session,n,r,step)
                if r["action"] == "QUESTION":
                    assert step["kind"] == "question"
                    assert step["question_id"].startswith("QZ_")
                    n += 1
                else:
                    assert step["kind"] == "recovery"
                    assert step["action"] == r["action"]
                answer = choose(bank, r["qid"], r["answer"] == "correct", "practice")
                # Even a wrong DROP_2 choice must be one of the two
                # options actually shown by the backend.
                if r["action"] == "DROP_2" and answer not in step["options"]:
                    answer = next(x for x in step["options"]
                                  if x != bank.get(r["qid"],form="practice").correct_answer)
                qid = r["qid"]
            else:
                assert step["kind"] == "recovery" and step["action"] == r["action"]
                answer, qid = None, None
            store.answer_quiz(
                ref, token,
                request_id=f"case{case}_step_{cursor:04d}",
                item_id=qid, choice=answer,
                shown_at=at, answered_at=at + timedelta(milliseconds=100),
            )
            cursor += 1
            # The result of the *previous* step is persisted before the
            # backend can choose the next question or recovery action.
            with store._tx() as db:
                state = store._state(db, ref)
                m = state["engine"]["mastery"][r["concept"]]
                D = 1-sum(state["engine"]["mastery"].values())/8
                assert f"{m:.2f}" == r["mastery"], (case,session,cursor)
                assert f"{D:.3f}" == r["D"], (case,session,cursor)
        assert n == count
        if session == 3:
            assert store.progress(ref, token)["phase"] == "POSTTEST"
            for i, q in enumerate(bank.forms["posttest"]):
                assert store.next_item(ref, token)["question_id"] == q.question_id
                store.answer_assessment(
                    ref, token,
                    request_id=f"case{case}_post_{i:03d}",
                    item_id=q.question_id,
                    choice=q.correct_answer, shown_at=at, answered_at=at,
                )
        assert store.progress(ref, token)["phase"] == "SURVEY"
        store.submit_survey(
            ref, token, values=(3,4,5,6,2,1), time_ms=500,
            request_id=f"case{case}_survey_{session}", at=at,
        )
        if session < 3:
            assert store.progress(ref,token)["phase"] == "WAITING_NEXT_SESSION"
            store.open_next_session(ref,token,at=T0 + timedelta(days=4*session))
    assert store.progress(ref,token)["phase"] == "DONE"
    saved = store.export_anonymous_events(ref=ref,token=token)
    assert len(saved) == 8 + 16 + len(reference) + 16 + 3
    assert all("email" not in event and "token_hash" not in event
               for event in saved)
    assert len({x["event_id"] for x in saved}) == len(saved)
    assert len({x["request_id"] for x in saved}) == len(saved)
    with store._tx() as db:
        assert db.execute(
            "SELECT COUNT(*) FROM surveys WHERE learner_id=?", (ref,)
        ).fetchone()[0] == 3
        assert db.execute(
            "SELECT COUNT(*) FROM state_history WHERE learner_id=?", (ref,)
        ).fetchone()[0] == len(saved)
        assert db.execute(
            "SELECT status FROM participants WHERE learner_id=?", (ref,)
        ).fetchone()["status"] == "completed"
        assert [x["status"] for x in db.execute(
            "SELECT status FROM sessions WHERE learner_id=? ORDER BY session_no",
            (ref,),
        )] == ["completed"] * 3
    return {"case":case,"steps":len(reference),"events":len(saved)}


@pytest.mark.parametrize("case", range(1,8))
def test_complete_three_session_supervisor_case_in_durable_store(tmp_path,case):
    result = replay_case(case, tmp_path)
    assert result["steps"] in (55,59,71,75,79)


def test_no_practice_question_ever_drawn_from_screen_or_test_forms(tmp_path):
    result = replay_case(7, tmp_path)
    assert result["events"] == 98  # 8 screening +16 pre +55 quiz +16 post +3 surveys
