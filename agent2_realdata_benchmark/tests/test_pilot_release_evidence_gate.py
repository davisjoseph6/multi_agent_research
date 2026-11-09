"""Evidence *index* tests: self-declared metadata never authorizes a person."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from src.prototype.pilot_release_evidence_gate import (
    SCHEMA, GATES, inspect_evidence_index,
)


def create_index(tmp_path, *, approved=False, tamper=None):
    manifest = dict(
        schema_version=SCHEMA,
        candidate_commit="2b1b130dd562d3a4c1faaf09dbc5cca7869f6378"
        if approved else "UNSET",
        records={},
    )
    for key, role in GATES.items():
        record = dict(
            status="pending", path=None, sha256=None,
            reviewer=None, reviewer_role=role, reviewed_at=None,
        )
        if approved:
            document = tmp_path / (key + ".txt")
            document.write_text("FICTIONAL TEST DOCUMENT: " + key)
            record.update(
                status="approved", path=document.name,
                sha256=sha256(document.read_bytes()).hexdigest(),
                reviewer="fictional-test-only",
                reviewed_at="2026-11-09T08:00:00+01:00",
            )
        manifest["records"][key] = record
    if tamper:
        tamper(manifest)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def test_default_manifest_fails_closed_without_evidence(tmp_path):
    path = create_index(tmp_path)
    before = path.read_bytes()
    result = inspect_evidence_index(path)
    assert result["result"] == "BLOCKED_MISSING_EVIDENCE"
    assert result["gates_complete"] == 0
    assert result["gates_required"] == len(GATES) == 14
    assert not result["human_enrollment_authorized"]
    assert result["no_real_participant_software_in_this_branch"]
    assert path.read_bytes() == before


def test_fictional_documents_cannot_grant_human_enrollment(tmp_path):
    path = create_index(tmp_path, approved=True)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = inspect_evidence_index(path)
    assert result["result"] == "INDEX_COMPLETE_EXTERNAL_REVIEW_STILL_REQUIRED"
    assert result["gates_complete"] == 14
    assert result["issues"] == []
    assert not result["human_enrollment_authorized"]
    assert not result["signed_document_authenticity_independently_verified"]
    assert not result["release_approved_by_software"]
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_edited_evidence_file_and_invalid_commit_block(tmp_path):
    path = create_index(tmp_path, approved=True)
    (tmp_path / "final_written_institutional_go.txt").write_text("CHANGED")
    result = inspect_evidence_index(path)
    assert result["result"] == "BLOCKED_MISSING_EVIDENCE"
    assert any("SHA-256 mismatch" in s for s in result["issues"])
    manifest = json.loads(path.read_text())
    manifest["candidate_commit"] = "not-a-commit"
    path.write_text(json.dumps(manifest))
    result = inspect_evidence_index(path)
    assert any("40-character" in s for s in result["issues"])


def test_missing_wrong_role_and_unknown_category_block(tmp_path):
    def tamper(data):
        data["records"]["protocol_and_analysis_plan"]["reviewer_role"] = "student"
        data["records"]["privacy_dpo_and_retention"]["status"] = "pending"
        data["records"]["extra_unexpected"] = dict(status="approved")
    path = create_index(tmp_path, approved=True, tamper=tamper)
    result = inspect_evidence_index(path)
    assert result["gates_complete"] == 12
    assert result["result"] == "BLOCKED_MISSING_EVIDENCE"
    assert any("unexpected evidence categories" in s for s in result["issues"])


def test_path_traversal_and_symlinks_block(tmp_path):
    path = create_index(tmp_path, approved=True)
    manifest = json.loads(path.read_text())
    manifest["records"]["responsible_institution_and_pi"]["path"] = "../outside.txt"
    path.write_text(json.dumps(manifest))
    result = inspect_evidence_index(path)
    assert any("path traversal" in s for s in result["issues"])
    manifest["records"]["responsible_institution_and_pi"]["path"] = "link.txt"
    path.write_text(json.dumps(manifest))
    (tmp_path / "link.txt").symlink_to(
        tmp_path / "responsible_institution_and_pi.txt"
    )
    result = inspect_evidence_index(path)
    assert any("symlink" in s for s in result["issues"])
    outer = tmp_path / "manifest-link.json"
    outer.symlink_to(path)
    with pytest.raises(ValueError):
        inspect_evidence_index(outer)
