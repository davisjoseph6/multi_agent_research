"""Tests ensure the triage is read-only and does not grant completion."""
import csv
from pathlib import Path

import pytest
from scripts.step72_123_weekend_triage import (
    build_snapshot, load_register, render_markdown, main,
)


def fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repository"
    root = repo / "agent2_realdata_benchmark"
    (root / "docs").mkdir(parents=True)
    (root / "scripts").mkdir()
    keys = ["step", "requirement", "evidence_status", "evidence_credit", "existing_evidence", "exit_criterion", "accountable_owner", "evidence_reference", "independent_signoff"]
    with (root / "docs/steps72_123_closure_register.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for i in range(72, 124):
            status, value = ("SYNTHETIC-IMPLEMENTED", "1.0") if i < 91 else (("PARTIAL", "0.5") if i < 111 else ("EXTERNAL-REQUIRED", "0.0"))
            writer.writerow({"step": i, "requirement": "Example", "evidence_status": status, "evidence_credit": value,
                             "existing_evidence": "not certified", "exit_criterion": "real exit criterion", "accountable_owner": "research team", "evidence_reference": "none", "independent_signoff": "NOT RECEIVED"})
    (root / "scripts/step96_106_content_audit.py").write_text(
        'import json,sys\nprint(json.dumps({"structural_check_passed":False,"issue_count":1142,"first_issues":["missing learning objective"],"expert_review_verified":False,"psychometric_validation_verified":False,"authorized_for_human_study":False}))\nsys.exit(1)\n',
        encoding="utf-8")
    return root


def test_52_steps_and_unchanged_credits(tmp_path):
    root = fixture_repo(tmp_path)
    rows, credit, counts = load_register(root / "docs/steps72_123_closure_register.csv")
    assert len(rows) == 52
    assert credit == 19 + 20 * .5
    assert counts["EXTERNAL-REQUIRED"] == 13


def test_no_content_audit_bypass_or_status_promotion(tmp_path):
    root = fixture_repo(tmp_path)
    path = root / "docs/steps72_123_closure_register.csv"
    original = path.read_bytes()
    s = build_snapshot(root)
    assert s["content_audit"]["exit_code"] == 1
    assert s["content_audit"]["json"]["issue_count"] == 1142
    assert s["score"]["provisional_percent"] == 55.8
    assert len(s["unreceived_signoffs"]) == 52
    assert path.read_bytes() == original
    assert "1,142" in render_markdown(s)


def test_reject_bad_register(tmp_path):
    root = fixture_repo(tmp_path)
    p = root / "docs/steps72_123_closure_register.csv"
    lines = p.read_text().splitlines()
    p.write_text("\n".join(lines[:-1]) + "\n")
    with pytest.raises(ValueError, match="52 steps"):
        load_register(p)


def test_optional_markdown_json_outputs(tmp_path):
    root = fixture_repo(tmp_path)
    output, js = tmp_path / "evidence.md", tmp_path / "evidence.json"
    assert main(["--root", str(root), "--output", str(output), "--json-output", str(js)]) == 0
    assert output.exists() and js.exists()
    assert "read-only" in output.read_text().lower()
    assert '"human_study_authorized"' not in js.read_text()  # no invented approval field
