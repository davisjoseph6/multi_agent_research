"""Operator-only remote demo is fictional, TLS-proxied and fail-closed."""
import json
from pathlib import Path

import pytest

from scripts.rct_candidate_cli import load_settings
from scripts.rct_operator_demo import make_demo_app, seed
from src.prototype.rct_candidate import RCTCandidateEngine
from src.prototype.study_v2_runtime import ProtocolError


BUNDLE_DIR = Path(__file__).resolve().parents[1] / "docs/rct_candidate_v1"


def configuration(tmp_path, hostname="demo.example.fr"):
    src = json.loads((BUNDLE_DIR / "settings_rehearsal.json").read_text())
    src["mode"] = "operator_demo"
    src["allowed_hosts"] = [hostname]
    src["behind_one_local_tls_proxy"] = True
    src["content"] = {k: str(BUNDLE_DIR / v) for k, v in src["content"].items()}
    p = tmp_path / "operator_demo.json"
    p.write_text(json.dumps(src))
    return p


def prepare(tmp_path):
    settings = configuration(tmp_path)
    db = tmp_path / "fictional.sqlite3"
    private = tmp_path / "invitations.json"
    report = seed(settings=settings, database=db, output=private)
    return settings, db, private, report


def test_seed_is_fictional_and_private(tmp_path):
    settings, db, private, report = prepare(tmp_path)
    assert report["fictional_enrolled"] == 9
    assert all(report["arm_counts"][arm] >= 2 for arm in "ABC")
    assert not report["human_enrollment_authorized"]
    invitations = json.loads(private.read_text())["invitations"]
    assert all(i["fictional"] and i["arm"] in "ABC" for i in invitations)
    assert all(i["invitation"] not in json.dumps(report) for i in invitations)
    assert private.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        seed(settings=settings, database=db, output=private)


def test_demo_endpoint_requires_trusted_proxy_https_host_and_no_http_enrollment(tmp_path, monkeypatch):
    settings, db, private, report = prepare(tmp_path)
    monkeypatch.setenv("RCT_DEMO_SETTINGS", str(settings))
    monkeypatch.setenv("RCT_DEMO_DATABASE", str(db))
    app = make_demo_app()
    invitation = json.loads(private.read_text())["invitations"][0]["invitation"]
    browser = app.test_client()
    proxy = {"REMOTE_ADDR": "127.0.0.1", "HTTP_X_FORWARDED_PROTO": "https",
             "HTTP_X_FORWARDED_FOR": "198.51.100.90"}
    good = browser.get("/", base_url="https://demo.example.fr", environ_overrides=proxy)
    assert good.status_code == 200
    assert b"OPERATOR-ONLY FICTIONAL DEMONSTRATION" in good.data
    assert good.headers["X-Robots-Tag"] == "noindex, nofollow"
    headers = {"Authorization": "Bearer " + invitation,
               "Origin": "https://demo.example.fr"}
    info = browser.post("/api/rct/information", base_url="https://demo.example.fr",
                        environ_overrides=proxy, headers=headers, json={})
    assert info.status_code == 200
    assert info.json["mode"] == "operator_demo"
    question = browser.post("/api/rct/next", base_url="https://demo.example.fr",
                            environ_overrides=proxy, headers=headers, json={})
    assert question.status_code == 200 and question.json["stage"] == "pretest"
    enroll = browser.post("/api/rct/enroll", base_url="https://demo.example.fr",
                          environ_overrides=proxy, headers=headers,
                          json={"agreed": True, "information_version": info.json["information_version"]})
    assert enroll.status_code == 403
    assert browser.get("/", base_url="http://demo.example.fr",
                       environ_overrides={"REMOTE_ADDR": "127.0.0.1"}).status_code == 403
    assert browser.get("/", base_url="https://wrong.example.fr",
                       environ_overrides=proxy).status_code == 403
    assert browser.get("/", base_url="https://demo.example.fr",
                       environ_overrides={**proxy, "REMOTE_ADDR": "198.51.100.90"}).status_code == 403


def test_demo_does_not_bypass_live_gate_or_allow_local_template(tmp_path):
    p = configuration(tmp_path, "demo.example.invalid")
    with pytest.raises(ValueError, match="hostname"):
        seed(settings=p, database=tmp_path / "bad.sqlite3", output=tmp_path / "bad.json")
    _, bundle, _ = load_settings(configuration(tmp_path))
    with pytest.raises(ProtocolError, match="Live enrollment blocked"):
        RCTCandidateEngine(tmp_path / "live.sqlite3", bundle, mode="live")
    assert not (tmp_path / "live.sqlite3").exists()
