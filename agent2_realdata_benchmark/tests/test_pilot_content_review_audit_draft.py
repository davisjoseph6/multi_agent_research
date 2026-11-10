"""Mechanical 95/32 reviewer register audit is not independent review."""
import csv
from pathlib import Path

from src.prototype.pilot_content_review_audit_draft import (
    ITEMS, REGISTER, RESOURCES, audit_content_review,
)


def test_current_register_and_unvalidated_fatigue_remain_blocked():
    report = audit_content_review()
    assert report["result"] == "BLOCKED"
    assert report["review_register_rows"] == 127
    assert report["items"] == 95
    assert report["resources"] == 32
    assert report["independent_assessment_items"] == 32
    assert report["review_pending"] == 127
    assert report["review_metadata_incomplete"] == 127
    assert report["review_alignment_errors"] == []
    assert report["rehearsal_fatigue_item_count"] == 6
    assert report["rehearsal_fatigue_is_not_approved_single_item_mvas"]
    assert report["independent_review_signature_authenticated"] is False
    assert report["human_enrollment_authorized"] is False
    for val in report["files_sha256"].values():
        assert len(val) == 64
        assert all(c in "0123456789abcdef" for c in val)


def test_register_mismatched_content_is_detected(tmp_path):
    rows = []
    with REGISTER.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)
    assert headers
    rows[0]["concept"] = "wrong concept"
    altered = tmp_path / "altered_register.csv"
    with altered.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)
    report = audit_content_review(register=altered)
    assert "reviewer record action/form or concept mismatch" in (
        report["review_alignment_errors"]
    )
    assert not report["human_enrollment_authorized"]


def test_register_duplicate_and_missing_rows_rejected(tmp_path):
    with REGISTER.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)
    assert headers
    altered = tmp_path / "duplicate_register.csv"
    rows[-1] = rows[0].copy()
    with altered.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)
    report = audit_content_review(register=altered)
    assert "duplicate reviewer-register record IDs" in report[
        "review_alignment_errors"
    ]
    assert "reviewer register IDs do not match item/resource bank" in report[
        "review_alignment_errors"
    ]
