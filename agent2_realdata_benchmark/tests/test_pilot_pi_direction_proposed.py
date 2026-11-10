"""Supervisor's proposed scientific direction is not a signed release."""
import json
from pathlib import Path

from src.prototype.pilot_feasibility_reporting_draft import (
    summarize_synthetic_feasibility,
)


DOCS = Path(__file__).resolve().parents[2] / "docs"
R = DOCS / "rct_candidate_v1"


def test_supervisor_draft_is_proposal_only_with_six_fatigue_measurements():
    direction = json.loads(
        (R / "PI_FEASIBILITY_DIRECTION_PROPOSED_20261110.json").read_text()
    )
    assert direction["status"].endswith("NOT_INSTITUTIONALLY_APPROVED")
    assert direction["target_initial_enrollment"] == 90
    assert direction["target_initial_enrollment_pending_power_and_feasibility_review"]
    assert direction["study_type"].endswith("_PROPOSED")
    assert set(direction["arms"]) == {"A", "B", "C"}
    assert direction["fatigue_instrument"]["ratings_per_student"] == 6
    assert direction["fatigue_instrument"]["ratings_per_visit"] == 2
    assert len(direction["primary_feasibility_domains"]) == 6
    for field in (
        "final_signed_scientific_protocol", "independent_statistical_approval",
        "research_institution_authorization", "ethics_review_determined",
        "dpo_review_determined", "content_and_instrument_review_complete",
        "human_enrollment_authorized",
    ):
        assert direction[field] is False
    assert direction["fatigue_instrument"]["exact_item_wording_approved"] is False


def test_release_approval_manifest_does_not_change_on_supervisor_message():
    manifest = json.loads(
        (DOCS / "pilot_release_evidence" / "MANIFEST_TEMPLATE.json").read_text()
    )
    assert len(manifest["records"]) == 14
    assert all(r["status"] == "pending" for r in manifest["records"].values())
    assert manifest["candidate_commit"] == "UNSET"


def test_fictional_90_person_example_reports_proposed_feasibility_only():
    payload = json.loads(
        (R / "EXAMPLE_FICTIONAL_FEASIBILITY_COUNTS.json").read_text()
    )
    report = summarize_synthetic_feasibility(payload)
    assert report["overall"]["protocol_completion_among_randomized"][
        "denominator"
    ] == 90
    assert report["overall"]["protocol_completion_among_randomized"][
        "numerator"
    ] == 75
    assert report["result"] == "DESCRIPTIVE_SYNTHETIC_ONLY"
    assert report["human_enrollment_authorized"] is False
    assert report["progression_criteria_signed_and_frozen"] is False
    protocol = (R / "PILOT_PROTOCOL_V0_2_PI_PROPOSAL_20261110.md").read_text()
    assert "NASA-TLX" in protocol and "M-VAS" in protocol
    assert "Aivancity" in protocol
    assert "DO NOT RECRUIT" in protocol
