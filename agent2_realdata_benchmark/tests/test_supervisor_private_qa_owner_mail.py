"""Self-consented Gmail-to-own-school QA link delivery, no actual provider."""
from pathlib import Path
import json
import stat

import pytest

from src.prototype.supervisor_mail_providers import MailConfigurationError,MailDeliveryUnknown
from scripts.supervisor_private_qa_owner_mail import (
    SENDER,RECIPIENT,_read_qa_url,send_owner_qa_link,
)


class StubSender:
    provider="gmail_delegated"
    sender=SENDER
    outbound_from=SENDER

    def __init__(self,fails=False):
        self.calls=[]
        self.fails=fails

    def send(self,*,to,subject,body):
        self.calls.append((to,subject,body))
        if self.fails:
            raise MailDeliveryUnknown("simulated uncertain provider response")


@pytest.fixture
def local(tmp_path):
    folder=tmp_path/"private"
    folder.mkdir(mode=0o700)
    link=folder/"qa-link.txt"
    link.write_text("http://127.0.0.1:8897/study/#invite="+("A"*60)+"\n")
    link.chmod(0o600)
    return folder,link


def test_owner_school_selftest_mail_is_one_shot_and_not_research(local):
    folder,link=local
    receipt=folder/"delivery.json"
    sender=StubSender()
    result=send_owner_qa_link(sender,recipient=RECIPIENT,
                              link_file=link,receipt_file=receipt)
    assert result["accepted_by_provider"] is True
    assert result["real_enrollment_authorized"] is False
    assert result["real_invitation_sent"] is False
    assert len(sender.calls)==1
    to,subject,body=sender.calls[0]
    assert to==RECIPIENT
    assert "PRIVATE QA ONLY" in subject
    assert "#invite=" in body
    assert "not permission to" in body
    assert "http://127.0.0.1:8897/study/#invite=" in body
    assert stat.S_IMODE(receipt.stat().st_mode)==0o600
    assert json.loads(receipt.read_text())["state"]=="provider_accepted_not_inbox_verified"
    assert "A"*40 not in receipt.read_text()
    with pytest.raises(MailConfigurationError,match="exists"):
        send_owner_qa_link(sender,recipient=RECIPIENT,
                           link_file=link,receipt_file=receipt)
    assert len(sender.calls)==1


def test_owner_selftest_rejects_other_people_and_public_tokens(local):
    folder,link=local
    sender=StubSender()
    for target in ("sara.elkardi@aivancity.education","visitor@example.com"):
        with pytest.raises(MailConfigurationError,match="exact owner"):
            send_owner_qa_link(sender,recipient=target,
                               link_file=link,receipt_file=folder/"not-used.json")
    assert not sender.calls
    for wrong in (
        "https://study.selfhealing-edu.fr/study/#invite="+("A"*60),
        "http://127.0.0.1:8897/study/#invite=short",
        "http://127.0.0.1:8897/study/#other="+("A"*60),
    ):
        link.write_text(wrong)
        with pytest.raises(MailConfigurationError):
            _read_qa_url(link)
    assert not (folder/"not-used.json").exists()


def test_uncertain_owner_delivery_reserves_receipt_without_retry(local):
    folder,link=local
    receipt=folder/"unknown.json"
    sender=StubSender(fails=True)
    with pytest.raises(MailDeliveryUnknown):
        send_owner_qa_link(sender,recipient=RECIPIENT,
                           link_file=link,receipt_file=receipt)
    assert json.loads(receipt.read_text())["state"]=="uncertain"
    with pytest.raises(MailConfigurationError,match="exists"):
        send_owner_qa_link(sender,recipient=RECIPIENT,
                           link_file=link,receipt_file=receipt)
    assert len(sender.calls)==1
