"""Disconnected synthetic admission-to-learning integration regression tests."""
from __future__ import annotations

import pytest

from scripts.pilot_integrated_synthetic_journey import run_integrated
from src.prototype.pilot_admission_controls_draft import AdmissionDenied


def test_full_concealed_synthetic_admission_and_learning_nine_records():
    report = run_integrated(participants=9, simulations=41)
    assert report["result"] == "PASS_SYNTHETIC_ONLY"
    assert report["fictional_participants"] == 9
    assert report["fictional_completed_visits"] == 27
    assert report["fictional_questions"] == 9 * (16 + 55 + 16)
    assert report["fictional_mvas_records"] == 9 * 6
    assert report["fictional_replay_checks"] >= 9
    assert set(report["allocated_by_arm"]) == {"A", "B", "C"}
    assert sum(report["allocated_by_arm"].values()) == 9
    assert report["admission_audit"] == "PASS_SYNTHETIC_ONLY"
    assert report["learning_audit"] == "PASS_SYNTHETIC_ONLY"
    assert report["no_client_supplied_arm"]
    assert report["no_network_requests"]
    assert report["temporary_stores_deleted"]
    assert not report["human_enrollment_authorized"]
    assert not report["staff_authentication_real"]
    assert not report["consent_or_measurement_validated"]
    assert not report["cross_database_atomicity"]


@pytest.mark.parametrize("participants", [0, 1, 3, 8, 91, -1, True, 9.0, "9"])
def test_invalid_integrated_fixture_counts_fail_closed(participants):
    with pytest.raises(ValueError):
        run_integrated(participants=participants)


@pytest.mark.parametrize("simulations", [0, 40, 241, True, 41.0, "41"])
def test_invalid_simulations_fail_closed(simulations):
    with pytest.raises(ValueError):
        run_integrated(simulations=simulations)
