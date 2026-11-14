"""Signed Gmail send-as alias tests (all provider calls replaced by fakes)."""
from __future__ import annotations

import base64
from email import message_from_bytes
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from urllib.parse import parse_qs

import pytest
from cryptography.fernet import Fernet

from src.prototype.supervisor_mail_providers import (
    MailConfigurationError, DelegatedOAuthSender, EncryptedRefreshVault,
    build_mail_router, verify_signed_mail_policy,
)

COMMIT = "f" * 40
OWNER = "qa.owner@gmail.com"
ALIAS = "private_quiz@selfhealing-edu.fr"
DEST = "recipient@example.org"


def private(tmp_path):
    secret = tmp_path / "confidential"
    secret.mkdir(mode=0o700)
    vault_dir = secret / "oauth-vault"
    vault_dir.mkdir(mode=0o700)
    key = secret / "fernet.key"
    key.write_bytes(Fernet.generate_key())
    key.chmod(0o600)
    return secret, EncryptedRefreshVault(vault_dir,key)


def signed(secret: Path, *, alias=ALIAS, grant_alias=ALIAS, allowed=True):
    if not shutil.which("openssl"):
        pytest.skip("OpenSSL required")
    owner_file = secret / "owner-consent.pdf"
    owner_file.write_bytes(b"%PDF-1.7\nTEST FIXTURE ONLY\n%%EOF")
    owner_file.chmod(0o600)
    alias_file = secret / "alias-verification.pdf"
    alias_file.write_bytes(b"%PDF-1.7\nTEST VERIFIED ALIAS FIXTURE ONLY\n%%EOF")
    alias_file.chmod(0o600)
    client_id = "google_client_id_for_test_2026"
    entry = {
        "provider": "gmail_delegated", "email": OWNER,
        "client_id": client_id, "from_alias": alias,
    }
    grant = {
        "provider": "gmail_delegated", "email": OWNER,
        "client_id": client_id,
        "owner_authorized": True,
        "institutional_scope_verified": True,
        "owner_evidence_file": str(owner_file),
        "owner_evidence_sha256": sha256(owner_file.read_bytes()).hexdigest(),
        "from_alias": grant_alias,
        "alias_verified_by_owner": allowed,
        "alias_domain_authorized": True,
        "alias_evidence_file": str(alias_file),
        "alias_evidence_sha256": sha256(alias_file.read_bytes()).hexdigest(),
    }
    config = secret / "routes.json"
    config.write_text(json.dumps({"schema":"IJCAI2027_MAIL_ROUTES_V1",
                                   "default":"personal_gmail",
                                   "routes":{"personal_gmail": entry},
                                   "by_actor":{}}))
    config.chmod(0o600)
    record = secret / "owner-policy.json"
    record.write_text(json.dumps({"schema":"IJCAI2027_MAILBOX_AUTHORIZATION_V1",
                                  "decision":"approved",
                                  "release_commit": COMMIT,
                                  "senders":{"personal_gmail":grant}}))
    record.chmod(0o600)
    key = secret / "institutional-private.test.pem"
    pub = secret / "institutional-public.test.pem"
    signature = secret / "owner-policy.sig"
    subprocess.run(["openssl","genpkey","-algorithm","RSA","-out",str(key),
                    "-pkeyopt","rsa_keygen_bits:2048"],check=True,capture_output=True)
    subprocess.run(["openssl","pkey","-in",str(key),"-pubout","-out",str(pub)],
                   check=True,capture_output=True)
    subprocess.run(["openssl","dgst","-sha256","-sign",str(key),
                    "-out",str(signature),str(record)],check=True,capture_output=True)
    pub.chmod(0o600)
    signature.chmod(0o600)
    return config, record, signature, pub


def test_signed_owner_alias_sends_from_alias_but_oauth_is_real_gmail(tmp_path):
    secret, vault = private(tmp_path)
    config, record, signature, pub = signed(secret)
    with vault.exclusive():
        vault.store("gmail_delegated",OWNER,"local_test_refresh_token",identity=OWNER)

    calls=[]
    def refresh(url,data,headers,timeout):
        assert parse_qs(data.decode())["refresh_token"] == ["local_test_refresh_token"]
        calls.append("oauth")
        return 200,b'{"access_token":"fake_google_access_token_for_test"}'

    def send(url,method,headers,payload,timeout):
        calls.append("send")
        assert url.endswith("/gmail/v1/users/me/messages/send")
        raw=payload["raw"]
        payload_bytes=base64.urlsafe_b64decode(raw+"="*((-len(raw))%4))
        mime=message_from_bytes(payload_bytes)
        assert mime["From"] == ALIAS
        assert mime["To"] == DEST
        assert mime["Subject"] == "QA alias test"
        assert mime.get_payload(decode=True).decode().strip() == "Only a test"
        return 200,b"{}"

    router=build_mail_router(
        config_file=config, approval_file=record, approval_signature=signature,
        institution_key=pub, release_commit=COMMIT, vault=vault,
        transport=send, token_transport=refresh,
    )
    assert router.routes["personal_gmail"].sender.sender == OWNER
    assert router.routes["personal_gmail"].sender.outbound_from == ALIAS
    router.send(to=DEST,subject="QA alias test",body="Only a test")
    assert calls == ["oauth","send"]


@pytest.mark.parametrize("alias,grant_alias,allowed",[
    ("unknown@other-domain.example",ALIAS,True),
    (ALIAS,ALIAS,False),
])
def test_alias_must_match_exact_signed_evidence(tmp_path,alias,grant_alias,allowed):
    secret,_ = private(tmp_path)
    config,record,sig,pub = signed(
        secret,alias=alias,grant_alias=grant_alias,allowed=allowed,
    )
    with pytest.raises(MailConfigurationError,match="alias"):
        verify_signed_mail_policy(config,record,sig,pub,release_commit=COMMIT)


def test_unapproved_graph_alias_is_rejected_even_with_delegated_graph_grant(tmp_path):
    _,vault=private(tmp_path)
    with pytest.raises(MailConfigurationError,match="Gmail delegated"):
        DelegatedOAuthSender(
            provider="graph_delegated",sender="someone@outlook.com",
            client_id="graph_oauth_test_client",client_secret_path=None,
            vault=vault,from_alias=ALIAS,
        )


def test_signer_cannot_approve_alias_for_different_release(tmp_path):
    secret,_=private(tmp_path)
    config,record,sig,pub=signed(secret)
    with pytest.raises(MailConfigurationError,match="release"):
        verify_signed_mail_policy(config,record,sig,pub,release_commit="e"*40)
