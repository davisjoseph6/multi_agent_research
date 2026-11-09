"""Fail-closed, OFFLINE inspection of a *private* pilot release-evidence index.

IMPORTANT: A passing index is NOT ethics approval, a cryptographic
verification of a signatory, or permission to enroll humans. The actual RCT
candidate intentionally has no human enrollment implementation or release
authorization path here. This module NEVER imports or modifies the running
software, participant database, VPS configuration or human identities.

Private evidence documents and the filled manifest must stay OUTSIDE Git.
Use SHA256 to bind each locally submitted artifact; authorized supervisors
and institutional reviewers must still independently verify authenticity.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from hmac import compare_digest
import json
from pathlib import Path
import re

SCHEMA = "IJCAI2027_PILOT_EVIDENCE_INDEX_V1"
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
GATES = {
    "responsible_institution_and_pi": "institutional_authority",
    "ethics_determination_and_approval": "ethics_authority",
    "privacy_dpo_and_retention": "dpo",
    "protocol_and_analysis_plan": "pi_and_statistician",
    "power_and_feasibility": "statistician",
    "item_resource_and_mvas_approval": "content_and_measurement_reviewers",
    "student_information_consent_language": "institutional_authority",
    "eligibility_recruitment_and_scheduling": "pi",
    "concealed_allocation_and_role_access": "independent_qa",
    "source_build_test_and_migration": "engineering_reviewer",
    "independent_security_and_accessibility": "independent_qa",
    "production_tls_load_device_monitoring": "operations_reviewer",
    "backup_restore_recovery_drills": "operations_reviewer",
    "final_written_institutional_go": "institutional_authority",
}


def _check_record(root: Path, name: str, record) -> list[str]:
    issues = []
    if type(record) is not dict:
        return ["missing evidence record"]
    if record.get("status") != "approved":
        issues.append("not marked approved")
    if record.get("reviewer_role") != GATES[name]:
        issues.append("required reviewer role not documented")
    reviewer = record.get("reviewer")
    if type(reviewer) is not str or len(reviewer.strip()) < 3:
        issues.append("reviewer name/identifier missing")
    date = record.get("reviewed_at")
    if type(date) is not str:
        issues.append("review timestamp missing")
    else:
        try:
            when = datetime.fromisoformat(date)
            if when.tzinfo is None or when.utcoffset() is None:
                issues.append("review timestamp must include timezone")
        except ValueError:
            issues.append("invalid review timestamp")
    digest = record.get("sha256")
    if type(digest) is not str or SHA_RE.fullmatch(digest) is None:
        issues.append("invalid/missing evidence SHA-256")
    rel = record.get("path")
    if type(rel) is not str or not rel.strip() or Path(rel).is_absolute():
        issues.append("missing or absolute evidence path")
        return issues
    path = Path(rel)
    if any(part in ("..", ".") for part in path.parts):
        issues.append("path traversal is forbidden")
        return issues
    candidate = root / path
    if not candidate.is_file() or candidate.is_symlink():
        issues.append("evidence file absent or symlink")
        return issues
    try:
        if not candidate.resolve().is_relative_to(root.resolve()):
            issues.append("evidence file escapes evidence directory")
            return issues
        h = sha256()
        with candidate.open("rb") as handle:
            for data in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(data)
        if type(digest) is str and SHA_RE.fullmatch(digest) and not compare_digest(h.hexdigest(), digest):
            issues.append("evidence file SHA-256 mismatch")
    except OSError:
        issues.append("evidence file not readable")
    return issues


def inspect_evidence_index(index_path: str | Path) -> dict:
    """Never returns a "human enrollment authorized" response.

    Accepts only an existing, nonsymlink private JSON index. All referenced
    evidence must be in the same directory or its subdirectories. Unknown
    evidence keys block completion; otherwise missing statuses/hashes/roles
    are listed separately. This is a *document inventory*, not verification
    that a self-declared reviewer is genuine.
    """
    path = Path(index_path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("existing nonsymlink evidence manifest required")
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if type(raw) is not dict or raw.get("schema_version") != SCHEMA:
        raise ValueError("unrecognized release evidence schema")
    records = raw.get("records")
    if type(records) is not dict:
        raise ValueError("evidence records must be an object")
    issues = []
    commit = raw.get("candidate_commit")
    if type(commit) is not str or COMMIT_RE.fullmatch(commit) is None:
        issues.append("candidate_commit: exact 40-character source SHA required")
    unknown = sorted(set(records) - set(GATES))
    if unknown:
        issues.append("unexpected evidence categories: " + ", ".join(unknown))
    checks = {}
    for key in GATES:
        errors = _check_record(path.parent, key, records.get(key))
        checks[key] = {"indexed": not errors, "issues": errors}
        issues.extend(f"{key}: {error}" for error in errors)
    return {
        "schema_version": SCHEMA,
        "result": "INDEX_COMPLETE_EXTERNAL_REVIEW_STILL_REQUIRED"
        if not issues else "BLOCKED_MISSING_EVIDENCE",
        "candidate_commit": commit if type(commit) is str and COMMIT_RE.fullmatch(commit) else None,
        "checks": checks,
        "gates_complete": sum(v["indexed"] for v in checks.values()),
        "gates_required": len(GATES),
        "issues": issues,
        "signed_document_authenticity_independently_verified": False,
        "human_enrollment_authorized": False,
        "release_approved_by_software": False,
        "no_real_participant_software_in_this_branch": True,
    }
