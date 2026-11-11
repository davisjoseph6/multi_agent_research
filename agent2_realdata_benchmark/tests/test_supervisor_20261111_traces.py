"""Regression oracle: all 465 submitted supervisor trace steps must match.

This reads actual supervisor-provided question IDs and scripted answers; the
selection engine NEVER reads the expected next item ID, concept or mode.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.prototype.supervisor_trace_engine import (
    CONCEPT_IDS, SESSION_BLOCKS, SupervisorTraceEngine,
)
from src.prototype.supervisor_content import SupervisorBank

DATA = Path(__file__).resolve().parents[1] / "data" / "supervisor_20261111"
INITIAL_MASTERY = {
    1: (.50, .20, .50, .50, .20, .20, .20, .50),
    2: (.75, .50, .75, .50, .75, .50, .20, .75),
    3: (.20, .20, .20, .20, .20, .20, .20, .20),
    4: (.75, .50, .75, .50, .75, .50, .20, .75),
    5: (.50, .20, .50, .50, .20, .20, .20, .50),
    6: (.50, .20, .50, .50, .20, .20, .20, .50),
    7: (.50, .20, .50, .50, .20, .20, .20, .50),
}


def rows():
    with (DATA / "scenario_traces.csv").open(
        newline="", encoding="utf-8-sig"
    ) as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def bank():
    return SupervisorBank(DATA)


@pytest.mark.parametrize("case", range(1, 8))
def test_every_supervisor_step_exactly_reproduced(case, bank):
    expected = [r for r in rows() if r["case"] == str(case)]
    expected_count = {1: 71, 2: 59, 3: 79, 4: 75,
                      5: 71, 6: 55, 7: 55}[case]
    assert len(expected) == expected_count
    engine = SupervisorTraceEngine(
        expected[0]["group"],
        dict(zip(CONCEPT_IDS, INITIAL_MASTERY[case])),
    )
    recovered = 0
    normal = 0
    for index, row in enumerate(expected):
        session = int(row["session"])
        if session != engine.session:
            engine.new_session(session)
        actual = engine.next_action()
        assert actual is not None, (case, index, "missing next action")
        expected_action = {
            "action": row["action"], "qid": row["qid"],
            "concept": row["concept"], "level": int(row["level"][1:]),
            "mode": row["mode"],
        }
        for name, wanted in expected_action.items():
            assert actual[name] == wanted, (
                case, session, index, name, actual[name], wanted,
            )
        if actual["action"] in ("QUESTION", "DROP_2", "SOCRATIC_HINT"):
            # Recovery and regular question IDs MUST come only from the
            # 192-item bank, never screening or independent assessments.
            item = bank.get(actual["qid"], form="practice")
            assert item.concept == row["concept"]
            assert item.level == int(row["level"][1:])
        engine.submit(row["answer"])
        assert format(engine.mastery[row["concept"]], ".2f") == row[
            "mastery"], (case, session, index, "mastery")
        assert format(engine.degradation, ".3f") == row[
            "D"], (case, session, index, "degradation")
        normal += actual["action"] == "QUESTION"
        recovered += actual["action"] != "QUESTION"
    assert normal == 55
    assert recovered == expected_count - 55
    assert engine.session == 3 and engine.question_in_session == 15
    assert engine.next_action() is None


def test_uploaded_trace_is_complete_and_has_three_nonoverlapping_arms(bank):
    trace = rows()
    assert len(trace) == 465
    assert {x["case"] for x in trace} == set("1234567")
    assert {x["group"] for x in trace} == {"A", "B", "C"}
    for case in range(1, 8):
        case_rows = [x for x in trace if x["case"] == str(case)]
        for session, block_size in enumerate(SESSION_BLOCKS, 1):
            assert len([
                x for x in case_rows if x["session"] == str(session)
                and x["action"] == "QUESTION"
            ]) == block_size
    assert len(bank.forms["practice"]) == 192
    assert len(bank.forms["screening"]) == 8
    assert len(bank.forms["pretest"]) == 16
    assert len(bank.forms["posttest"]) == 16


def test_group_c_original_inventory_order_and_no_new_question_numbers(bank):
    ids = bank.group_c_order()
    assert len(ids) == 55 and len(set(ids)) == 55
    assert ids[0] == "QZ_C1_L1_01"
    assert ids[23] == "QZ_C8_L1_03"
    assert ids[24] == "QZ_C1_L2_01"
    assert ids[54] == "QZ_C3_L3_01"
    assert all(x.endswith(("_01", "_02", "_03")) for x in ids)
    assert all(bank.get(q, form="practice").question_id == q for q in ids)


def test_full_screening_eligibility_and_pretest_qmatrix(bank):
    screening = bank.forms["screening"]
    right = {q.question_id:q.correct_answer for q in screening}
    assert bank.eligible(econ_course=False, screening_answers=right) == (
        False, 8)
    assert bank.eligible(econ_course=True, screening_answers={}) == (
        False, 0)
    # With five correct answers, the candidate may proceed.
    for q in screening[5:]:
        right[q.question_id] = (
            "B" if q.correct_answer != "B" else "C"
        )
    assert bank.eligible(econ_course=False, screening_answers=right) == (
        True, 5)
    assert bank.eligible(econ_course=True, screening_answers={}) == (
        False, 0)

    pre = bank.forms["pretest"]
    responses = {q.question_id:q.correct_answer for q in pre}
    for item in pre:
        if item.concept == "C2" or (
            item.concept == "C3" and item.level == 3
        ):
            responses[item.question_id] = (
                "B" if item.correct_answer != "B" else "C"
            )
    mastery = bank.initialize_qmatrix(responses)
    assert mastery["C1"] == .75
    assert mastery["C2"] == .20
    assert mastery["C3"] == .50
    assert set(mastery) == set(CONCEPT_IDS)
    assert all(item.question_id not in bank.group_c_order()
               for item in pre)


def test_assessment_answers_and_explanations_are_never_public(bank):
    for form, questions in bank.forms.items():
        for q in questions:
            public = q.public()
            assert "correct_answer" not in public
            assert "explanation" not in public
            assert set(public["options"]) == set("ABCD")
            assert q.question_text
            assert q.question_id not in (
                {i.question_id for name, items in bank.forms.items()
                 if name != form for i in items}
            )


def test_submitting_wrong_answer_type_does_not_trigger_recovery():
    engine = SupervisorTraceEngine(
        "A", dict(zip(CONCEPT_IDS, INITIAL_MASTERY[1])))
    with pytest.raises(ValueError, match="scored"):
        engine.submit("")
    # Explicitly do not treat degradation > 0.5 as a trigger.
    engine.submit("correct")
    assert engine.degradation > 0.5
    assert engine.pending == []


def test_recovery_graded_steps_do_not_increase_regular_question_counter():
    engine = SupervisorTraceEngine(
        "A", dict(zip(CONCEPT_IDS, INITIAL_MASTERY[3])))
    for _ in range(3):
        assert engine.next_action()["action"] == "QUESTION"
        engine.submit("wrong")
    assert engine.question_in_session == 3
    assert [x["action"] for x in engine.pending] == [
        "CONCEPT_SUMMARY", "DROP_2", "WORKED_EXAMPLE", "SOCRATIC_HINT"
    ]
    for answer in ("", "wrong", "", "wrong"):
        engine.submit(answer)
    assert engine.question_in_session == 3
    assert engine.attempts_session == 1


def test_no_additional_recovery_outside_arm_a():
    for arm in ("B", "C"):
        engine = SupervisorTraceEngine(
            arm, dict(zip(CONCEPT_IDS, INITIAL_MASTERY[3])))
        for _ in range(10):
            engine.submit("wrong")
        assert engine.pending == []
        assert engine.attempts_session == 0



def test_json_snapshot_resume_preserves_pending_recovery_and_session_peak():
    import json
    initial = dict(zip(CONCEPT_IDS, INITIAL_MASTERY[2]))
    engine = SupervisorTraceEngine("A", initial)
    # Case 2's first period has an L1 promotion and a later decline.
    for i, response in enumerate(("correct", "correct", "correct", "correct",
                                   "correct", "correct", "correct", "correct",
                                   "correct", "correct")):
        engine.submit(response)
    snap = json.loads(json.dumps(engine.snapshot()))
    resumed = SupervisorTraceEngine.restore(snap)
    assert resumed.snapshot() == engine.snapshot()
    assert resumed.next_action() == engine.next_action()
    # Complete case 2's actual 59-step oracle, checkpointing after every step.
    oracle = [x for x in rows() if x["case"] == "2"]
    engine = SupervisorTraceEngine("A", dict(zip(CONCEPT_IDS, INITIAL_MASTERY[2])))
    for row in oracle:
        if int(row["session"]) != engine.session:
            engine.new_session(int(row["session"]))
        expected = engine.next_action()
        assert expected["qid"] == row["qid"]
        engine.submit(row["answer"])
        engine = SupervisorTraceEngine.restore(
            json.loads(json.dumps(engine.snapshot())))
    assert engine.session == 3 and engine.question_in_session == 15


def test_recovery_resumes_at_exact_four_step_position_after_restart():
    import json
    p = SupervisorTraceEngine("A", dict(zip(CONCEPT_IDS, INITIAL_MASTERY[3])))
    for answer in ("wrong","wrong","wrong"):
        p.submit(answer)
    assert p.next_action()["action"] == "CONCEPT_SUMMARY"
    p.submit("")
    saved = json.loads(json.dumps(p.snapshot()))
    restored = SupervisorTraceEngine.restore(saved)
    assert restored.next_action()["action"] == "DROP_2"
    assert restored.next_action()["qid"] == "QZ_C1_L1_04"
    restored.submit("wrong")
    assert restored.next_action()["action"] == "WORKED_EXAMPLE"
    restored.submit("")
    restored.submit("wrong")
    assert restored.next_action()["qid"] == "QZ_C1_L1_05"
