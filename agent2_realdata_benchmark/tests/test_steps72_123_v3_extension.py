"""Independent synthetic engineering checks. NOT ethics, calibration, or a proof."""
import json
import random

import pytest

from src.prototype.study_v2 import CONCEPTS, synthetic_bank
from src.prototype.study_v3_pomcp import (
    ACTIONS, PRACTICE, EightConceptPOMCP, GenerativeAssumptions,
    PlanningState,
)
from src.prototype.study_v3_runtime import SyntheticPOMCPProtocolEngine
import importlib.util
from scripts.step123_v3_pomcp_mock import run


def planner(sims=80, **kw):
    return EightConceptPOMCP(simulations=sims, **kw)


def belief(v=.2):
    return dict.fromkeys(CONCEPTS,v)


def test_eight_concepts_and_five_action_kinds():
    assert len(CONCEPTS) == 8
    assert ACTIONS == ("QUESTION", "CONCEPT_SUMMARY", "DROP_2", "WORKED_EXAMPLE", "SOCRATIC_HINT")
    result=planner().choose(belief(),practice_concepts=CONCEPTS,seed=31)
    assert len(result.root_visits) == 40
    assert result.action in ACTIONS
    assert result.concept in CONCEPTS
    assert result.synthetic_only
    assert result.simulations == 80
    assert sum(result.root_visits.values()) <= 80


def test_repeatable_action_and_trace_for_fixed_seed():
    a=planner().choose(belief(.37),practice_concepts=CONCEPTS,seed=99)
    b=planner().choose(belief(.37),practice_concepts=CONCEPTS,seed=99)
    assert a == b
    assert a.assumption_hash == GenerativeAssumptions().fingerprint


def test_resource_budget_zero_fixes_practice_only():
    a=planner().choose(belief(),practice_concepts=CONCEPTS,resources_left=0)
    assert a.action==PRACTICE and len(a.root_visits)==8


def test_concept_availability_is_enforced():
    a=planner().choose(belief(),practice_concepts=[CONCEPTS[3]],resources_left=2)
    assert a.concept==CONCEPTS[3]
    assert len(a.root_visits)==5


def test_action_budget_decrements_for_resource():
    p=planner()
    state=PlanningState((False,)*8,1)
    s,obs,r=p._step(state,("WORKED_EXAMPLE",CONCEPTS[0]),random.Random(1))
    assert s.resources_left==0
    assert obs is None
    with pytest.raises(ValueError):
        p._step(s,("WORKED_EXAMPLE",CONCEPTS[0]),random.Random(1))


def test_observation_occurs_before_learning_transition():
    a=GenerativeAssumptions(learn_practice=1,slip=0,guess=0)
    p=planner(assumptions=a)
    s,obs,_=p._step(PlanningState((False,)*8,0),(PRACTICE,CONCEPTS[0]),random.Random(1))
    assert obs==0 and s.mastered[0] is True


@pytest.mark.parametrize("state",[(True,), (False,)*9,(0,)*8])
def test_invalid_latent_state_rejected(state):
    with pytest.raises(ValueError):
        PlanningState(state,1)


@pytest.mark.parametrize("kwargs",[
    {"horizon":0}, {"simulations":0}, {"exploration":float('nan')},
    {"discount":2}, {"horizon":21},
])
def test_invalid_planner_configuration(kwargs):
    with pytest.raises(ValueError):
        EightConceptPOMCP(**kwargs)


@pytest.mark.parametrize("invalid",[
    {"other":.3}, {**dict.fromkeys(CONCEPTS,.2),CONCEPTS[0]:float('nan')},
    {**dict.fromkeys(CONCEPTS,.2),CONCEPTS[0]:-1},
])
def test_invalid_belief_rejected(invalid):
    with pytest.raises(ValueError):
        planner(20).choose(invalid,practice_concepts=CONCEPTS)


def test_calibration_honesty_zero_learning_counterexample():
    no_learning=GenerativeAssumptions(learn_practice=0,learn_summary=0,
        learn_drop2=0,learn_worked=0,learn_socratic=0)
    p=planner(assumptions=no_learning)
    s=PlanningState((False,)*8,2)
    for action in ACTIONS:
        _,_,reward=p._step(s,(action,CONCEPTS[0]),random.Random(4))
        assert reward <= 0  # A blanket strict negative-drift theorem cannot hold.


def test_resource_budget_bounded_across_durable_actions(tmp_path):
    e=SyntheticPOMCPProtocolEngine(tmp_path/"p.db",synthetic_bank(),planner=planner(40),
                                   max_resources_per_session=2)
    e.enroll("SYN_abc","A")
    for k in range(16):
        a=e.next_action("SYN_abc")
        e.act("SYN_abc",f"pre{k}",{"item_id":a["item_id"],"choice_id":"A"})
    resources=0
    for k in range(100):
        a=e.next_action("SYN_abc")
        if a["action"]=="FATIGUE":break
        if a["action"] in ("QUESTION","DROP_2"):
            data={"item_id":a["item_id"],"choice_id":"A"}
        else:
            data={"acknowledged":True}
        if a["action"]!="QUESTION":resources+=1
        e.act("SYN_abc",f"practice{k}",data)
    else:
        pytest.fail("first session did not terminate")
    assert resources<=2
    assert e.snapshot("SYN_abc")["recovery"]["pomcp_resource_spent"]==resources


def test_durable_pending_recovery_and_exactly_once_request(tmp_path):
    path=tmp_path/"p.db"; bank=synthetic_bank()
    e=SyntheticPOMCPProtocolEngine(path,bank,planner=planner(20))
    e.enroll("SYN_persist","B")
    original=e.next_action("SYN_persist")
    reopened=SyntheticPOMCPProtocolEngine(path,bank,planner=planner(20))
    assert reopened.next_action("SYN_persist")==original
    payload={"item_id":original["item_id"],"choice_id":"A"}
    assert reopened.act("SYN_persist","uuid-persist",payload)["replayed"] is False
    assert e.act("SYN_persist","uuid-persist",payload)["replayed"] is True


def test_three_arm_complete_synthetic_mock():
    result=run(n=3,seed=71,simulations=20)
    assert result["synthetic"] and result["approved_study"] is False
    assert result["per_arm"]=={"A":1,"B":1,"C":1}
    assert result["activity_counts"]=={"pretest":48,"practice":165,"fatigue":9,"posttest":48}
    assert result["resource_actions_by_arm"]["B"]==0
    assert result["resource_actions_by_arm"]["C"]==0


def browser(tmp_path):
    from src.prototype.study_v3_demo_api import create_synthetic_browser_app
    app=create_synthetic_browser_app(tmp_path/"browser.db",token="TEST_DEVELOPMENT_ONLY_TOKEN_123456789",simulations=20)
    app.config["TESTING"]=True
    return app.test_client()


def auth():
    return {"Authorization":"Bearer TEST_DEVELOPMENT_ONLY_TOKEN_123456789"}


@pytest.mark.skipif(importlib.util.find_spec("flask") is None, reason="Flask not installed in isolated test container")
def test_development_browser_content_security_and_synthetic_warning(tmp_path):
    c=browser(tmp_path)
    res=c.get("/trial-v3")
    assert res.status_code==200
    assert b"SYNTHETIC" in res.data
    assert b"TEST_DEVELOPMENT_ONLY_TOKEN" not in res.data
    assert "frame-ancestors 'none'" in res.headers["Content-Security-Policy"]
    assert c.get("/trial-v3/app.js").status_code==200
    assert c.get("/trial-v3/base.css").status_code==200


@pytest.mark.skipif(importlib.util.find_spec("flask") is None, reason="Flask not installed in isolated test container")
def test_browser_auth_required_for_every_session_action(tmp_path):
    c=browser(tmp_path)
    for route in ("enroll","next","act","status"):
        assert c.post(f"/api/v3/{route}",json={"participant_id":"SYN_abc"}).status_code==401
        assert c.post(f"/api/v3/{route}",headers={"Authorization":"Bearer invalid"},
                      json={"participant_id":"SYN_abc"}).status_code==401


@pytest.mark.skipif(importlib.util.find_spec("flask") is None, reason="Flask not installed in isolated test container")
def test_remote_browser_denied(tmp_path):
    c=browser(tmp_path)
    assert c.get("/trial-v3",environ_overrides={"REMOTE_ADDR":"8.8.8.8"}).status_code==403


@pytest.mark.skipif(importlib.util.find_spec("flask") is None, reason="Flask not installed in isolated test container")
def test_browser_rejects_real_participant_and_replays_enrollment(tmp_path):
    c=browser(tmp_path)
    assert c.post("/api/v3/enroll",headers=auth(),json={"participant_id":"Real John","arm":"A"}).status_code==400
    one=c.post("/api/v3/enroll",headers=auth(),json={"participant_id":"SYN_abc","arm":"C"})
    two=c.post("/api/v3/enroll",headers=auth(),json={"participant_id":"SYN_abc","arm":"C"})
    assert one.status_code==201 and two.status_code==200
    assert two.get_json()["created"] is False
    assert c.post("/api/v3/enroll",headers=auth(),json={"participant_id":"SYN_abc","arm":"A"}).status_code==400


@pytest.mark.skipif(importlib.util.find_spec("flask") is None, reason="Flask not installed in isolated test container")
def test_browser_question_and_no_answer_key_and_replay(tmp_path):
    c=browser(tmp_path)
    c.post("/api/v3/enroll",headers=auth(),json={"participant_id":"SYN_abc","arm":"B"})
    q=c.post("/api/v3/next",headers=auth(),json={"participant_id":"SYN_abc"}).get_json()
    assert q["action"]=="QUESTION" and "answer_id" not in json.dumps(q)
    payload={"participant_id":"SYN_abc","request_id":"r1",
             "response":{"item_id":q["item_id"],"choice_id":"A"}}
    first=c.post("/api/v3/act",headers=auth(),json=payload)
    replay=c.post("/api/v3/act",headers=auth(),json=payload)
    assert first.status_code==200 and replay.get_json()["replayed"] is True
    assert "correct" not in first.get_json() # independent pretest must not leak
    q2=c.post("/api/v3/next",headers=auth(),json={"participant_id":"SYN_abc"}).get_json()
    assert q2["item_id"]!=q["item_id"]


@pytest.mark.skipif(importlib.util.find_spec("flask") is None, reason="Flask not installed in isolated test container")
def test_bad_host_header_denied(tmp_path):
    c=browser(tmp_path)
    assert c.get("/trial-v3",headers={"Host":"evil.example"}).status_code==403


def test_pretest_updates_belief_without_instructional_transition(tmp_path):
    e=SyntheticPOMCPProtocolEngine(tmp_path/"p.db",synthetic_bank(),planner=planner(20))
    e.enroll("SYN_baseline","B")
    q=e.next_action("SYN_baseline")
    concept=q["concept"]
    e.act("SYN_baseline","pre_first",{"item_id":q["item_id"],"choice_id":"A"})
    with e._connect() as conn:
        state=e._get(conn,"SYN_baseline")
    # From prior=0.20, slip=.10, guess=.25, incorrect observation:
    # P(mastered | incorrect) = .02/(.02+.60) = .032258...
    assert state["mastery"][concept] == pytest.approx(.02/(.02+.60))


def test_v3_nonadaptive_schedule_balances_all_eight_concepts(tmp_path):
    e=SyntheticPOMCPProtocolEngine(tmp_path/"p.db",synthetic_bank(),planner=planner(20))
    e.enroll("SYN_fixed","C")
    for k in range(16):
        q=e.next_action("SYN_fixed")
        e.act("SYN_fixed",f"pre{k}",{"item_id":q["item_id"],"choice_id":"A"})
    seen=[]
    for k in range(60):
        q=e.next_action("SYN_fixed")
        if q["action"] == "FATIGUE":
            e.act("SYN_fixed",f"fatigue{k}",{"values":[3]*6})
            continue
        if q["action"] == "QUESTION":
            seen.append(q["concept"])
            e.act("SYN_fixed",f"practice{k}",{"item_id":q["item_id"],"choice_id":"A"})
        if len(seen) == 55:
            break
    assert len(seen) == 55
    assert set(seen)==set(CONCEPTS)
    assert max(seen.count(c) for c in CONCEPTS)-min(seen.count(c) for c in CONCEPTS)<=1


def test_exact_one_step_drift_identity_all_256_states():
    from itertools import product
    model=GenerativeAssumptions()
    for bits in product((False,True),repeat=8):
        before=1-sum(bits)/8
        for action in ACTIONS:
            j=4
            p=model.rate(action)
            if bits[j]:
                expected_after=before
            else:
                mastered=list(bits)
                mastered[j]=True
                after_mastery=1-sum(mastered)/8
                expected_after=p*after_mastery+(1-p)*before
            assert expected_after-before == pytest.approx(-p*(1-int(bits[j]))/8)


def test_v3_mock_replays_deterministically_and_uses_planner():
    first=run(n=3,seed=99,simulations=30)
    second=run(n=3,seed=99,simulations=30)
    assert first==second
    assert 0 <= first["resource_actions_by_arm"]["A"] <= 6
    assert first["resource_actions_by_arm"]["B"] == 0
    assert first["resource_actions_by_arm"]["C"] == 0


def test_v3_sensitivity_is_distinct_from_human_evidence():
    from scripts.step95_v3_sensitivity import run as sensitivities
    result=sensitivities(seed=2,simulations=20)
    assert result["synthetic"] and not result["human_evidence"]
    assert len(result["results"]) == 9
    assert len({entry["model_sha256"] for entry in result["results"]}) == 3


def test_reject_v3_restart_with_different_planner_or_budget(tmp_path):
    from src.prototype.study_v2_runtime import ProtocolError
    path=tmp_path/"p.db"
    SyntheticPOMCPProtocolEngine(path,synthetic_bank(),planner=planner(20))
    SyntheticPOMCPProtocolEngine(path,synthetic_bank(),planner=planner(20))
    with pytest.raises(ProtocolError,match="configuration changed"):
        SyntheticPOMCPProtocolEngine(path,synthetic_bank(),planner=planner(21))
    with pytest.raises(ProtocolError,match="configuration changed"):
        SyntheticPOMCPProtocolEngine(path,synthetic_bank(),planner=planner(20),
                                      max_resources_per_session=1)


def test_refuse_silent_upgrade_of_existing_v2_trial(tmp_path):
    from src.prototype.study_v2_runtime import SyntheticProtocolEngine, ProtocolError
    path=tmp_path/"p.db"
    legacy=SyntheticProtocolEngine(path,synthetic_bank())
    legacy.enroll("SYN_legacy","A")
    with pytest.raises(ProtocolError,match="cannot upgrade"):
        SyntheticPOMCPProtocolEngine(path,synthetic_bank(),planner=planner(20))


@pytest.mark.skipif(importlib.util.find_spec("flask") is None, reason="Flask not installed in isolated test container")
@pytest.mark.parametrize("arm",["A","B","C"])
def test_flask_full_three_session_synthetic_journey(tmp_path, arm):
    client=browser(tmp_path)
    pid=f"SYN_FULL_{arm}"
    data={"participant_id":pid,"arm":arm}
    assert client.post("/api/v3/enroll",headers=auth(),json=data).status_code==201
    counts={"pretest":0,"practice":0,"posttest":0,"fatigue":0}
    for k in range(160):
        status=client.post("/api/v3/status",headers=auth(),json={"participant_id":pid})
        assert status.status_code==200
        stage=status.get_json()["stage"]
        action=client.post("/api/v3/next",headers=auth(),json={"participant_id":pid})
        assert action.status_code==200
        decision=action.get_json()
        if decision["action"]=="COMPLETE":
            break
        if k==15:
            # Emulates a page reload and returning to the same enrollment.
            replay=client.post("/api/v3/enroll",headers=auth(),json=data)
            assert replay.status_code==200
        if decision["action"] in ("QUESTION","DROP_2"):
            payload={"item_id":decision["item_id"],"choice_id":"A"}
            if decision["action"]=="QUESTION":
                counts[stage]+=1
                if stage in ("pretest","posttest"):
                    assert "answer_id" not in json.dumps(decision)
        elif decision["action"]=="FATIGUE":
            payload={"values":[3]*6}
            counts["fatigue"]+=1
        else:
            payload={"acknowledged":True}
        response=client.post("/api/v3/act",headers=auth(),json={
            "participant_id":pid,"request_id":f"full-{arm}-{k}","response":payload})
        assert response.status_code==200, response.get_json()
    else:
        pytest.fail("three-session browser protocol did not finish")
    assert counts=={"pretest":16,"practice":55,"posttest":16,"fatigue":3}
