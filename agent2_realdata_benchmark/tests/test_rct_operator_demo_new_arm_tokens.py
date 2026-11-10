"""Refresh only *fictional* demo credentials; old HTTPS demo remains usable."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sqlite3

import pytest

from scripts.rct_candidate_cli import engine_from
from scripts.rct_operator_demo import seed
from scripts.rct_operator_demo_new_arm_tokens import issue_fresh_demo_arm_tokens


BUNDLE = Path(__file__).resolve().parents[1] / "docs/rct_candidate_v1"
HOST = "demo.selfhealing-edu.fr"


def setup(tmp_path, hostname=HOST):
    source = json.loads((BUNDLE / "settings_rehearsal.json").read_text())
    source.update({
        "mode": "operator_demo",
        "allowed_hosts": [hostname],
        "behind_one_local_tls_proxy": True,
        "release_evidence": None,
        "content": {
            k: str(BUNDLE / value)
            for k, value in source["content"].items()
        },
    })
    settings = tmp_path / "demo_settings.json"
    settings.write_text(json.dumps(source), encoding="utf-8")
    database = tmp_path / "fictional.sqlite3"
    first_private = tmp_path / "first_PRIVATE.json"
    seed(settings=settings, database=database, output=first_private)
    return settings, database, first_private


def count_people(database):
    with sqlite3.connect(database) as db:
        return db.execute("SELECT COUNT(*) FROM rct_people").fetchone()[0]


def test_registers_fresh_a_b_c_in_same_existing_database(tmp_path):
    settings, database, first_private = setup(tmp_path)
    old_tokens = json.loads(first_private.read_text())["invitations"]
    old_first = old_tokens[0]["invitation"]
    engine = engine_from(settings, database)
    old_info = engine.information(old_first)
    assert old_info["mode"] == "operator_demo"
    target = tmp_path / "new_arm_tokens_PRIVATE.json"

    result = issue_fresh_demo_arm_tokens(
        settings=settings, database=database, output=target,
        expected_host=HOST, lifetime_hours=24,
    )
    assert result["result"] == "NEW_FICTIONAL_ARM_TOKENS_REGISTERED"
    assert result["created_fictional_records"] == 9
    assert sorted(result["selected_demo_arms"]) == ["A", "B", "C"]
    assert sum(result["new_arm_counts"].values()) == 9
    assert count_people(database) == 18
    assert target.stat().st_mode & 0o777 == 0o600
    assert not result["tokens_printed"] and not result["human_enrollment_authorized"]
    assert not result["existing_tokens_rotated"]
    assert engine.information(old_first) == old_info

    private = json.loads(target.read_text())
    assert private["host"] == HOST
    assert private["mode"] == "operator_demo"
    assert not private["human_enrollment_authorized"]
    selected = private["tokens_by_arm"]
    assert set(selected) == {"A", "B", "C"}
    assert len(private["reserve_fictional_invitations"]) == 6
    new_tokens = [selected[arm]["invitation"] for arm in "ABC"]
    new_tokens += [row["invitation"] for row in private["reserve_fictional_invitations"]]
    assert len(set(new_tokens)) == 9
    assert not set(new_tokens) & {row["invitation"] for row in old_tokens}
    assert all(token not in json.dumps(result) for token in new_tokens)

    all_private = engine.export_private()["outcomes"]
    arms = {record["pid"]: record["assigned_arm"] for record in all_private}
    for arm in "ABC":
        record = selected[arm]
        assert arms[record["participant_id"]] == arm
        assert record["fictional"]
        assert engine.information(record["invitation"])["status"] == "active"
        action = engine.next_action(record["invitation"])
        assert action["stage"] == "pretest"
        assert action["mode"] == "operator_demo"
        assert "answer_id" not in action["question"]


def test_rejects_existing_output_without_changing_db(tmp_path):
    settings, db, initial = setup(tmp_path)
    old_count = count_people(db)
    with pytest.raises(ValueError):
        issue_fresh_demo_arm_tokens(
            settings=settings, database=db, output=initial,
            expected_host=HOST,
        )
    assert count_people(db) == old_count


def test_rejects_unverified_host_and_unseeded_database(tmp_path):
    settings, db, initial = setup(tmp_path)
    old_count = count_people(db)
    with pytest.raises(ValueError, match="hostname"):
        issue_fresh_demo_arm_tokens(
            settings=settings, database=db,
            output=tmp_path / "bad_PRIVATE.json",
            expected_host="demo.example.fr",
        )
    assert count_people(db) == old_count
    with pytest.raises(ValueError):
        issue_fresh_demo_arm_tokens(
            settings=settings, database=tmp_path / "missing.sqlite3",
            output=tmp_path / "bad_PRIVATE.json",
            expected_host=HOST,
        )
    assert count_people(db) == old_count


def test_refuses_symlinked_database(tmp_path):
    settings, db, initial = setup(tmp_path)
    shortcut = tmp_path / "alias.sqlite3"
    shortcut.symlink_to(db)
    with pytest.raises(ValueError):
        issue_fresh_demo_arm_tokens(
            settings=settings, database=shortcut,
            output=tmp_path / "new_PRIVATE.json",
            expected_host=HOST,
        )
    assert count_people(db) == 9

def test_failed_allocation_rolls_back_entire_batch_and_private_file(tmp_path, monkeypatch):
    settings, db, initial = setup(tmp_path)
    from src.prototype.rct_candidate import RCTCandidateEngine

    original = RCTCandidateEngine._allocate
    calls = {"n": 0}

    def interrupted(conn, pid):
        calls["n"] += 1
        if calls["n"] == 4:
            raise RuntimeError("synthetic interrupted allocation")
        return original(conn, pid)

    monkeypatch.setattr(RCTCandidateEngine, "_allocate", staticmethod(interrupted))
    output = tmp_path / "failed_new_tokens_PRIVATE.json"
    with pytest.raises(RuntimeError, match="interrupted"):
        issue_fresh_demo_arm_tokens(
            settings=settings, database=db, output=output,
            expected_host=HOST,
        )
    assert count_people(db) == 9
    assert not output.exists()
    assert not list(tmp_path.glob(".pending_demo_arm_tokens_*"))


