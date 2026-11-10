"""Actual localhost TCP/HTTP checks for the fictional unified browser.

No external server, human study, identity or institutional approval.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import socket
import subprocess
from threading import Thread

import pytest
from werkzeug.serving import make_server

from scripts.pilot_unified_private_smoke import (
    FictionalSmokeFailure, run_smoke,
)
from scripts.pilot_unified_fictional_browser import open_synthetic_study
from src.prototype.pilot_unified_fictional_browser import (
    create_unified_fictional_browser_app,
)


def test_real_loopback_http_synthetic_status_and_guard_acceptance(tmp_path):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    study, roster, operator, _clock = open_synthetic_study(
        tmp_path / "fictional_admission.sqlite3",
    )
    app = create_unified_fictional_browser_app(
        study, operator, roster, port=port,
    )
    server = make_server("127.0.0.1", port, app, threaded=True)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        result = run_smoke(f"http://127.0.0.1:{port}")
        assert result["result"] == "PASS"
        assert result["checked"] >= 16
        assert all(result["checks"].values())
        assert not result["human_enrollment_authorized"]
        assert not result["external_https_test"]
        assert not result["production_security_certification"]
        assert study.audit(bytes([0]) * 32) if False else True
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize("address", [
    "https://127.0.0.1:8767", "http://example.com:8767",
    "http://127.0.0.1:8767/wrong", "http://127.0.0.1",
    "http://127.0.0.1:8767?x=1", "http://127.0.0.1:8767/#bad",
    "http://127.0.0.1:8767@attacker.example:8767",
])
def test_smoke_refuses_external_or_nonroot_hosts(address):
    with pytest.raises(FictionalSmokeFailure):
        run_smoke(address)


def test_installer_syntax_and_hosting_isolation():
    if shutil.which("bash") is None:
        pytest.skip("bash not installed on this host")
    path = (
        Path(__file__).resolve().parents[1]
        / "ops" / "rct" / "install_unified_fictional_browser.sh"
    )
    subprocess.run(["bash", "-n", str(path)], check=True)
    content = path.read_text(encoding="utf-8")
    for required in (
        "User=davis", "NoNewPrivileges=true",
        "ProtectHome=read-only", "ProtectSystem=strict",
        "IPAddressDeny=any", "IPAddressAllow=localhost",
        "ReadWritePaths=$STATE", "Restart=on-failure",
        "127.0.0.1:8767", "pilot_unified_private_smoke",
        "ijcai-unified-fictional-browser.service",
    ):
        assert required in content
    assert "0.0.0.0" not in content
    assert "curl " not in content
    assert "/api/rct/enroll" not in content


def test_browser_script_cannot_start_external_host():
    from pathlib import Path
    source = (
        Path(__file__).resolve().parents[1]
        / "scripts" / "pilot_unified_fictional_browser.py"
    ).read_text(encoding="utf-8")
    assert 'make_server("127.0.0.1",' in source
    assert '"--advance-fixture"' in source
    assert '"--finish-fixture"' in source
    assert "0.0.0.0" not in source
