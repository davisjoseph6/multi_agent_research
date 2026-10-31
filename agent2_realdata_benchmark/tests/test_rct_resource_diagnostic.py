"""Read-only resource diagnostic tests use fictional local records only."""
import json
import sqlite3

import pytest

from scripts.rct_candidate_cli import DEFAULT_SETTINGS, engine_from
from scripts.rct_resource_diagnostic import analyze


def test_rehearsal_resource_audit_shows_arm_without_token_or_identity(tmp_path):
    database=tmp_path/"fictional.sqlite3"
    engine=engine_from(DEFAULT_SETTINGS,database)
    invitation=engine.issue_invitation()
    engine.enroll(invitation["invitation"],agreed=True,
                  information_version=engine.bundle.hashes["information"])
    action=engine.next_action(invitation["invitation"])
    assert action["stage"]=="pretest"
    output=analyze(database)
    assert output["evidence"]=="LOCAL_REHEARSAL_READ_ONLY"
    assert output["participant_records"]==1
    assert sum(output["enrolled_by_arm"].values())==1
    assert output["latest_enrollment"]["stage"]=="pretest"
    assert output["latest_enrollment"]["question_index"]==0
    assert output["all_resources_offered"]=={}
    assert output["arm_A_POMCP_root_decisions"]==0
    rendered=json.dumps(output)
    assert invitation["invitation"] not in rendered
    assert invitation["participant_id"] not in rendered
    assert "token_hash" not in rendered
    assert engine.next_action(invitation["invitation"])==action


def test_diagnostic_refuses_live_mode_even_on_fake_empty_database(tmp_path):
    database=tmp_path/"fake-live.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE rct_config(id INTEGER PRIMARY KEY,value TEXT)")
        db.execute("INSERT INTO rct_config VALUES(1,?)",(json.dumps({"mode":"live"}),))
    with pytest.raises(ValueError,match="real-participant"):
        analyze(database)


def test_diagnostic_rejects_unknown_database(tmp_path):
    with pytest.raises(FileNotFoundError):
        analyze(tmp_path/"missing.sqlite3")
