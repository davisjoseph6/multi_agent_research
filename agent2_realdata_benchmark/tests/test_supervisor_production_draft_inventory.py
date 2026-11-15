"""Draft release packages must never impersonate institutional approvals."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat

import pytest

from scripts.supervisor_production_draft_inventory import scaffold, inspect
from src.prototype.pilot_release_evidence_gate import GATES, inspect_evidence_index

COMMIT = "a" * 40


def test_private_placeholder_package_is_explicitly_blocked(tmp_path):
    folder = tmp_path / "private-review"
    result = scaffold(folder, COMMIT)
    assert result["human_enrollment_authorized"] is False
    assert result["evidence_categories"] == len(GATES) == 14
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    manifest = folder / "evidence_index.json"
    assert stat.S_IMODE(manifest.stat().st_mode) == 0o600
    data = json.loads(manifest.read_text())
    assert data["candidate_commit"] == COMMIT
    assert all(x["status"] == "pending" for x in data["records"].values())
    assert all(not (folder / x["path"]).exists() for x in data["records"].values())
    actual = inspect_evidence_index(manifest)
    assert actual["gates_complete"] == 0
    assert actual["human_enrollment_authorized"] is False
    review = inspect(folder)
    assert review["content_review_decision"] == "pending"
    assert review["release_signature_verified"] is False
    assert review["human_enrollment_authorized"] is False
    env = (folder / "configuration/live.env.template").read_text()
    assert "SUPERVISOR_VPS_MODE=staging" in env
    assert "SUPERVISOR_MAIL_TRANSPORT=disabled" in env
    assert "SUPERVISOR_GRAPH_CLIENT_SECRET=<PRIVATE_VAULT_VALUE>" in env
    assert not (folder / "configuration/live.env").exists()
    assert not list(folder.rglob("*.sig"))


def test_rejects_weak_destination_reuse_and_invalid_commit(tmp_path):
    out = tmp_path / "private"
    with pytest.raises(ValueError, match="40-character"):
        scaffold(out, "main")
    scaffold(out, COMMIT)
    with pytest.raises(ValueError, match="unoccupied"):
        scaffold(out, COMMIT)
    with pytest.raises(ValueError, match="absolute"):
        scaffold(Path("relative/review"), COMMIT)
    out.chmod(0o755)
    with pytest.raises(ValueError, match="0700"):
        inspect(out)
    out.chmod(0o700)


def test_no_activation_and_no_secret_mocks(tmp_path):
    folder = tmp_path / "release"
    scaffold(folder, COMMIT)
    contents = "\n".join(
        p.read_text(encoding="utf-8")
        for p in folder.rglob("*")
        if p.is_file()
    )
    assert "DRAFT" in contents
    assert "NOT APPROVED" in contents
    assert "SUPERVISOR_VPS_MODE=staging" in contents
    assert "SUPERVISOR_MAIL_TRANSPORT=disabled" in contents
    assert "SUPERVISOR_MAIL_TRANSPORT=microsoft_graph" in contents
    assert not any(p.suffix.lower()==".pdf" for p in folder.rglob("*"))
