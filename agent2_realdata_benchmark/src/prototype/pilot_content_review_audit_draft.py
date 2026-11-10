"""Read-only audit of 95 draft items, 32 draft resources and reviewer register.

Checks ID alignment and source/content SHA256. Does NOT validate educational
accuracy, copyright, reviewer independence, signatures or M-VAS psychometrics.
It NEVER authorizes human enrollment, even with all review fields filled.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
import csv
import json

BASE = Path(__file__).resolve().parents[2]
SOURCE = BASE / "docs/rct_candidate_v1"
REVIEW = BASE.parent / "docs/rct_candidate_v1"
REGISTER = REVIEW / "CONTENT_REVIEW_REGISTER_20261108.csv"
ITEMS = SOURCE / "items.csv"
RESOURCES = SOURCE / "resources.csv"
FATIGUE_REHEARSAL = SOURCE / "fatigue_REHEARSAL_ONLY.json"


def _read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("duplicate or missing review CSV headers")
        data = list(reader)
    if not data or any(None in row or None in row.values() for row in data):
        raise ValueError("empty or malformed review data")
    return data


def _sha(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def audit_content_review(
    *, register: Path = REGISTER, items: Path = ITEMS,
    resources: Path = RESOURCES, fatigue: Path = FATIGUE_REHEARSAL,
) -> dict:
    register, items, resources, fatigue = (
        Path(register), Path(items), Path(resources), Path(fatigue)
    )
    rows = _read_rows(register)
    item_rows = _read_rows(items)
    resource_rows = _read_rows(resources)

    expected = {
        ("item", row["item_id"]): (
            row["form"], row["concept"]
        ) for row in item_rows
    }
    expected.update({
        ("resource", row["resource_id"]): (
            row["action"], row["concept"]
        ) for row in resource_rows
    })
    review_ids = [(row["record_type"], row["record_id"]) for row in rows]
    errors = []
    if len(expected) != len(item_rows) + len(resource_rows):
        errors.append("duplicate source item or resource IDs")
    if len(set(review_ids)) != len(review_ids):
        errors.append("duplicate reviewer-register record IDs")
    if set(review_ids) != set(expected):
        errors.append("reviewer register IDs do not match item/resource bank")
    for row in rows:
        key = (row["record_type"], row["record_id"])
        if key in expected and expected[key] != (
            row["form_or_action"], row["concept"]
        ):
            errors.append("reviewer record action/form or concept mismatch")
            break
    if len(item_rows) != 95 or len(resource_rows) != 32:
        errors.append("unexpected 95-item/32-resource bank size")
    if Counter(r["form"] for r in item_rows) != {
        "pretest": 16, "posttest": 16,
        "practice": 55, "recovery_drop2": 8,
    }:
        errors.append("unexpected independent pre/post/practice/recovery composition")

    pending = [
        (row["record_type"], row["record_id"]) for row in rows
        if row["final_decision"].strip().lower() != "approved"
    ]
    incomplete = [
        (row["record_type"], row["record_id"]) for row in rows
        if not all(row.get(k, "").strip() for k in (
            "reviewer_1", "reviewer_1_date", "reviewer_1_decision",
            "reviewer_2", "reviewer_2_date", "reviewer_2_decision",
            "answer_or_claim_correctness", "clarity", "concept_coverage",
            "source_permission", "language_accessibility",
            "final_decision", "approval_evidence_link",
        ))
    ]
    fatigue_data = json.loads(fatigue.read_text(encoding="utf-8"))
    unvalidated = fatigue_data.get("review_decision") != "approved" or (
        "REHEARSAL_ONLY" in fatigue_data.get("version", "")
    )
    # Even approved paper entries and an approved questionnaire file alone
    # cannot authenticate the reviewers or prove correct measurement choices.
    return {
        "kind": "IJCAI2027_READONLY_CONTENT_REVIEW_AUDIT_DRAFT",
        "result": "BLOCKED" if pending or incomplete or errors or unvalidated
                  else "REVIEW_METADATA_PRESENT_EXTERNAL_VERIFICATION_REQUIRED",
        "review_register_rows": len(rows),
        "items": len(item_rows),
        "resources": len(resource_rows),
        "independent_assessment_items": sum(
            x["form"] in ("pretest", "posttest") for x in item_rows
        ),
        "review_pending": len(pending),
        "review_metadata_incomplete": len(incomplete),
        "review_alignment_errors": errors,
        "rehearsal_fatigue_item_count": len(fatigue_data.get("items", [])),
        "rehearsal_fatigue_is_not_approved_single_item_mvas": True,
        "files_sha256": {
            "review_register": _sha(register),
            "items": _sha(items),
            "resources": _sha(resources),
            "rehearsal_fatigue": _sha(fatigue),
        },
        "independent_review_signature_authenticated": False,
        "instrument_wording_and_digital_validity_approved": False,
        "human_enrollment_authorized": False,
        "note": (
            "Metadata and asset alignment only; external subject expert, "
            "copyright, psychometric, language and signature verification "
            "are mandatory. No personal or participant data."
        ),
    }
