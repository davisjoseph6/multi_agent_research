"""Isolated VPS synthetic batch report contract and shell runner checks."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from scripts.pilot_integrated_vps_report_check import (
    CONTRACT, SyntheticReportError, check_report, main,
)


def valid_report():
    return {
        **CONTRACT,
        "allocated_by_arm": {"A": 10, "B": 10, "C": 10},
        "fictional_replay_checks": 220,
    }


def test_nominal_and_acceptable_partial_random_block_distributions():
    report = valid_report()
    assert check_report(report)["result"] == "PASS_SYNTHETIC_ONLY"
    report["allocated_by_arm"] = {"A": 9, "B": 9, "C": 12}
    assert check_report(report)["checked"] >= 15
    report["allocated_by_arm"] = {"A": 11, "B": 10, "C": 9}
    assert check_report(report)["human_enrollment_authorized"] is False


@pytest.mark.parametrize("changed", [
    {"result": "PASS"},
    {"human_enrollment_authorized": True},
    {"staff_authentication_real": True},
    {"cross_database_atomicity": True},
    {"fictional_completed_visits": 89},
    {"fictional_questions": 2609},
    {"fictional_mvas_records": 179},
    {"no_network_requests": False},
    {"temporary_stores_deleted": False},
    {"fictional_replay_checks": 29},
    {"fictional_replay_checks": True},
    {"allocated_by_arm": {"A": 30, "B": 0, "C": 0}},
    {"allocated_by_arm": {"A": 12, "B": 10, "C": 8}},
    {"allocated_by_arm": {"A": 11, "B": 11, "C": 11}},
    {"allocated_by_arm": {"A": True, "B": 10, "C": 19}},
    {"allocated_by_arm": {"A": 10, "B": 20}},
])
def test_fails_closed_on_invalid_synthetic_report(changed):
    report = valid_report()
    report.update(changed)
    with pytest.raises(SyntheticReportError):
        check_report(report)


def test_rejects_wrong_json_shape():
    for shape in (None, [], "PASS", 30):
        with pytest.raises(SyntheticReportError):
            check_report(shape)


def test_report_cli_reads_without_modifying(tmp_path):
    path = tmp_path / "fictional_report.json"
    original = json.dumps(valid_report(), sort_keys=True)
    path.write_text(original, encoding="utf-8")
    result = subprocess.run(
        ["python3", "-m", "scripts.pilot_integrated_vps_report_check",
         "--path", str(path)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["result"] == "PASS_SYNTHETIC_ONLY"
    assert path.read_text(encoding="utf-8") == original


def test_vps_runner_bash_syntax_and_private_boundary():
    if shutil.which("bash") is None:
        pytest.skip("bash unavailable")
    script = (
        Path(__file__).resolve().parents[1]
        / "ops" / "rct" / "run_integrated_fictional_vps.sh"
    )
    subprocess.run(["bash", "-n", str(script)], check=True)
    content = script.read_text(encoding="utf-8")
    for required in (
        '$(id -un)',
        '^/home/davis/ijcai_integrated_vps_',
        "pilOT_integrated".lower(),  # no network-facing route
        '--participants 30 --simulations 41',
        "timeout --signal=TERM",
        "nice -n 10",
        "no arguments",
        "umask 077",
        "mktemp",
        "pilot_integrated_vps_report_check",
    ):
        # Check names without inventing services or endpoints.
        assert required.lower() in content.lower()
    for forbidden in (
        "sudo ", "systemctl ", "0.0.0.0", "curl ", "caddy ", "flask run",
        "/api/rct/enroll", "listen 8766",
    ):
        assert forbidden not in content.lower()
