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
