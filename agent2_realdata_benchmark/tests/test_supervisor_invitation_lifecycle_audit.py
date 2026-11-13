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
