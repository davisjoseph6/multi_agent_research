"""No-network proof that delegated owner mail canary is harmless and once-only."""
from pathlib import Path
import json
import stat

import pytest
from src.prototype.supervisor_mail_providers import MailConfigurationError, MailDeliveryUnknown
from scripts.supervisor_mail_owner_canary import one_shot_self_canary


class FakeOwner:
    def __init__(self, *, provider="gmail_delegated", fails=False):
        self.provider=provider
        self.sender="self-qa@example.org"
        self.fails=fails
        self.calls=[]

    def send(self, *, to, subject, body):
        self.calls.append((to,subject,body))
        if self.fails:
            raise MailDeliveryUnknown("simulated transport uncertainty")


def test_one_shot_owner_self_mail_has_no_study_links_and_no_duplicates(tmp_path):
    vault=tmp_path/"private"
    vault.mkdir(mode=0o700)
    record=vault/"canary-once.json"
    owner=FakeOwner()
    result=one_shot_self_canary(owner,receipt_file=record)
    assert result["canary"]=="provider_accepted"
    assert not result["study_mail_enabled"]
    assert not result["human_enrollment_enabled"]
    assert not result["inbox_delivery_verified"]
    assert len(owner.calls)==1
    to,subject,body=owner.calls[0]
    assert to==owner.sender
    assert "connectivity test" in subject
    assert "no questionnaire" in body
    assert "#invite=" not in body
    assert "https://" not in body
    assert stat.S_IMODE(record.stat().st_mode)==0o600
    assert json.loads(record.read_text())["state"]=="provider_accepted_not_inbox_confirmed"
    assert owner.sender not in record.read_text()
    with pytest.raises(MailConfigurationError,match="fresh"):
        one_shot_self_canary(owner,receipt_file=record)
    assert len(owner.calls)==1


def test_uncertain_delivery_retains_reserved_record_and_refuses_retry(tmp_path):
    private=tmp_path/"private"
    private.mkdir(mode=0o700)
    record=private/"attempt.json"
    owner=FakeOwner(provider="graph_delegated",fails=True)
    with pytest.raises(MailDeliveryUnknown):
        one_shot_self_canary(owner,receipt_file=record)
    assert json.loads(record.read_text())["state"]=="uncertain"
    with pytest.raises(MailConfigurationError):
        one_shot_self_canary(owner,receipt_file=record)
    assert len(owner.calls)==1


def test_canary_rejects_unrelated_provider_and_insecure_output(tmp_path):
    root=tmp_path/"public"
    root.mkdir(mode=0o755)
    owner=FakeOwner()
    with pytest.raises(MailConfigurationError,match="0700"):
        one_shot_self_canary(owner,receipt_file=root/"canary.json")
    assert not owner.calls
    root.chmod(0o700)
    owner.provider="graph_application"
    with pytest.raises(MailConfigurationError,match="delegated"):
        one_shot_self_canary(owner,receipt_file=root/"canary.json")
    assert not owner.calls
