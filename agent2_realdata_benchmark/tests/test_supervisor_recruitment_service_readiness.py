"""Regression tests for the SSH-only recruitment preview readiness gate.

These tests never open a port, send mail, access a VPS, or use participant data.
"""
from pathlib import Path
import subprocess


SCRIPT = Path(__file__).resolve().parents[1] / "ops/supervisor/enable_recruitment_admin_preview.sh"


def test_installer_syntax_and_bounded_readiness_wait():
    source = SCRIPT.read_text(encoding="utf-8")
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    assert "for attempt in {1..25}; do" in source
    assert "systemctl is-active --quiet ijcai-supervisor-recruitment" in source
    assert 'http_code /control/' in source
    assert '[[' in source and '"$login_status" == 200' in source
    assert "sleep 1" in source
    assert "journalctl -u ijcai-supervisor-recruitment -n 40" in source
    assert "exit 2" in source


def test_anonymous_admin_is_rejected_and_public_intake_stays_closed():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "ReadWritePaths=/var/lib/ijcai-supervisor-staging" in source
    assert "ProtectSystem=strict" in source
    assert 'http_code /control/api/overview' in source
    assert '"$private_status" == 409' in source
    assert 'http_code /interest/school' in source
    assert '"$form_status" == 404' in source
    assert "127.0.0.1:8791" in source
    assert "SUPERVISOR_VPS_MODE=staging" in source
