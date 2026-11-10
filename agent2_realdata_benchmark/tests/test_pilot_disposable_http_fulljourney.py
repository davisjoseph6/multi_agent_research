"""Run actual three-arm/three-visit HTTP rehearsal on disposable SQLite only."""
from __future__ import annotations

from scripts.pilot_disposable_http_fulljourney import (
    _answer, run_disposable_http_fulljourney,
)


def test_answers_for_fictional_question_and_mvas():
    assert _answer({
        "action": "QUESTION",
        "question": {"options": [["a", "A"], ["b", "B"]]},
    }) == {"choice_id": "a"}
    assert _answer({
        "action": "MVAS", "stage": "mvas_pre",
    }) == {"rating": 30}
    assert _answer({
        "action": "MVAS", "stage": "mvas_post",
    }) == {"rating": 45}


def test_disposable_http_three_arm_three_visit_acceptance():
    result = run_disposable_http_fulljourney()
    assert result["result"] == "PASS_SYNTHETIC_ONLY"
    assert result["completed_visits"] == 9
    assert result["read_only_smoke"] == "PASS"
    assert result["sqlite_audit"] == "PASS_SYNTHETIC_ONLY"
    assert result["sqlite_integrity"] == "ok"
    assert result["replay_checks"] >= 9
    assert set(result["arms"]) == {"A", "B", "C"}
    for arm in "ABC":
        record = result["arms"][arm]
        assert record["visits"] == 3
        assert record["questions"] == 87
        assert record["mvas"] == 6
        assert 0 <= record["recovery"] <= (6 if arm == "A" else 0)
    assert result["temporary_database_deleted_on_exit"]
    assert not result["human_enrollment_authorized"]
    assert not result["public_https_test"]
    assert not result["production_concurrency_validation"]
