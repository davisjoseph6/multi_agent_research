"""Both modes must keep complete fictional study records correct across processes."""
import pytest

from src.prototype.pilot_multiprocess_full_journey_rehearsal import (
    run_multiprocess_full_journey,
)


@pytest.mark.parametrize("mode", ("native", "fifo"))
def test_two_processes_complete_six_students_all_arms_without_double_scoring(mode):
    report = run_multiprocess_full_journey(
        participants=6, processes=2, threads_per_process=2,
        simulations=41, writer_admission=mode,
    )
    assert report["result"] == "PASS", report["failures"]
    assert report["sqlite_integrity_ok"]
    assert report["completed_by_arm"] == {"A": 2, "B": 2, "C": 2}
    assert report["completed_visits"] == 18
    assert report["pretest_answers"] == 96
    assert report["practice_answers"] == 330
    assert report["posttest_answers"] == 96
    assert report["mvas_responses"] == 36
    assert report["recovery_actions"] <= 12
    assert report["replays_verified"] > 0
    assert report["action_calls"] == 6 * 93 + report["recovery_actions"]
    assert report["persisted_requests"] == report["action_calls"]
    assert report["separate_store_per_process"]
    assert not report["cross_process_fifo_coordination"]
    assert not report["human_enrollment_authorized"]
    assert not report["real_student_identity_or_consent"]
    assert not report["external_https_load"]
    assert not report["independent_security_accessibility_qa"]
    assert report["not_production_capacity_certificate"]


def test_invalid_full_study_multiprocess_config_fails_before_db_creation():
    invalid = (
        {"processes": 1}, {"processes": 5}, {"processes": True},
        {"participants": 3}, {"participants": 7}, {"participants": 91},
        {"participants": True},
        {"threads_per_process": 0}, {"threads_per_process": 5},
        {"threads_per_process": False},
        {"simulations": 40}, {"simulations": 241},
        {"simulations": True}, {"writer_admission": "none"},
    )
    for changes in invalid:
        with pytest.raises(ValueError):
            run_multiprocess_full_journey(**changes)
