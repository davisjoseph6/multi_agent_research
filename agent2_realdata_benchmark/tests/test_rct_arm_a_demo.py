"""Fictional operator-selected Arm A demo never changes allocation or prints credentials."""
import json
import stat

import pytest

from scripts.rct_arm_a_demo import prepare
from scripts.rct_candidate_cli import DEFAULT_SETTINGS, engine_from


def test_operator_selects_arm_a_from_unchanged_balanced_fictional_allocations(tmp_path):
    database = tmp_path / "fresh_rehearsal.sqlite3"
    out = tmp_path / "private_invite.json"
    result = prepare(database=database, output=out)
    assert result["fictional_enrolled"] == 9
    assert result["operator_selected_demo_arm"] == "A"
    assert not result["human_RCT_evidence"]
    assert not result["treatment_policy_modified"]
    assert result["arm_counts"]["A"] >= 2
    assert result["arm_counts"]["B"] >= 2
    assert result["arm_counts"]["C"] >= 2
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    private = json.loads(out.read_text())
    assert private["selected_arm"] == "A"
    assert private["not_randomly_selected_recruit"]
    assert private["invitation"] not in json.dumps(result)
    engine = engine_from(DEFAULT_SETTINGS, database)
    action = engine.next_action(private["invitation"])
    assert action["action"] == "QUESTION"
    assert action["stage"] == "pretest"
    assert action["index"] == 0
    assert engine.audit()["people"]["active"] == 9


def test_demo_refuses_to_reuse_records_or_overwrite_invite(tmp_path):
    database = tmp_path / "fresh_rehearsal.sqlite3"
    output = tmp_path / "private_invite.json"
    prepare(database=database, output=output)
    with pytest.raises(FileExistsError):
        prepare(database=database, output=tmp_path/"other.json")
    with pytest.raises(FileExistsError):
        prepare(database=tmp_path/"other.sqlite3", output=output)
