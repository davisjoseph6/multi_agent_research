"""Review-document completeness only; does not validate PI approval."""
import json
from pathlib import Path


DOCS = Path(__file__).resolve().parents[2] / "docs/rct_candidate_v1"
IDS = {f"SUP-{i:02d}" for i in range(1, 15)}


def test_public_supervisor_decision_template_is_explicitly_unapproved():
    raw = json.loads(
        (DOCS / "SUPERVISOR_ALIGNMENT_DECISIONS_TEMPLATE.json").read_text()
    )
    assert raw["schema_version"].endswith("_V1")
    assert raw["document_status"] == "UNAPPROVED_PUBLIC_TEMPLATE"
    assert set(raw["decisions"]) == IDS
    assert not raw["pi_approved"]
    assert not raw["institutionally_authorized"]
    assert not raw["human_enrollment_authorized"]
    for decision in raw["decisions"].values():
        assert decision["status"] == "unresolved"
        assert decision["pi_decision"] is None
        assert decision["review_evidence_sha256"] is None


def test_each_unresolved_protocol_difference_is_in_crosswalk():
    text = (
        DOCS / "SUPERVISOR_BRIEF_PROTOCOL_CROSSWALK_20261110.md"
    ).read_text()
    for item in IDS:
        assert f"| {item} |" in text
    assert "NASA-TLX" in text
    assert "M-VAS" in text
    assert "POMCP" in text
    assert "BKT" in text
    assert "75" in text and "90" in text
    assert "NO" in text.upper() or "NOT approved" in text
