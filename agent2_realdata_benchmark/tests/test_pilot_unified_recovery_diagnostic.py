"""Audit the exact 8767 fictional app schema without touching a live service."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import uuid

import pytest

from scripts.pilot_unified_fictional_browser import open_synthetic_study
from scripts.pilot_unified_recovery_diagnostic import (
    FictionalRecoveryDiagnosticError, inspect_fictional_recovery,
)
from src.prototype.pilot_unified_fictional_browser import SYNTHETIC_EPOCH


def test_separate_unified_fixture_report_is_private_and_read_only(tmp_path):
    db = tmp_path / "fictional_admission.sqlite3"
    study, roster, operator, clock = open_synthetic_study(db)
    before = sha256(db.read_bytes()).hexdigest()
    report = inspect_fictional_recovery(db)
    assert sha256(db.read_bytes()).hexdigest() == before
    assert report["result"] == "PASS_SYNTHETIC_INSPECTION"
    assert report["application"] == "PORT_8767_UNIFIED_SYNTHETIC_SQLITE"
    assert set(report["fictional_fixture_counts"]) == {"F1", "F2", "F3"}
    assert set(report["private_aggregate_by_arm"]) == {"A", "B", "C"}
    assert report["all_three_have_zero_recoveries"]
    assert report["sqlite_read_only"]
    assert report["operator_demo_8077_inspected"] is False
    assert report["human_enrollment_authorized"] is False
    assert all("operator_private_arm" not in detail
               for detail in report["fictional_fixture_counts"].values())
    assert "SYN_PILOT_" not in json.dumps(report)
    assert "SYN_ADMISSION_" not in json.dumps(report)
    private = inspect_fictional_recovery(db, show_arm=True)
    assert {x["operator_private_arm"]
            for x in private["fictional_fixture_counts"].values()} == {"A", "B", "C"}


def test_read_only_diagnostic_counts_actual_wrong_practice_answer(tmp_path):
    db = tmp_path / "fictional_admission.sqlite3"
    study, roster, operator, clock = open_synthetic_study(db)
    arm_a = next(
        pid for pid in roster.values()
        if study.operator_lookup(operator, pid)[1] == "A"
    )
    learner, _ = study.operator_lookup(operator, arm_a)
    at = SYNTHETIC_EPOCH
    for _ in range(16):
        offered = study.learning.next_action(learner, at=at)
        assert offered["action"] == "QUESTION"
        study.learning.mark_rendered(learner, offered["action_id"], at=at)
        study.learning.submit(
            learner, offered["action_id"], uuid.uuid4().hex,
            {"choice_id": offered["question"]["options"][0][0]}, at=at,
        )
    fatigue = study.learning.next_action(learner, at=at)
    assert fatigue["action"] == "MVAS"
    study.learning.mark_rendered(learner, fatigue["action_id"], at=at)
    study.learning.submit(
        learner, fatigue["action_id"], uuid.uuid4().hex,
        {"rating": 50}, at=at,
    )
    question = study.learning.next_action(learner, at=at)
    assert question["action"] == "QUESTION"
    item = study.learning.policy_bank.by_id[question["question"]["item_id"]]
    wrong = next(option for option, _ in item.options if option != item.answer_id)
    study.learning.mark_rendered(learner, question["action_id"], at=at)
    assert study.learning.submit(
        learner, question["action_id"], uuid.uuid4().hex,
        {"choice_id": wrong}, at=at,
    )["correct"] is False
    report = inspect_fictional_recovery(db)
    arm = report["private_aggregate_by_arm"]["A"]
    assert arm["incorrect_practice_questions"] == 1
    assert arm["completed_practice_questions"] == 1
    assert arm["recovery_offered_total"] == 0
    assert arm["planner_practice_choices_with_trace"] == 0


def test_refuse_other_filenames_absent_file_or_corrupted_schema(tmp_path):
    with pytest.raises(FictionalRecoveryDiagnosticError):
        inspect_fictional_recovery(tmp_path / "not-fictional.sqlite3")
    db = tmp_path / "fictional_admission.sqlite3"
    with pytest.raises(FictionalRecoveryDiagnosticError):
        inspect_fictional_recovery(db)
    study, roster, operator, clock = open_synthetic_study(db)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE admission_config SET config=? WHERE id=1",
                     ('{"schema":"NOT_SYNTHETIC"}',))
    with pytest.raises(FictionalRecoveryDiagnosticError):
        inspect_fictional_recovery(db)
