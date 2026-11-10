"""End-to-end one-file synthetic study regression (not human RCT readiness)."""
from __future__ import annotations

import pytest

from scripts.pilot_unified_sqlite_rehearsal import run_unified


def test_nine_fictional_people_and_complete_three_visit_restart_rehearsal():
    report = run_unified(participants=9, simulations=41)
    assert report["result"] == "PASS_SYNTHETIC_ONLY"
    assert report["fictional_participants"] == 9
    assert report["fictional_completed_visits"] == 27
    assert report["fictional_questions"] == 9 * 87
    assert report["fictional_mvas_records"] == 9 * 6
    assert report["fictional_replay_checks"] >= 9
    assert sum(report["allocation_by_arm"].values()) == 9
    assert all(report["allocation_by_arm"].get(arm, 0) > 0 for arm in "ABC")
    assert report["sqlite_integrity"] == "ok"
    assert report["unified_audit"] == "PASS_SYNTHETIC_ONLY"
    assert report["single_sqlite_file"]
    assert report["atomic_provisioning_and_visit_boundaries"]
    assert report["crash_restart_reopen_checks"] == 3
    assert report["data_deleted_on_exit"]
    assert report["no_network_requests"]
    assert not report["human_enrollment_authorized"]
    assert not report["staff_authentication_real"]
    assert not report["consent_or_instrument_reviewed"]
    assert not report["independent_security_review"]


@pytest.mark.parametrize("participants", [0, 1, 8, 91, -9, True, 9.0, "9"])
def test_reject_invalid_synthetic_participant_counts(participants):
    with pytest.raises(ValueError):
        run_unified(participants=participants)


@pytest.mark.parametrize("simulations", [0, 40, 241, True, 41.0, "41"])
def test_reject_invalid_synthetic_simulation_budget(simulations):
    with pytest.raises(ValueError):
        run_unified(simulations=simulations)
