"""Synthetic FIFO experiment only, not a human-system readiness statement."""
import pytest

from scripts.pilot_writer_admission_pair_comparison import (
    compare_writer_admission,
)


def test_synthetic_writer_admission_pair_and_scientific_boundaries():
    report = compare_writer_admission(
        participants=3, workers=3, simulations=41, repetitions=1,
    )
    assert report["result"] == "SYNTHETIC_TESTS_PASSED", report["runs"]
    assert [r["writer_admission"] for r in report["runs"]] == [
        "native", "fifo",
    ]
    assert all(r["result"] == "PASS" for r in report["runs"])
    assert all(r["failures"] == [] for r in report["runs"])
    assert all(r["completed_visits"] == 9 for r in report["runs"])
    assert all(r["pretest_answers"] == 48 for r in report["runs"])
    assert all(r["unique_practice_answers"] == 165 for r in report["runs"])
    assert all(r["posttest_answers"] == 48 for r in report["runs"])
    assert all(r["mvas_responses"] == 18 for r in report["runs"])
    assert all(r["replayed_requests_verified"] > 0 for r in report["runs"])
    assert set(report["summary"]) == {"native", "fifo"}
    assert report["summary"]["fifo"]["paired_runs"] == 1
    assert report["summary"]["native"]["paired_runs"] == 1
    assert report["execution_order_alternates"]
    assert report["writer_queue_process_local_only"]
    assert report["all_databases_new_temporary_and_deleted"]
    assert report["performance_comparison_is_observational"]
    assert not report["human_enrollment_authorized"]
    assert not report["production_performance_approved"]
    assert not report["independent_load_test_performed"]
    assert not report["approved_slo"]


def test_invalid_writer_comparison_rejected():
    for bad in (0, 7, True, -1, 2.3):
        with pytest.raises(ValueError):
            compare_writer_admission(repetitions=bad)
    for bad in (0, 2, 4, 91, True):
        with pytest.raises(ValueError):
            compare_writer_admission(participants=bad)
    for bad in (0, 17, False):
        with pytest.raises(ValueError):
            compare_writer_admission(workers=bad)
    for bad in (0, 40, 241, True):
        with pytest.raises(ValueError):
            compare_writer_admission(simulations=bad)
