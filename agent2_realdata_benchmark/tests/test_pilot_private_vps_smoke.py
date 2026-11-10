"""Actual loopback HTTP acceptance tests for the fictional-only VPS preview."""
from __future__ import annotations

import socket
from pathlib import Path
from threading import Thread

import pytest
from werkzeug.serving import make_server

from scripts.pilot_private_vps_smoke import (
    run_acceptance, validate_loopback_base,
)
from src.prototype.pilot_local_browser_preview import (
    create_fictional_preview_app, ensure_three_fictional_records,
)
from src.prototype.pilot_three_arm_store_draft import SyntheticThreeArmPilotStore


CONTENT = Path(__file__).resolve().parents[1] / "docs" / "rct_candidate_v1"


@pytest.mark.parametrize("host", [
    "https://demo.selfhealing-edu.fr", "http://localhost:8766",
    "http://0.0.0.0:8766", "http://31.70.172.140:8766",
    "http://[::1]:8766", "http://127.0.0.1",
    "http://127.0.0.1:80", "http://127.0.0.1:65536",
    "http://user:password@127.0.0.1:8766",
    "http://127.0.0.1:8766/somewhere", "http://127.0.0.1:8766/?x=1",
    "http://127.0.0.1:8766/#x", "file:///tmp/not-http",
])
def test_smoke_cannot_target_external_or_ambiguous_urls(host):
    with pytest.raises(ValueError):
        validate_loopback_base(host)


def test_smoke_checks_actual_local_http_without_writing_study_state(tmp_path):
    with socket.socket() as socket_fd:
        socket_fd.bind(("127.0.0.1", 0))
        port = socket_fd.getsockname()[1]
    store = SyntheticThreeArmPilotStore(
        tmp_path / "fictional_browser_preview.sqlite3",
        items_path=CONTENT / "items.csv",
        resources_path=CONTENT / "resources.csv",
        simulations=41,
    )
    ids = ensure_three_fictional_records(store)
    before = {arm: store.snapshot(pid) for arm, pid in ids.items()}
    app = create_fictional_preview_app(store, port=port)
    server = make_server("127.0.0.1", port, app, threaded=True)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        result = run_acceptance(f"http://127.0.0.1:{port}")
        assert result["result"] == "PASS", result["failures"]
        assert result["checked"] >= 17
        assert result["checks"]["enrollment_route_absent"]
        assert result["checks"]["missing_nonce_denied"]
        assert result["checks"]["missing_origin_denied"]
        assert result["checks"]["fictional_arm_A_status"]
        assert result["checks"]["fictional_arm_B_status"]
        assert result["checks"]["fictional_arm_C_status"]
        assert result["not_security_or_production_certification"]
        assert not result["human_enrollment_authorized"]
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()
    assert before == {arm: store.snapshot(pid) for arm, pid in ids.items()}


def test_smoke_fails_closed_when_preview_is_not_running():
    with socket.socket() as socket_fd:
        socket_fd.bind(("127.0.0.1", 0))
        port = socket_fd.getsockname()[1]
    result = run_acceptance(f"http://127.0.0.1:{port}")
    assert result["result"] == "FAIL"
    assert not result["human_enrollment_authorized"]


def test_no_external_origin_server_paths_present():
    src = (Path(__file__).resolve().parents[1] /
           "scripts" / "pilot_private_vps_smoke.py").read_text()
    assert 'only explicit http://127.0.0.1:' in src
    assert '"enrollment_route_absent"' in src
    assert '"human_enrollment_route_absent"' in src
    assert '"real_student_identity_or_consent"' not in src
