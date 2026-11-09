"""Paired comparison is synthetic correctness evidence, never an SLO release."""
import pytest

from scripts.pilot_journal_pair_comparison import compare_journal_modes


def test_paired_journal_comparison_runs_both_modes_with_no_human_authority():
    report = compare_journal_modes(
        participants=3, workers=2, simulations=41, repetitions=1,
    )
    assert report["result"] == "SYNTHETIC_TESTS_PASSED", report["runs"]
    assert len(report["runs"]) == 2
    assert [r["journal_mode"] for r in report["runs"]] == ["delete", "wal"]
    assert all(r["result"] == "PASS" for r in report["runs"])
    assert all(r["completed_visits"] == 9 for r in report["runs"])
    assert all(r["failures"] == [] for r in report["runs"])
    assert report["summary"]["delete"]["pairs"] == 1
    assert report["summary"]["wal"]["pairs"] == 1
    assert report["success_is_not_a_wal_speedup_claim"]
    assert report["not_repeated_identical_planner_randomness"]
    assert report["sqlite_wal_remains_single_writer"]
    assert not report["not_external_https_load"] is False
    assert not report["human_enrollment_authorized"]
    assert not report["production_performance_approved"]
    assert not report["approved_slo"]


def test_paired_journal_comparison_invalid_parameters_fail_closed():
    for repetitions in (0, 7, True, -1, 1.5):
        with pytest.raises(ValueError):
            compare_journal_modes(repetitions=repetitions)
    for participants in (0, 2, 4, 91, True):
        with pytest.raises(ValueError):
            compare_journal_modes(participants=participants)
    for workers in (0, 17, False):
        with pytest.raises(ValueError):
            compare_journal_modes(workers=workers)
    for simulations in (0, 40, 241, True):
        with pytest.raises(ValueError):
            compare_journal_modes(simulations=simulations)
