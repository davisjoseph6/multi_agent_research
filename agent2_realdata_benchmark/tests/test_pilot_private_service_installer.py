"""Static, nonprivileged checks for private, fictional VPS service installer.

Never run this installer from tests: it needs explicit server-side sudo approval.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT = (Path(__file__).resolve().parents[1] /
          "ops" / "rct" / "install_private_preview_service.sh")


def test_installer_is_syntactically_valid_bash():
    if shutil.which("bash") is None:
        pytest.skip("bash unavailable")
    assert SCRIPT.is_file()
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_installer_must_remain_synthetic_only_and_fail_closed():
    content = SCRIPT.read_text(encoding="utf-8")
    for required in (
        'if [[ "$(id -un)" != "davis" ]]',
        '^/home/davis/ijcai_preview_[a-zA-Z0-9_-]+,
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
        "python -m scripts.pilot_local_browser_preview",
        "pilot_private_vps_smoke",
    ):
        if required == "python -m scripts.pilot_local_browser_preview":
            # ExecStart uses the selected Python interpreter in a variable.
            assert ' -m scripts.pilot_local_browser_preview ' in content
        else:
            assert required in content
    assert "0.0.0.0" not in content
    assert "caddy" not in content.lower().replace(
        "existing Caddy operator demo".lower(), ""
    ).replace("rewrite caddy", "")
    assert "human_enrollment_authorized=true" not in content.lower()
,
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
        "python -m scripts.pilot_local_browser_preview",
        "pilot_private_vps_smoke",
    ):
        if required == "python -m scripts.pilot_local_browser_preview":
            # ExecStart uses the selected Python interpreter in a variable.
            assert ' -m scripts.pilot_local_browser_preview ' in content
        else:
            assert required in content
    assert "0.0.0.0" not in content
    assert "caddy" not in content.lower().replace(
        "existing Caddy operator demo".lower(), ""
    ).replace("rewrite caddy", "")
    assert "human_enrollment_authorized=true" not in content.lower()
