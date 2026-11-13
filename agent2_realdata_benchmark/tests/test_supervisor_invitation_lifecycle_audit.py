"""Privacy-safe read-only invitation lifecycle and 21-day policy tests."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from scripts.supervisor_invitation_lifecycle_audit import inspect
from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_operational_intake import OperationalIntake
from src.prototype.supervisor_synthetic_store import (
    SupervisorSyntheticStore, SyntheticStudyError,
)

DATA=Path(__file__).resolve().parents[1]/"data"/"supervisor_20261111"
T=datetime(2026,11,12,21,29,tzinfo=timezone.utc)
EMAIL="supervisor-test@example.example"


def fixture(tmp_path):
    store=SupervisorSyntheticStore(
        tmp_path,bank=SupervisorBank(DATA),operational=True,
    )
    intake=OperationalIntake(store,programs=("Test student program",))
    token=intake.issue(EMAIL,at=T,allow_example=True)
    return store,intake,token


def test_unregistered_invitation_valid_for_21_days_not_one(tmp_path):
    _,intake,token=fixture(tmp_path)
    assert intake.status(token,at=T+timedelta(hours=25))["stage"]=="invited"
    audit=inspect(intake,EMAIL,at=T+timedelta(days=20))
    assert audit["can_register_before_expiry"]
    assert audit["registered_link_reusable"] is False
    assert audit["cookie_lifetime_days"]==14
    assert inspect(intake,EMAIL,at=T+timedelta(days=22))[
        "can_register_before_expiry"] is False
    with pytest.raises(SyntheticStudyError,match="expired"):
        intake.status(token,at=T+timedelta(days=22))
    assert token not in json.dumps(audit) and EMAIL not in json.dumps(audit)
    assert inspect(intake,"missing@example.example",at=T)["record_found"] is False


def test_registered_can_resume_past_initial_expiry_without_leaking_secret(tmp_path):
    store,intake,token=fixture(tmp_path)
    intake.consent(token,checks=[True]*5,optional=False,
                   language="en",at=T+timedelta(days=1))
    screening={
        q.question_id:(q.correct_answer if i<4 else
            next(k for k in "ABCD" if k!=q.correct_answer))
        for i,q in enumerate(store.bank.forms["screening"])
    }
    assert intake.screening(token,answers=screening,
                            at=T+timedelta(days=1))["eligible"]
    intake.register(token,age=24,program="Test student program",
                    at=T+timedelta(days=1))
    later=T+timedelta(days=35)
    assert intake.status(token,at=later)["stage"]=="participant"
    audit=inspect(intake,EMAIL,at=later)
    assert audit["registered_ignores_original_registration_expiry"]
    assert audit["registered_link_reusable"]
    assert audit["can_register_before_expiry"] is False
    assert token not in json.dumps(audit) and EMAIL not in json.dumps(audit)
    assert "token_hash" not in json.dumps(audit)


def test_cli_one_day_invitation_is_optional_and_does_not_send(tmp_path):
    import os
    import stat
    import subprocess
    import sys
    from urllib.parse import urlsplit,parse_qs
    root=Path(__file__).resolve().parents[1]
    env=os.environ.copy()
    env.update({
        "SUPERVISOR_VPS_MODE":"staging",
        "SUPERVISOR_VPS_ROOT":str(tmp_path),
        "SUPERVISOR_VPS_HOST":"demo.selfhealing-edu.fr",
        "SUPERVISOR_VPS_COMMIT":"a"*40,
        "SUPERVISOR_PROGRAMS":"Test student program",
    })
    recipient="one-day-review@example.example"
    destination=tmp_path/"private-invite.txt"
    before=datetime.now(timezone.utc)
    result=subprocess.run([
        sys.executable,"-m","scripts.supervisor_vps_admin",
        "--issue",recipient,"--validity-days","1",
        "--output",str(destination),
    ],cwd=root,env=env,capture_output=True,text=True,check=True)
    after=datetime.now(timezone.utc)
    assert "No email sent" in result.stdout
    assert recipient not in result.stdout+result.stderr
    assert (destination.stat().st_mode & 0o777)==0o600
    invitation=destination.read_text(encoding="utf-8").strip()
    token=parse_qs(urlsplit(invitation).fragment)["invite"][0]
    assert token not in result.stdout+result.stderr
    store=SupervisorSyntheticStore(
        tmp_path,bank=SupervisorBank(DATA),operational=True,
    )
    intake=OperationalIntake(store,programs=("Test student program",))
    with store._tx() as db:
        row=db.execute("SELECT expires_at FROM pii.invitations "
                       "WHERE email=?",(recipient,)).fetchone()
    until=datetime.fromisoformat(row["expires_at"])
    assert before+timedelta(days=1)<=until<=after+timedelta(days=1)
    assert intake.status(token,at=until-timedelta(seconds=1))["stage"]=="invited"
    with pytest.raises(SyntheticStudyError,match="expired"):
        intake.status(token,at=until+timedelta(seconds=1))


def test_failed_offline_invite_file_write_leaves_no_unclaimable_email(tmp_path,monkeypatch):
    """Failure after token insertion must not strand a contact or leak a link."""
    import sys
    from scripts import supervisor_vps_admin as admin
    store,intake,_=fixture(tmp_path)
    recipient="failed-write@example.example"
    monkeypatch.setattr(admin,"load",lambda:(intake,"staging"))
    monkeypatch.setenv("SUPERVISOR_VPS_HOST","demo.selfhealing-edu.fr")
    def fail_write(*_):
        raise OSError("injected private filesystem failure")
    monkeypatch.setattr(admin,"write_private",fail_write)
    output=tmp_path/"never-written.txt"
    monkeypatch.setattr(sys,"argv",[
        "supervisor_vps_admin","--issue",recipient,"--output",str(output)])
    with pytest.raises(OSError,match="filesystem failure"):
        admin.main()
    with store._tx() as db:
        assert db.execute(
            "SELECT COUNT(*) FROM pii.invitations WHERE email=?",
            (recipient,),
        ).fetchone()[0]==0
    assert not output.exists()
    # The staff operator can retry safely with the same intended recipient.
    new=intake.issue(recipient,at=T,allow_example=True)
    assert intake.status(new,at=T)["stage"]=="invited"


def test_failed_file_compensation_cannot_delete_consented_or_registered_invite(tmp_path):
    store,intake,token=fixture(tmp_path)
    intake.consent(token,checks=[True]*5,optional=False,language="en",at=T)
    with pytest.raises(SyntheticStudyError,match="cleanup cannot"):
        intake.cancel_unclaimed_private_file_failure(token)
    assert intake.status(token,at=T)["stage"]=="consented"
