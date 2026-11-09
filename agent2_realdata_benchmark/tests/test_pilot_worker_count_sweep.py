"""Worker-count sensitivity experiments cannot authorize a human pilot."""
from __future__ import annotations

import pytest

from scripts import pilot_worker_count_sweep as sweep


def test_parse_worker_counts_rejects_duplicate_missing_or_invalid():
    assert sweep.parse_worker_counts("1, 2,3,5") == (1, 2, 3, 5)
    for bad in ("", "1", "1,1", "0,1", "1,17", "1,x", "1,,2"):
        with pytest.raises(ValueError):
            sweep.parse_worker_counts(bad)


def test_repetition_order_alternates_forward_and_reverse():
    counts = (1, 2, 3, 5)
    assert sweep.order_for_repetition(counts, 0) == counts
    assert sweep.order_for_repetition(counts, 1) == (5, 3, 2, 1)
    assert sweep.order_for_repetition(counts, 2) == counts


def test_aggregate_medians_are_per_run_and_no_details_leak(monkeypatch):
    called = []

    def fictional_runner(*, participants, workers, simulations):
        called.append(workers)
        return {
            "workers": workers,
            "result": "PASS",
            "failures": [],
            "completed_participants": participants,
            "completed_visits": 3 * participants,
            "action_calls": 100,
            "wall_seconds": workers * 10,
            "actions_over_1000ms": workers,
            "latency_ms": dict(p50=10, p95=workers*10, p99=workers*20,
                               max=workers*30),
            "sqlite_phase_latency_ms": {
                "sqlite_begin_total_ms": {"p99": workers*15},
                "sqlite_body_total_ms": {"p99": workers},
                "sqlite_finalize_total_ms": {"p99": workers*2},
            },
            "private_token": "DO_NOT_INCLUDE_THIS",
        }

    monkeypatch.setattr(sweep, "run_full_journey_rehearsal", fictional_runner)
    report = sweep.run_sweep(
        participants=3, simulations=41, workers=(1, 2), repetitions=2,
    )
    assert called == [1, 2, 2, 1]
    assert report["result"] == "PASS"
    assert report["journal_mode"] == "DELETE_default_no_WAL_change"
    assert report["summary"]["2"]["median_of_run_metrics"]["action_p99_ms"] == 40
    assert report["summary"]["2"]["run_count"] == 2
    assert report["fictional_only"]
    assert not report["human_enrollment_authorized"]
    assert not report["external_https_load"]
    assert not report["production_capacity_established"]
    assert "DO_NOT_INCLUDE_THIS" not in str(report)
    assert not any("private_token" in r for r in report["runs"])


def test_run_sweep_input_validation_without_running_workload():
    configs = [
        {"participants": 4}, {"participants": True},
        {"simulations": 40}, {"simulations": False},
        {"workers": (1,)}, {"workers": (1, 1)},
        {"workers": (1, True)}, {"workers": (0, 2)},
        {"repetitions": 0}, {"repetitions": True},
        {"repetitions": 10, "workers": (1, 2, 3, 4, 5)},
    ]
    for kwargs in configs:
        with pytest.raises(ValueError):
            sweep.run_sweep(**kwargs)


def test_tiny_real_fictional_sweep_preserves_all_three_arms():
    report = sweep.run_sweep(
        participants=3, simulations=41, workers=(1, 2), repetitions=1,
    )
    assert report["result"] == "PASS"
    assert len(report["runs"]) == 2
    assert all(x["completed"] == 3 and x["completed_visits"] == 9
               for x in report["runs"])
    assert all(x["action_calls"] >= 279 for x in report["runs"])
    assert all(x["passed"] for x in report["runs"])
    assert "not a pooled" in report["interpretation_limits"]
