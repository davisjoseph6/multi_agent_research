"""High-level synthetic admission and three-visit disposable acceptance."""
import pytest

from scripts.pilot_admission_offline_rehearsal import run_rehearsal


@pytest.mark.parametrize("count", [3, 30])
def test_complete_offline_synthetic_admission_visits_and_restore(count):
    result = run_rehearsal(participants=count)
    assert result["result"] == "PASS_SYNTHETIC_ONLY"
    assert result["fictional_participants"] == count
    assert result["fictional_started_visits"] == count * 3
    assert result["fictional_completed_visits"] == count * 3
    assert result["concealed_assignment_records"] == count
    assert result["audit"] == result["restore_audit"] == "PASS_SYNTHETIC_ONLY"
    assert result["backup"] == "PASS_SYNTHETIC_BACKUP_ONLY"
    assert result["sqlite_integrity"] == "ok"
    assert result["temporary_files_deleted_on_exit"]
    assert result["no_network_requests"]
    assert result["no_real_participant_data"]
    assert not result["human_enrollment_authorized"]
    assert not result["staff_identity_verified"]
    assert not result["external_review_or_approval"]


@pytest.mark.parametrize("participants", [0, 1, 2, 91, -1, True, 3.0, "30"])
def test_fictional_admission_rehearsal_rejects_invalid_capacity(participants):
    with pytest.raises(ValueError):
        run_rehearsal(participants=participants)
