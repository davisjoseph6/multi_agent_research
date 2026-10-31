"""A separately configured *draft* Raw TLX workload scale, not an approved study measure."""
import json

import pytest

from scripts.rct_candidate_cli import load_settings
from src.prototype.rct_candidate import RCTCandidateEngine
from src.prototype.rct_candidate_content import ContentBundle
from src.prototype.study_v2_runtime import ProtocolError

REHEARSAL_RAW="docs/rct_candidate_v1/settings_raw_tlx_REHEARSAL.json"


def test_raw_tlx_draft_is_unreviewed_and_has_correct_levels():
    settings,bundle,release=load_settings(REHEARSAL_RAW)
    assert settings["mode"]=="rehearsal"
    assert release is None
    assert bundle.fatigue["scale"]=={"minimum":0,"maximum":100,"step":5}
    assert len(bundle.fatigue["items"])==6
    assert set(bundle.fatigue["labels"])=={str(x) for x in range(0,101,5)}
    assert not bundle.fatigue_reviewed


def test_raw_tlx_draft_enforces_scale_without_changing_default(tmp_path):
    _,bundle,_=load_settings(REHEARSAL_RAW)
    engine=RCTCandidateEngine(tmp_path/"raw_tlx.sqlite3",bundle,simulations=41)
    issued=engine.issue_invitation()
    invitation=issued["invitation"]
    pid=issued["participant_id"]
    engine.enroll(invitation,agreed=True,information_version=bundle.hashes["information"])
    with engine._transaction() as db:
        row=db.execute("SELECT state FROM rct_people WHERE pid=?",
                       (pid,)).fetchone()
        state=json.loads(row["state"])
        state.update(stage="fatigue",session=1,index=0,pending=None)
        db.execute("UPDATE rct_people SET state=? WHERE pid=?",
                   (json.dumps(state,sort_keys=True,separators=(",",":")),
                    pid))
    action=engine.next_action(invitation)
    assert action["action"]=="FATIGUE"
    assert action["questionnaire"]["scale"]["maximum"]==100
    engine.rendered(invitation,action["action_id"])
    for values in ([1,5,10,20,30,40],[-5,5,10,20,30,40],[0,0,0,0,0,105]):
        with pytest.raises(ProtocolError,match="questionnaire scale"):
            engine.act(invitation,"rejected"+str(values),action["action_id"],{"values":values})
    assert engine.act(invitation,"valid_raw_tlx",action["action_id"],
                      {"values":[0,5,25,50,75,100]})["accepted"]
    assert engine.audit()["pending_actions"]==0


def test_existing_rehearsal_fixture_remains_1_to_5():
    _,bundle,_=load_settings("docs/rct_candidate_v1/settings_rehearsal.json")
    assert bundle.fatigue["scale"]=={"minimum":1,"maximum":5,"step":1}
    assert not bundle.fatigue_reviewed
