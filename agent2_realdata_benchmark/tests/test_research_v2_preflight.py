"""Public two-language release gate remains closed on original candidate content."""
from pathlib import Path

from scripts.research_v2_preflight import ROOT, preflight


def test_existing_95_question_bank_cannot_release_three_period_fr_en_study():
    report = preflight(ROOT / "items.csv")
    assert report["result"] == "BLOCKED_NOT_APPROVED"
    assert report["english_bank_question_rows"] == 95
    assert report["english_bank_distinct_ids"] == 95
    assert report["minimum_distinct_question_rows"] == 261
    assert report["english_bank_forms"] == {
        "posttest": 16,
        "practice": 55,
        "pretest": 16,
        "recovery_drop2": 8,
    }
    assert report["french_bank_fully_reviewed_rows"] == 0
    assert any("261" in x for x in report["blockers"])
    assert any("French" in x for x in report["blockers"])
    assert not report["human_enrollment_authorized"]
    assert not report["changes_to_vps_services"]
