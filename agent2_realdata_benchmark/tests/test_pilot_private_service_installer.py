"""Static, nonprivileged contract tests for synthetic-only VPS installer.

The installer is never executed in tests: actual systemd changes require the
operator to run the reviewed script on the designated private VPS.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "ops" / "rct" / "install_private_preview_service.sh"
)


def test_installer_is_syntactically_valid_bash():
    if shutil.which("bash") is None:
        pytest.skip("bash unavailable")
    assert SCRIPT.is_file()
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_installer_must_remain_synthetic_only_and_fail_closed():
    content = SCRIPT.read_text(encoding="utf-8")
    for required in (
        'if [[ "$(id -un)" != "davis" ]]',
        "^/home/davis/ijcai_preview_[a-zA-Z0-9_-]+",
        "fictional_browser_preview.sqlite3",
        "ijcai-pilot-private-preview.service",
        "systemctl cat",
        "Port 8766 already in use",
        "User=davis",
        "NoNewPrivileges=true",
        "ProtectSystem=strict",
        "ProtectHome=read-only",
        "IPAddressDeny=any",
        "IPAddressAllow=localhost",
        "ReadWritePaths=$STATE",
        " -m scripts.pilot_local_browser_preview ",
        "pilot_private_vps_smoke",
    ):
        assert required in content
    assert "0.0.0.0" not in content
    assert "caddy" not in content.lower().replace(
        "existing caddy operator demo", ""
    )
    assert "human_enrollment_authorized=true" not in content.lower()
