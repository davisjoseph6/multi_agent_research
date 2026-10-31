"""Fictional interruption and SQLite restore drill."""
from scripts.rct_restore_drill import drill


def test_pending_action_restores_without_duplicate_and_journey_finishes():
    result=drill()
    assert result["passed"]
    assert result["pending_action_preserved"]
    assert result["previous_database_not_modified_by_restore"]
    assert result["outcome_pretest_answered"]==16
    assert result["outcome_posttest_answered"]==16
    assert result["pending_actions_after_restore"]==0
    assert len(result["backup_sha256"])==64
    assert not result["production_disaster_recovery_verified"]
