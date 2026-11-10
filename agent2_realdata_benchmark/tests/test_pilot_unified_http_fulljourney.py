"""Real loopback HTTP integration for all three blinded fictional treatments."""
from __future__ import annotations

from pathlib import Path

from scripts.pilot_unified_http_fulljourney import run_fulljourney


def test_all_three_real_http_fictional_journeys_are_complete_and_auditable():
    report = run_fulljourney()
    assert report["result"] == "PASS_SYNTHETIC_ONLY"
    assert report["fictional_displayed_participants"] == 3
    assert report["fictional_cohort_records"] == 9
    assert report["completed_fictional_visits"] == 9
    assert report["completed_questions"] == 261
    assert report["proposed_mvas_responses"] == 18
    assert report["retry_replays"] >= 9
    assert report["http_smoke_checks"] == 18
    assert report["read_only_completion_audit"] == "PASS_SYNTHETIC_ONLY"
    assert report["all_three_finished"]
    assert report["temporary_sqlite_removed_on_exit"]
    assert report["single_sqlite_file"]
    assert report["network_scope"] == "EPHEMERAL_LOOPBACK_HTTP_ONLY"
    assert not report["human_enrollment_authorized"]
    assert not report["real_browser_accessibility_test"]
    assert not report["production_security_certification"]


def test_fulljourney_never_connects_to_vps_or_accepts_human_database():
    code = (
        Path(__file__).resolve().parents[1]
        / "scripts" / "pilot_unified_http_fulljourney.py"
    ).read_text(encoding="utf-8")
    assert 'make_server("127.0.0.1", port, app' in code
    assert 'with TemporaryDirectory(prefix=' in code
    assert "http://31." not in code
    assert "ijcai_unified_browser_20261110/state" not in code
    assert "human_enrollment_authorized" in code
