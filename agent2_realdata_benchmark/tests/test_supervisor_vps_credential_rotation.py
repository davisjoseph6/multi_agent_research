"""Offline-only test credential rotation; never exercise real participant access.

A full invitation capability was accidentally shared during VPS staging.
Security remedy: create a replacement without deleting the three-session
research state, and immediately invalidate existing browsers and old URL.
"""
from datetime import datetime, timezone
from pathlib import Path
import os
import secrets
import stat
import subprocess
import sys
from urllib.parse import urlsplit, parse_qs

import pytest

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_operational_intake import OperationalIntake
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore, SyntheticStudyError
from src.prototype.supervisor_vps_web import make_supervisor_vps_app

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "data" / "supervisor_20261111"
NOW = lambda: datetime.now(timezone.utc)


def fixture(tmp_path):
    store = SupervisorSyntheticStore(tmp_path, bank=SupervisorBank(BANK), operational=True)
    intake = OperationalIntake(store, programs=("Test student program",))
    old = intake.issue("staging-fixture@example.example", at=NOW(), allow_example=True)
    intake.consent(old, checks=[True] * 5, optional=False, language="fr", at=NOW())
    screening = {
        q.question_id: (q.correct_answer if n < 4 else
                        next(a for a in "ABCD" if a != q.correct_answer))
        for n, q in enumerate(store.bank.forms["screening"])
    }
    assert intake.screening(old, answers=screening, at=NOW())["eligible"]
    intake.register(old, age=23, program="Test student program", at=NOW())
    return store, intake, old


def test_registered_credential_rotation_invalidates_previous_cookie_and_preserves_study(tmp_path):
    store, intake, old = fixture(tmp_path)
    ref = intake.learner(old, at=NOW())
    state = store.progress(ref, old)
    with store._tx() as db:
        old_events = db.execute(
            "SELECT COUNT(*) FROM events WHERE learner_id=?", (ref,)
        ).fetchone()[0]
        old_arm = db.execute(
            "SELECT grp FROM participants WHERE learner_id=?", (ref,)
        ).fetchone()[0]
        schedule = [r["scheduled_for"] for r in db.execute(
            "SELECT scheduled_for FROM sessions WHERE learner_id=? ORDER BY session_no",
            (ref,),
        )]

    app = make_supervisor_vps_app(
        intake, hostname="demo.selfhealing-edu.fr", proxy_mode=False,
        release_mode="staging",
    )
    client = app.test_client()
    headers = {"Origin": "http://127.0.0.1:8788",
               "X-Study-Request": "1", "Content-Type": "application/json"}
    def call(endpoint, body):
        return client.post("/study/api/" + endpoint, json=body,
                           headers=headers, base_url="http://127.0.0.1:8788")

    assert call("exchange", {"token": old}).status_code == 200
    assert call("status", {}).json["stage"] == "participant"
    replacement = secrets.token_urlsafe(40)
    assert intake.rotate_registered_test(
        "staging-fixture@example.example", new_token=replacement, at=NOW()
    ) == ref
    with pytest.raises(SyntheticStudyError, match="invitation not found"):
        intake.status(old, at=NOW())
    assert call("status", {}).status_code == 409  # old HttpOnly cookie
    assert call("exchange", {"token": replacement}).status_code == 200
    assert call("status", {}).json["stage"] == "participant"
    assert intake.learner(replacement, at=NOW()) == ref
    assert store.progress(ref, replacement) == state

    with store._tx() as db:
        assert db.execute(
            "SELECT COUNT(*) FROM events WHERE learner_id=?", (ref,)
        ).fetchone()[0] == old_events
        assert db.execute(
            "SELECT grp FROM participants WHERE learner_id=?", (ref,)
        ).fetchone()[0] == old_arm
        assert [r["scheduled_for"] for r in db.execute(
            "SELECT scheduled_for FROM sessions WHERE learner_id=? ORDER BY session_no",
            (ref,),
        )] == schedule
        assert db.execute(
            "SELECT COUNT(*) FROM pii.contacts WHERE learner_id=?", (ref,)
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT COUNT(*) FROM pii.invitations WHERE learner_id=?", (ref,)
        ).fetchone()[0] == 1


def test_rotation_requires_registered_example_and_does_not_revoke_on_failure(tmp_path):
    store, intake, old = fixture(tmp_path)
    for email, new_token in (
        ("unregistered@example.example", secrets.token_urlsafe(40)),
        ("staging-fixture@gmail.com", secrets.token_urlsafe(40)),
        ("staging-fixture@example.example", "too-short"),
        ("staging-fixture@example.example", old),
    ):
        with pytest.raises(SyntheticStudyError):
            intake.rotate_registered_test(email, new_token=new_token, at=NOW())
        assert intake.status(old, at=NOW())["stage"] == "participant"
    assert store.progress(intake.learner(old, at=NOW()), old)["phase"] == "PRETEST"


def test_private_cli_output_rotates_only_after_creation_and_never_prints_secret(tmp_path):
    _, intake, old = fixture(tmp_path)
    env = os.environ.copy()
    env.update({
        "SUPERVISOR_VPS_MODE": "staging",
        "SUPERVISOR_VPS_ROOT": str(tmp_path),
        "SUPERVISOR_VPS_HOST": "demo.selfhealing-edu.fr",
        "SUPERVISOR_VPS_COMMIT": "a" * 40,
        "SUPERVISOR_PROGRAMS": "Test student program",
    })
    private = tmp_path / "rotated-secret.txt"
    private.write_text("do not overwrite\n", encoding="utf-8")
    refused = subprocess.run([
        sys.executable, "-m", "scripts.supervisor_vps_admin",
        "--rotate-registered-test", "staging-fixture@example.example",
        "--output", str(private),
    ], cwd=ROOT, env=env, text=True, capture_output=True)
    assert refused.returncode != 0
    assert private.read_text(encoding="utf-8") == "do not overwrite\n"
    assert intake.status(old, at=NOW())["stage"] == "participant"
    private.unlink()

    rotated = subprocess.run([
        sys.executable, "-m", "scripts.supervisor_vps_admin",
        "--rotate-registered-test", "staging-fixture@example.example",
        "--output", str(private),
    ], cwd=ROOT, env=env, text=True, capture_output=True, check=True)
    assert stat.S_IMODE(private.stat().st_mode) == 0o600
    url = private.read_text(encoding="utf-8").strip()
    assert url.startswith("https://demo.selfhealing-edu.fr/study/#invite=")
    new_token = parse_qs(urlsplit(url).fragment)["invite"][0]
    assert len(new_token) >= 40
    assert new_token not in (rotated.stdout + rotated.stderr)
    assert old not in (rotated.stdout + rotated.stderr)
    assert "previous invitation" in rotated.stdout.lower()
    with pytest.raises(SyntheticStudyError):
        intake.status(old, at=NOW())
    assert intake.status(new_token, at=NOW())["stage"] == "participant"
