"""Mechanical isolation checks for the one-file fictional VPS batch."""
from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess

import pytest

from scripts.pilot_unified_vps_report_check import CONTRACT, validate


def sample_report():
    return {**CONTRACT, "allocation_by_arm": {"A": 9, "B": 11, "C": 10},
            "fictional_replay_checks": 220}


def test_accepts_valid_single_sqlite_fictional_report():
    result = validate(sample_report())
    assert result["result"] == "PASS_SYNTHETIC_ONLY"
    assert result["checked"] == len(CONTRACT) + 2
    assert result["human_enrollment_authorized"] is False


@pytest.mark.parametrize("malformed", [
    {"human_enrollment_authorized": True},
    {"single_sqlite_file": False},
    {"atomic_provisioning_and_visit_boundaries": False},
    {"staff_authentication_real": True},
    {"independent_security_review": True},
    {"data_deleted_on_exit": False},
    {"no_network_requests": False},
    {"fictional_completed_visits": 89},
    {"fictional_questions": 2609},
    {"fictional_mvas_records": 179},
    {"fictional_replay_checks": 5},
    {"fictional_replay_checks": True},
    {"allocation_by_arm": {"A": 12, "B": 10, "C": 8}},
    {"allocation_by_arm": {"A": True, "B": 10, "C": 19}},
    {"allocation_by_arm": {"A": 10, "B": 20}},
])
def test_rejects_unverified_fixture_evidence(malformed):
    report = sample_report()
    report.update(malformed)
    with pytest.raises(ValueError):
        validate(report)


def test_rejects_nonobject():
    for thing in (None, [], "PASS", 42):
        with pytest.raises(ValueError):
            validate(thing)


def test_cli_reads_synthetic_report_only(tmp_path):
    target = tmp_path / "fictitious.json"
    before = json.dumps(sample_report(), sort_keys=True)
    target.write_text(before, encoding="utf-8")
    test = subprocess.run(
        ["python3", "-m", "scripts.pilot_unified_vps_report_check",
         "--path", str(target)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, check=True,
    )
    assert json.loads(test.stdout)["result"] == "PASS_SYNTHETIC_ONLY"
    assert target.read_text(encoding="utf-8") == before


def test_vps_shell_is_syntax_valid_and_has_no_public_study_route():
    if shutil.which("bash") is None:
        pytest.skip("bash unavailable")
    script = Path(__file__).resolve().parents[1] / (
        "ops/rct/run_unified_fictional_vps.sh"
    )
    subprocess.run(["bash", "-n", str(script)], check=True)
    text = script.read_text(encoding="utf-8").lower()
    for expected in (
        "/home/davis/ijcai_unified_vps_",
        "timeout --signal=term", "nice -n 10",
        "--participants 30 --simulations 41",
        "pilot_unified_vps_report_check", "umask 077",
    ):
        assert expected in text
    for forbidden in (
        "sudo ", "systemctl ", "0.0.0.0", "flask run",
        "caddy ", "curl ", "/api/rct/enroll",
    ):
        assert forbidden not in text
