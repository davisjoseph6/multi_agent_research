"""Synthetic-only guarded protocol integration and paired comparison audit."""
import json
import sqlite3

import pytest

from src.prototype.study_v2 import CONCEPTS, synthetic_bank
from src.prototype.study_v2_runtime import ProtocolError
from src.prototype.study_v3_pomcp import EightConceptPOMCP
from src.prototype.study_v3_runtime import SyntheticPOMCPProtocolEngine
from src.prototype.study_v5_guarded_planner import BeliefSupportGuardedPOMCP
from src.prototype.study_v5_protocol import PolicyLockedGuardedProtocolEngine, POLICY_ID
from scripts.step95_v5_paired_decisions import cases, run


def engine(tmp_path, *, simulations=25):
    return PolicyLockedGuardedProtocolEngine(
        tmp_path / "guarded.sqlite3",synthetic_bank(),
        planner=BeliefSupportGuardedPOMCP(simulations=simulations),
    )


def test_v5_policy_db_lock_and_clean_restart(tmp_path):
    e = engine(tmp_path)
    assert e.v5_config["policy_id"] == POLICY_ID
    reopened = engine(tmp_path)
    assert reopened.v5_config == e.v5_config


def test_reject_silent_existing_v3_database(tmp_path):
    path = tmp_path / "guarded.sqlite3"
    v3 = SyntheticPOMCPProtocolEngine(
        path,synthetic_bank(),planner=EightConceptPOMCP(simulations=25)
    )
    v3.enroll("SYN_EXISTING", "A")
    with pytest.raises(ProtocolError,match="preexisting V3"):
        engine(tmp_path)


def test_reject_changed_guarded_planning_budget(tmp_path):
    engine(tmp_path)
    with pytest.raises(ProtocolError):
        engine(tmp_path, simulations=35)


def test_reject_plain_v3_planner_for_v5(tmp_path):
    with pytest.raises(TypeError, match="guarded planner"):
        PolicyLockedGuardedProtocolEngine(
            tmp_path/"bad.sqlite3",synthetic_bank(),
            planner=EightConceptPOMCP(simulations=25),
        )


def advance_pretest(e,pid):
    e.enroll(pid,"A")
    for i in range(16):
        q = e.next_action(pid)
        assert q["action"] == "QUESTION"
        outcome = e.act(pid,f"pre_{i}",{"item_id":q["item_id"],"choice_id":"A"})
        assert outcome["accepted"]


def test_pomcp_trace_survives_commit_and_restart(tmp_path):
    e = engine(tmp_path)
    advance_pretest(e,"SYN_TEST")
    warmup = e.next_action("SYN_TEST")
    e.act("SYN_TEST","warmup_1",{"item_id":warmup["item_id"],"choice_id":"A"})
    plan = e.next_action("SYN_TEST")
    assert plan["planning_trace"]["policy_id"] == POLICY_ID
    audit_before = e.guarded_decision_audit()
    assert audit_before["planner_decisions"] == 1
    if plan["action"] in ("QUESTION","DROP_2"):
        payload = {"item_id":plan["item_id"],"choice_id":"A"}
    else:
        payload = {"acknowledged":True}
    e.act("SYN_TEST","plan_2",payload)
    restarted = engine(tmp_path)
    audit_after = restarted.guarded_decision_audit()
    assert audit_after["planner_decisions"] == 1
    assert audit_after["raw_action_preserved"]
    with sqlite3.connect(restarted.path) as db:
        events = [json.loads(r[0]) for r in db.execute(
            "SELECT event_json FROM synthetic_protocol_events ORDER BY seq")]
    plans = [x["planning_trace"] for x in events if x.get("planning_trace")]
    assert plans and plans[0]["raw_concept"] in CONCEPTS
    assert "guard_applied" in plans[0]


def test_next_action_idempotent_no_duplicate_provenance(tmp_path):
    e = engine(tmp_path)
    advance_pretest(e,"SYN_REPEAT")
    a = e.next_action("SYN_REPEAT")
    b = e.next_action("SYN_REPEAT")
    assert a == b
    assert e.guarded_decision_audit()["action_events"] == 17


def test_no_real_ids_accepted(tmp_path):
    e = engine(tmp_path)
    with pytest.raises(ProtocolError):
        e.enroll("real_person","A")


def test_paired_decisions_exactly_reproducible():
    a = run(simulations=12,seeds=(71,),budgets=(0,2))
    b = run(simulations=12,seeds=(71,),budgets=(0,2))
    assert a==b
    assert a["summary"]["cases"] == 2*len(cases())
    assert a["human_evidence"] is False


def test_known_witness_intercepted_with_comparable_inputs():
    out = run(simulations=240,seeds=(71,),budgets=(2,))
    row = next(r for r in out["rows"] if r["scenario"]=="one_unmastered_nudge")
    assert row["raw_action"] == "QUESTION"
    assert row["raw_concept"] == "Utility"
    assert row["guarded_concept"] == "Nudge Theory"
    assert row["guard_applied"]
    assert row["raw_expected_gain"] == 0
    assert row["guarded_expected_gain"] > 0


def test_no_zero_gain_increase_without_legal_alternative():
    out = run(simulations=10,seeds=(71,),budgets=(0,))
    fully_mastered = [r for r in out["rows"] if r["scenario"] == "all_mastered"]
    assert len(fully_mastered) == 1
    assert not fully_mastered[0]["guard_applied"]
    assert fully_mastered[0]["guarded_expected_gain"] == 0


def test_complete_three_arm_v5_mock_is_auditable():
    from scripts.step123_v5_guarded_mock import run as run_mock
    report = run_mock(n=3,seed=71,simulations=12)
    assert report["activity_counts"] == {
        "pretest":48,"practice":165,"fatigue":9,"posttest":48,
    }
    assert report["per_arm"] == {"A":1,"B":1,"C":1}
    assert report["v5_policy_audit"]["planner_decisions"] > 0
    assert report["v5_policy_audit"]["raw_action_preserved"]
    assert report["approved_study"] is False


def test_integrity_audit_detects_tampered_policy_identity(tmp_path):
    e = engine(tmp_path)
    e.enroll("SYN_TAMPER","B")
    e.next_action("SYN_TAMPER")
    with sqlite3.connect(e.path) as db:
        row = db.execute(
            "SELECT seq,event_json FROM synthetic_protocol_events "
            "WHERE event_json LIKE '%action_selected%' LIMIT 1"
        ).fetchone()
        event = json.loads(row[1]); event["policy_id"] = "wrong_policy"
        db.execute("UPDATE synthetic_protocol_events SET event_json=? WHERE seq=?",
                   (json.dumps(event),row[0]))
    with pytest.raises(ProtocolError,match="mixed policy"):
        e.guarded_decision_audit()
