"""Provisional Steps 72-123 regression tests; synthetic evidence only."""
import sqlite3
from dataclasses import replace

import pytest

from src.prototype.study_v2 import (
    ARMS, BLOOM, CONCEPTS, SESSION_TARGETS, BKT, Belief, FixedPolicy,
    GreedyPolicy, RecoveryStatus, RuleBasedSelfHealing, OneConceptPOMCP,
    SyntheticAuditSQLite, audit_mock_study, allocate_arms, bank_hash,
    mock_study, require_expert_reviewed, synthetic_bank, validate_bank,
    write_mock_result,
)
from src.prototype.study_v2_runtime import SyntheticProtocolEngine, ProtocolError


def test_specification_and_bank_coverage():
    assert len(CONCEPTS) == 8 and len(BLOOM) == 6
    assert ARMS == ("A", "B", "C")
    assert SESSION_TARGETS == (20, 20, 15)
    assert validate_bank(synthetic_bank(), full=True)["pretest"] == 16


def test_answer_key_server_side_only():
    item = synthetic_bank()[0]
    assert "answer_id" not in item.public()


def test_unreviewed_content_cannot_pass_release_gate():
    with pytest.raises(ValueError, match="unreviewed"):
        require_expert_reviewed(synthetic_bank())


def test_duplicate_question_rejected():
    items = synthetic_bank()
    with pytest.raises(ValueError, match="duplicate"):
        validate_bank(items + [items[0]])


def test_duplicate_wording_rejected():
    items = synthetic_bank()
    with pytest.raises(ValueError, match="duplicate"):
        validate_bank(items + [replace(items[0],item_id="SYN_DIFFERENT")])


def test_bkt_correct_posterior_and_learning():
    b = BKT()
    assert b.posterior(.20, True) == pytest.approx(.18 / (.18 + .20))
    assert b.update(.20, True) > b.posterior(.20, True)


def test_bkt_incorrect_reduces_probability_before_learning():
    b = BKT()
    assert b.posterior(.20, False) == pytest.approx(.02 / (.02 + .60))
    assert b.update(.20, False) == pytest.approx(.12903225806451613)


def test_bkt_impossible_event_rejected():
    with pytest.raises(ValueError,match="impossible"):
        BKT(learn=0, slip=0, guess=0).posterior(1.0, False)


def test_belief_degradation_initial_and_update():
    belief = Belief()
    assert belief.degradation == pytest.approx(.80)
    belief.observe(CONCEPTS[0], True)
    assert belief.degradation < .80


def test_fixed_policy_is_independent_of_belief():
    items = [q for q in synthetic_bank() if q.form == "practice"]
    low = Belief()
    high = Belief({c:.9 for c in CONCEPTS})
    assert FixedPolicy().choose(low,items).item_id == FixedPolicy().choose(high,items).item_id


def test_greedy_selects_weakest_concept():
    items = [q for q in synthetic_bank() if q.form == "practice"]
    mastery = {c:.8 for c in CONCEPTS}
    mastery[CONCEPTS[3]] = .1
    chosen = GreedyPolicy().choose(Belief(mastery),items)
    assert chosen.concept == CONCEPTS[3]


def test_recovery_four_stages_and_bounded_attempts():
    policy = RuleBasedSelfHealing()
    b = Belief()
    s = RecoveryStatus()
    items = [q for q in synthetic_bank() if q.form == "practice"]
    decisions = [policy.choose(b,items,1,s).action for _ in range(8)]
    assert decisions == list(("CONCEPT_SUMMARY","DROP_2","WORKED_EXAMPLE","SOCRATIC_HINT") * 2)
    assert s.attempts == 2
    assert policy.choose(b,items,1,s).action == "QUESTION"
    assert s.nonrecoverable


def test_no_recovery_before_first_response():
    result = RuleBasedSelfHealing().choose(Belief(),
               [q for q in synthetic_bank() if q.form == "practice"],0,RecoveryStatus())
    assert result.action == "QUESTION"


def test_pomcp_deterministic_seed_and_valid_action():
    planner = OneConceptPOMCP(simulations=80)
    action = planner.choose(.2)
    assert action in planner.ACTIONS
    assert planner.choose(.2) == action


def test_pomcp_changes_with_parameters():
    with pytest.raises(ValueError):
        OneConceptPOMCP(horizon=0)
    with pytest.raises(ValueError):
        OneConceptPOMCP().choose(1.2)


def test_bank_manifest_stable():
    assert bank_hash(synthetic_bank()) == bank_hash(synthetic_bank())


def test_synthetic_randomization_is_balanced_and_seeded():
    import random
    first = allocate_arms(30, random.Random(5))
    assert first == allocate_arms(30, random.Random(5))
    assert {a:first.count(a) for a in ARMS} == dict.fromkeys(ARMS, 10)
    with pytest.raises(ValueError):
        allocate_arms(4, random.Random(5))


def test_nine_participant_full_dry_run():
    result = mock_study(9)
    audit = audit_mock_study(result)
    assert audit["participants"] == 9
    assert audit["normal_practice_responses"] == 495
    assert audit["pretest_responses"] == audit["posttest_responses"] == 144
    assert all(p["synthetic"] for p in result["participants"])


def test_mock_not_real_evidence():
    result = mock_study(3)
    result["synthetic"] = False
    with pytest.raises(ValueError,match="synthetic"):
        audit_mock_study(result)


def test_export_refuses_overwrite(tmp_path):
    path = tmp_path / "synthetic.json"
    result = mock_study(3)
    write_mock_result(path,result)
    with pytest.raises(FileExistsError):
        write_mock_result(path,result)


def test_synthetic_sqlite_journal_idempotent(tmp_path):
    journal = SyntheticAuditSQLite(tmp_path / "a.sqlite3")
    assert journal.append("SYN_0000", 0, "test", {"v":1})
    assert not journal.append("SYN_0000", 0, "test", {"v":1})
    assert len(journal.read_events()) == 1
    with pytest.raises(ValueError):
        journal.append("real_user",0,"test",{})


def engine(tmp_path):
    return SyntheticProtocolEngine(tmp_path / "protocol.sqlite3",synthetic_bank())


def test_protocol_enrollment_and_no_real_identifiers(tmp_path):
    e=engine(tmp_path)
    assert e.enroll("SYN_001", "A")
    assert not e.enroll("SYN_001", "A")
    with pytest.raises(ProtocolError):
        e.enroll("SYN_001", "B")
    with pytest.raises(ProtocolError):
        e.enroll("personal_name", "A")


def test_protocol_pending_action_survives_reopen(tmp_path):
    e=engine(tmp_path)
    e.enroll("SYN_001", "B")
    pending=e.next_action("SYN_001")
    assert "answer_id" not in pending["question"]
    new=engine(tmp_path)
    assert new.next_action("SYN_001") == pending


def test_protocol_request_replay_and_conflict(tmp_path):
    e=engine(tmp_path)
    e.enroll("SYN_001", "C")
    q=e.next_action("SYN_001")
    payload={"item_id":q["item_id"],"choice_id":"A"}
    first=e.act("SYN_001", "req-1", payload)
    assert first["replayed"] is False
    assert "correct" not in first  # no assessment feedback
    assert e.act("SYN_001", "req-1", payload)["replayed"] is True
    with pytest.raises(ProtocolError,match="reused"):
        e.act("SYN_001","req-1",{"item_id":q["item_id"],"choice_id":"B"})


def test_protocol_rejects_out_of_order_answer(tmp_path):
    e=engine(tmp_path)
    e.enroll("SYN_001","B")
    q=e.next_action("SYN_001")
    with pytest.raises(ProtocolError,match="pending"):
        e.act("SYN_001","req-2",{"item_id":"wrong","choice_id":"A"})
    with pytest.raises(ProtocolError,match="invalid option"):
        e.act("SYN_001","req-3",{"item_id":q["item_id"],"choice_id":"X"})


def test_protocol_three_arm_complete_with_synthetic_actions(tmp_path):
    e=engine(tmp_path)
    counts={}
    for arm in ARMS:
        pid="SYN_"+arm
        e.enroll(pid, arm)
        kinds=[]
        for k in range(130):
            d=e.next_action(pid)
            kind=d["action"]
            kinds.append(kind)
            if kind == "COMPLETE":
                break
            if kind in ("QUESTION","DROP_2"):
                payload={"item_id":d["item_id"],"choice_id":"A"}
            elif kind == "FATIGUE":
                payload={"values":[3]*6}
            else:
                payload={"acknowledged":True}
            e.act(pid,f"{pid}-{k}",payload)
        else:
            raise AssertionError("session loop did not terminate")
        assert kinds.count("QUESTION") == 16+55+16
        assert kinds.count("FATIGUE") == 3
        assert e.snapshot(pid)["stage"] == "complete"
        counts[arm]=kinds
    assert "CONCEPT_SUMMARY" in counts["A"]
    assert "CONCEPT_SUMMARY" not in counts["B"]+counts["C"]
    assert e.audit()["unique_request_count"] > 3 * (16+55+16+3)


def test_protocol_item_bank_change_detected(tmp_path):
    e=engine(tmp_path)
    e.enroll("SYN_001","B")
    bank=synthetic_bank()
    bank[0]=replace(bank[0],prompt="SYNTHETIC CHANGED FIXTURE")
    changed=SyntheticProtocolEngine(tmp_path / "protocol.sqlite3",bank)
    with pytest.raises(ProtocolError,match="changed"):
        changed.next_action("SYN_001")


def test_counterexample_initial_high_degradation_is_not_a_decline():
    """D>.5 at enrollment does not logically imply degradation occurred."""
    belief=Belief()
    assert belief.degradation > .5
    assert belief.mastery == dict.fromkeys(CONCEPTS,.20)


def test_counterexample_recovery_not_guaranteed_by_bounded_attempts():
    """The controller can exhaust its recovery budget with D still high."""
    b=Belief()
    s=RecoveryStatus()
    p=RuleBasedSelfHealing()
    items=[q for q in synthetic_bank() if q.form=="practice"]
    for _ in range(8):
        p.choose(b,items,1,s)
    assert s.attempts == 2
    assert b.degradation > .5
    p.choose(b,items,1,s)
    assert s.nonrecoverable


def test_invalid_protocol_action_does_not_advance_session(tmp_path):
    e=engine(tmp_path)
    e.enroll("SYN_001","A")
    question=e.next_action("SYN_001")
    start=e.snapshot("SYN_001")
    with pytest.raises(ProtocolError):
        e.act("SYN_001","bad-request",{"item_id":question["item_id"],"choice_id":"X"})
    assert e.snapshot("SYN_001") == start
    assert e.next_action("SYN_001")==question


def test_two_simultaneous_retries_are_idempotent(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    e=engine(tmp_path)
    e.enroll("SYN_001","C")
    d=e.next_action("SYN_001")
    payload={"item_id":d["item_id"],"choice_id":"A"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda i:e.act("SYN_001","same-id",payload), range(2)))
    assert sorted(r["replayed"] for r in results)==[False,True]
    assert e.snapshot("SYN_001")["index"]==1
