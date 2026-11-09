"""Complete three-visit fictional study load is not a human RCT."""
import pytest

from src.prototype.pilot_full_journey_rehearsal import run_full_journey_rehearsal


def test_parallel_complete_three_visits_all_arms_with_six_fatigue_measurements():
    report = run_full_journey_rehearsal(
        participants=3, workers=3, simulations=41,
    )
    assert report["result"] == "PASS", report["failures"]
    assert report["completed_participants"] == 3
    assert report["completed_by_arm"] == {"A": 1, "B": 1, "C": 1}
    assert report["completed_visits"] == 9
    assert report["pretest_answers"] == 3 * 16
    assert report["unique_practice_answers"] == 3 * 55
    assert report["posttest_answers"] == 3 * 16
    assert report["mvas_responses"] == 3 * 6
    assert report["action_calls"] == 3 * 93 + report["recovery_actions"]
    assert report["recovery_actions"] <= 6
    assert report["replayed_requests_verified"] > 0
    assert not report["human_enrollment_authorized"]
    assert not report["external_https_load"]
    assert not report["approved_latency_thresholds"]
    assert not report["independent_research_qa"]
    assert report["not_scientific_validation"]
    assert not report["real_world_calendar_test"]
    assert report["latency_ms"]["p50"] >= 0
    assert set(report["per_arm_latency"]) == {"A", "B", "C"}
    assert set(report["per_visit_latency"]) == {"1", "2", "3"}
    assert sum(entry["count"] for entry in report["per_arm_latency"].values()) == report["action_calls"]
    assert sum(entry["count"] for entry in report["per_visit_latency"].values()) == report["action_calls"]
    for key in (
        "next_ms", "render_ms", "submit_ms",
        "sqlite_begin_next_ms", "sqlite_begin_render_ms",
        "sqlite_begin_submit_ms", "sqlite_begin_total_ms",
    ):
        metrics = report["sqlite_phase_latency_ms"][key]
        assert 0 <= metrics["p50"] <= metrics["p95"] <= metrics["p99"] <= metrics["max"]
    assert report["actions_over_1000ms"] <= report["actions_over_250ms"]
    assert len(report["slowest_10_actions"]) == 10
    assert all(
        "pid" not in entry and "participant_id" not in entry
        for entry in report["slowest_10_actions"]
    )
    assert all(
        entry["sqlite_begin_total_ms"] <= entry["action_roundtrip_ms"] + .02
        for entry in report["slowest_10_actions"]
    )


def test_three_visit_load_rejects_unbalanced_or_invalid_configs():
    for invalid in (0, 1, 2, 4, 91, -3, True):
        with pytest.raises(ValueError):
            run_full_journey_rehearsal(participants=invalid)
    for invalid in (0, 17, False):
        with pytest.raises(ValueError):
            run_full_journey_rehearsal(workers=invalid)
    for invalid in (0, 40, 241, True):
        with pytest.raises(ValueError):
            run_full_journey_rehearsal(simulations=invalid)



def test_full_journey_phase_attribution_does_not_claim_real_study_slo():
    report = run_full_journey_rehearsal(
        participants=3, workers=2, simulations=41,
    )
    assert report["result"] == "PASS", report["failures"]
    assert report["completed_visits"] == 9
    assert report["action_calls"] == 279 + report["recovery_actions"]
    assert report["per_arm_latency"]["A"]["count"] >= 93
    assert report["per_arm_latency"]["B"]["count"] == 93
    assert report["per_arm_latency"]["C"]["count"] == 93
    assert "does not separately measure lock wait" in (
        report["sqlite_entry_timing_limitations"]
    )
    assert not report["approved_latency_thresholds"]
    assert not report["external_https_load"]
    assert not report["human_enrollment_authorized"]



def test_full_journey_diagnoses_writer_hold_without_changing_store_semantics():
    report = run_full_journey_rehearsal(
        participants=3, workers=2, simulations=41,
    )
    assert report["result"] == "PASS", report["failures"]
    for phase in (
        "sqlite_body_next_ms", "sqlite_body_render_ms",
        "sqlite_body_submit_ms", "sqlite_body_total_ms",
        "sqlite_finalize_next_ms", "sqlite_finalize_render_ms",
        "sqlite_finalize_submit_ms", "sqlite_finalize_total_ms",
    ):
        metrics = report["sqlite_phase_latency_ms"][phase]
        assert 0 <= metrics["p50"] <= metrics["p95"] <= metrics["p99"] <= metrics["max"]
    assert report["sqlite_phase_latency_ms"]["sqlite_body_next_ms"]["max"] >= 0
    for observation in report["slowest_10_actions"]:
        # Entry, work under RESERVED writer lock, and commit/close are
        # entirely inside next/render/submit completion.
        components = (
            observation["sqlite_begin_total_ms"]
            + observation["sqlite_body_total_ms"]
            + observation["sqlite_finalize_total_ms"]
        )
        assert components <= observation["action_roundtrip_ms"] + 0.1
        assert "pid" not in observation
        assert "participant_id" not in observation
    assert "process scheduling" in report["sqlite_writer_hold_timing_limitations"]
    assert report["fictional_only"]
    assert not report["human_enrollment_authorized"]
    assert not report["external_https_load"]
    assert not report["approved_latency_thresholds"]



def test_fifo_writer_admission_preserves_full_three_arm_fictional_journey():
    """FIFO wraps transactions only; state transitions and budgets unchanged."""
    report = run_full_journey_rehearsal(
        participants=3, workers=3, simulations=41, writer_admission="fifo",
    )
    assert report["result"] == "PASS", report["failures"]
    assert report["writer_admission"] == "fifo"
    assert report["completed_participants"] == 3
    assert report["completed_by_arm"] == {"A": 1, "B": 1, "C": 1}
    assert report["completed_visits"] == 9
    assert report["pretest_answers"] == 48
    assert report["unique_practice_answers"] == 165
    assert report["posttest_answers"] == 48
    assert report["mvas_responses"] == 18
    assert report["replayed_requests_verified"] > 0
    assert report["experimental_in_process_only"]
    assert report["writer_queue_not_cross_process"]
    for key in (
        "writer_queue_wait_next_ms", "writer_queue_wait_render_ms",
        "writer_queue_wait_submit_ms", "writer_queue_wait_total_ms",
    ):
        metric = report["sqlite_phase_latency_ms"][key]
        assert 0 <= metric["p50"] <= metric["p95"] <= metric["p99"] <= metric["max"]
    assert not report["human_enrollment_authorized"]
    assert not report["approved_latency_thresholds"]
    assert not report["external_https_load"]


def test_native_is_unchanged_and_invalid_admission_fails_closed():
    native = run_full_journey_rehearsal(
        participants=3, workers=2, simulations=41,
    )
    assert native["result"] == "PASS", native["failures"]
    assert native["writer_admission"] == "native"
    assert native["sqlite_phase_latency_ms"][
        "writer_queue_wait_total_ms"
    ]["max"] == 0
    for bad in ("FIFO", "unlocked", "wal", "", None, 1, False):
        with pytest.raises(ValueError):
            run_full_journey_rehearsal(writer_admission=bad)



def test_fifo_writer_ticket_released_on_rollback_and_no_duplicate_action(tmp_path):
    """Queue cleanup survives exceptions; pending-action semantics remain SQL."""
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    from src.prototype.pilot_full_journey_rehearsal import (
        _FIFOMeasuredSyntheticStore,
    )

    content = Path(__file__).resolve().parents[1] / "docs/rct_candidate_v1"
    store = _FIFOMeasuredSyntheticStore(
        tmp_path / "fifo_rollback.sqlite3",
        items_path=content / "items.csv",
        resources_path=content / "resources.csv",
        simulations=41,
    )
    with pytest.raises(RuntimeError):
        with store._transaction():
            raise RuntimeError("forced rollback in disposable test")

    at = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    pid = store.new_synthetic_participant(arm="B", at=at)
    store.start_supervised_visit(
        pid, visit=1, at=at,
        offline_staff_authorized=True,
        synthetic_release_authorized=True,
    )
    next_at = at + timedelta(seconds=1)
    with ThreadPoolExecutor(max_workers=4) as pool:
        actions = list(pool.map(
            lambda _: store.next_action(pid, at=next_at), range(4),
        ))
    assert all(item == actions[0] for item in actions)
    assert actions[0]["action"] == "QUESTION"
    assert store.snapshot(pid)["completed_actions"] == 0
    assert not store.snapshot(pid)["approved_for_humans"]
