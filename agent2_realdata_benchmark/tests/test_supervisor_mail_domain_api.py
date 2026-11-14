"""No-network signed domain transactional email API acceptance tests."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import uuid

import pytest

from src.prototype.supervisor_mail_providers import (
    build_mail_router, verify_signed_mail_policy, MailConfigurationError,
    MailDeliveryJournal, MailDeliveryError, MailDeliveryUnknown,
)

COMMIT="1"*40
DOMAIN_SENDER="private_quiz@selfhealing-edu.fr"
KEY="xkeysib-QA-PLACEHOLDER-NEVER-USABLE-1234567890"


def files(root: Path, *, verified=True, sender=DOMAIN_SENDER):
    if shutil.which("openssl") is None:
        pytest.skip("OpenSSL required")
    secret=root/"restricted"
    secret.mkdir(mode=0o700)
    auth=secret/"owner-authorization.pdf"
    auth.write_bytes(b"%PDF-1.7\nOFFLINE FIXTURE ONLY\n%%EOF")
    auth.chmod(0o600)
    domain=secret/"domain-dns-authenticated.pdf"
    domain.write_bytes(b"%PDF-1.7\nOFFLINE DOMAIN FIXTURE ONLY\n%%EOF")
    domain.chmod(0o600)
    api=secret/"brevo-api.key"
    api.write_text(KEY)
    api.chmod(0o600)
    digest=lambda p:sha256(p.read_bytes()).hexdigest()
    cfg={"schema":"IJCAI2027_MAIL_ROUTES_V1","default":"domain_sender",
         "routes":{"domain_sender":{
            "provider":"brevo_api","email":sender,
            "api_key_label":"owner-domain-v1",
            "api_key_file":str(api),
         }},"by_actor":{}}
    policy={"schema":"IJCAI2027_MAILBOX_AUTHORIZATION_V1",
            "decision":"approved","release_commit":COMMIT,
            "senders":{"domain_sender":{
                "provider":"brevo_api","email":DOMAIN_SENDER,
                "owner_authorized":True,"institutional_scope_verified":True,
                "owner_evidence_file":str(auth),"owner_evidence_sha256":digest(auth),
                "api_key_label":"owner-domain-v1",
                "api_key_file":str(api),
                "sender_domain_authenticated":verified,
                "domain_evidence_file":str(domain),
                "domain_evidence_sha256":digest(domain),
            }}}
    def private_json(path,obj):
        path.write_text(json.dumps(obj))
        path.chmod(0o600)
        return path
    config=private_json(secret/"routes.json",cfg)
    approval=private_json(secret/"owner-policy.json",policy)
    key=secret/"institutional-test-private.pem"
    pub=secret/"institutional-test-pub.pem"
    signature=secret/"owner-policy.sig"
    subprocess.run(["openssl","genpkey","-algorithm","RSA","-out",str(key),
                    "-pkeyopt","rsa_keygen_bits:2048"],capture_output=True,check=True)
    subprocess.run(["openssl","pkey","-in",str(key),"-pubout","-out",str(pub)],
                   capture_output=True,check=True)
    subprocess.run(["openssl","dgst","-sha256","-sign",str(key),
                    "-out",str(signature),str(approval)],capture_output=True,check=True)
    pub.chmod(0o600)
    signature.chmod(0o600)
    return secret,config,approval,signature,pub


def test_signed_domain_api_delivers_plain_text_via_fake_transport(tmp_path):
    secret, config, approval, signature, pub=files(tmp_path)
    audit=secret/"audit-secret"
    audit.write_bytes(b"x"*64)
    audit.chmod(0o600)
    journal=MailDeliveryJournal(secret/"mail-audit.sqlite3",audit)
    requests=[]
    def transport(url,*,method,headers,payload,timeout):
        requests.append((url,method,headers,payload))
        assert url=="https://api.brevo.com/v3/smtp/email"
        assert method=="POST"
        assert headers["api-key"]==KEY
        assert payload["sender"]["email"]==DOMAIN_SENDER
        assert payload["to"]==[{"email":"myself@example.org"}]
        assert payload["textContent"]=="This is a generic QA transport check"
        assert payload["subject"]=="QA test"
        assert uuid.UUID(payload["headers"]["IdempotencyKey"]).version==5
        return 201,b'{"messageId":"<fake-message-id@example.org>"}'
    router=build_mail_router(
        config_file=config,approval_file=approval,approval_signature=signature,
        institution_key=pub,release_commit=COMMIT,journal=journal,
        transport=transport,
    )
    route=router.routes["domain_sender"]
    route.send(to="myself@example.org",subject="QA test",
               body="This is a generic QA transport check",
               delivery_key="qa-once-20261114")
    assert len(requests)==1
    assert b"myself@example.org" not in journal.path.read_bytes()
    with pytest.raises(MailDeliveryUnknown,match="duplicate"):
        route.send(to="myself@example.org",subject="QA test",
                   body="This is a generic QA transport check",
                   delivery_key="qa-once-20261114")
    assert len(requests)==1


def test_domain_sender_requires_signed_verified_dns_proof(tmp_path):
    _,config,approval,signature,pub=files(tmp_path,verified=False)
    with pytest.raises(MailConfigurationError,match="domain"):
        verify_signed_mail_policy(config,approval,signature,pub,
                                  release_commit=COMMIT)


def test_sender_cannot_be_repointed_by_unsigned_json(tmp_path):
    _,config,approval,signature,pub=files(tmp_path,sender="untrusted@other-domain.org")
    with pytest.raises(MailConfigurationError,match="owner/institution"):
        verify_signed_mail_policy(config,approval,signature,pub,
                                  release_commit=COMMIT)


def test_domain_send_without_provider_receipt_requires_manual_review(tmp_path):
    secret,config,approval,signature,pub=files(tmp_path)
    audit=secret/"audit-secret"
    audit.write_bytes(b"b"*64)
    audit.chmod(0o600)
    journal=MailDeliveryJournal(secret/"audit.sqlite3",audit)
    sent=[]
    def fake_http(url,method,headers,payload,timeout):
        sent.append(1)
        return 201,b"{}"
    route=build_mail_router(config_file=config,approval_file=approval,
        approval_signature=signature,institution_key=pub,release_commit=COMMIT,
        journal=journal,transport=fake_http).routes["domain_sender"]
    with pytest.raises(MailDeliveryUnknown,match="reconcile"):
        route.send(to="myself@example.org",subject="QA",body="test",
                   delivery_key="one-error")
    with pytest.raises(MailDeliveryUnknown,match="duplicate"):
        route.send(to="myself@example.org",subject="QA",body="test",
                   delivery_key="one-error")
    assert len(sent)==1
