"""Process-local FIFO must not be mistaken for multiprocess coordination."""
import pytest

from src.prototype.pilot_multiprocess_writer_probe import run_multiprocess_probe


@pytest.mark.parametrize("mode", ["native", "fifo"])
def test_disposable_shared_sqlite_preserves_count_across_two_processes(mode):
    report = run_multiprocess_probe(
        writer_admission=mode, processes=2, threads_per_process=2,
        operations_per_thread=2, hold_ms=6,
    )
    assert report["result"] == "PASS", report["failures"]
    assert report["expected_updates"] == 8
    assert report["observed_updates"] == 8
    assert report["integrity_ok"]
    assert report["separate_store_per_process"]
    assert report["cross_process_fifo_coordination"] is False
    assert report["journal_mode"] == "DELETE"
    assert not report["human_enrollment_authorized"]
    assert not report["external_https_test"]
    assert not report["production_capacity_established"]
    assert report["multi_process_test_not_a_deployment_solution"]
    for metric in ("total_ms", "entry_ms", "queue_ms",
                   "body_ms", "finalize_ms"):
        values = report["timing_ms"][metric]
        assert 0 <= values["p50"] <= values["p95"] <= values["p99"] <= values["max"]


@pytest.mark.parametrize("changes", [
    {"writer_admission": "unlocked"},
    {"processes": 1},
    {"processes": True},
    {"threads_per_process": 0},
    {"threads_per_process": True},
    {"operations_per_thread": 0},
    {"operations_per_thread": 21},
    {"hold_ms": -1},
    {"hold_ms": 50},
])
def test_invalid_or_unsafe_probe_config_fails_closed(changes):
    with pytest.raises(ValueError):
        run_multiprocess_probe(**changes)
