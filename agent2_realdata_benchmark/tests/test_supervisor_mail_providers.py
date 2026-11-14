"""Offline safety tests. No real Microsoft/Google/mailbox calls."""
from __future__ import annotations

import base64
from datetime import datetime,timezone,timedelta
from email import message_from_bytes
import json
from pathlib import Path
import sqlite3
import subprocess
from urllib.parse import parse_qs
from cryptography.fernet import Fernet
import pytest

from src.prototype.supervisor_mail_providers import (
    MailConfigurationError, MailDeliveryError, MailDeliveryUnknown,
    EncryptedRefreshVault, DelegatedOAuthSender, MailRoute, MailRouter,
    MailDeliveryJournal, build_mail_router, verify_signed_mail_policy,
)
from scripts.supervisor_oauth_bootstrap import start, finish


def _private(tmp_path):
    root=tmp_path/"mail_secrets"
    root.mkdir(mode=0o700)
    vaultdir=root/"vault"
    vaultdir.mkdir(mode=0o700)
    key=root/"oauth.key"
    key.write_bytes(Fernet.generate_key())
    key.chmod(0o600)
    return root,EncryptedRefreshVault(vaultdir,key)


class FakeSender:
    def __init__(self, fails=False):
        self.calls=[]
        self.fails=fails
    def send(self, **message):
        self.calls.append(message)
        if self.fails:
            raise MailDeliveryUnknown("uncertain provider response")


def test_routing_is_independent_of_researcher_roles(tmp_path):
    root,_=_private(tmp_path)
    a,b=FakeSender(),FakeSender()
    router=MailRouter({
        "davis":MailRoute(sender=a,provider="gmail_delegated",
                          sender_email="davisjoseph767@gmail.com"),
        "wiam":MailRoute(sender=b,provider="graph_application",
                         sender_email="wiam.belouard@aivancity.education"),
    },"davis",by_actor={"wiam.belouard@aivancity.education":"wiam"})
    router.send(to="student@example.org",subject="Test",body="Content")
    assert len(a.calls)==1 and len(b.calls)==0
    router.for_actor("wiam.belouard@aivancity.education").send(
        to="student@example.org",subject="Test",body="Content")
    assert len(b.calls)==1
    # A mere application researcher identity is NOT a grant to use a
    # different sender unless that actor-to-provider route was signed.
    router.for_actor("sara.elkardi@aivancity.education").send(
        to="student@example.org",subject="Test",body="Content")
    assert len(a.calls)==2 and len(b.calls)==1
    with pytest.raises(MailConfigurationError):
        MailRouter(router.routes,"davis",by_actor={"sara.elkardi@aivancity.education":"unapproved"})


def test_audited_exact_invitation_key_never_retries_uncertain_send(tmp_path):
    private,_=_private(tmp_path)
    salt=private/"audit.secret"
    salt.write_bytes(b"x"*32)
    salt.chmod(0o600)
    db=private/"audit.sqlite3"
    journal=MailDeliveryJournal(db,salt)
    bad=FakeSender(fails=True)
    route=MailRoute(sender=bad,provider="gmail_delegated",
                    sender_email="davisjoseph767@gmail.com",
                    journal=journal,identifier="gmail")
    with pytest.raises(MailDeliveryUnknown):
        route.send(to="fictional@example.org",subject="Invitation",body="link",
                   delivery_key="invite:123")
    with pytest.raises(MailDeliveryUnknown, match="duplicate"):
        route.send(to="fictional@example.org",subject="Invitation",body="link",
                   delivery_key="invite:123")
    assert len(bad.calls)==1
    with sqlite3.connect(db) as conn:
        row=conn.execute("SELECT state,recipient_hmac FROM mail_receipts").fetchone()
    assert row[0]=="uncertain" and len(row[1])==64
    assert b"fictional@example.org" not in db.read_bytes()


@pytest.mark.parametrize("provider,success,urlpart",[
    ("graph_delegated",202,"graph.microsoft.com/v1.0/me/sendMail"),
    ("gmail_delegated",200,"gmail.googleapis.com/gmail/v1/users/me/messages/send"),
])
def test_delegated_refresh_rotation_and_provider_payload(tmp_path,provider,success,urlpart):
    private,vault=_private(tmp_path)
    sender=("someone@outlook.com" if provider=="graph_delegated"
            else "davisjoseph767@gmail.com")
    with vault.exclusive():
        vault.store(provider,sender,"old_refresh_token",identity=sender)
    calls=[]
    def refresh(url,data,headers,timeout):
        params=parse_qs(data.decode())
        assert params["refresh_token"]==["old_refresh_token"]
        assert params["grant_type"]==["refresh_token"]
        calls.append(("refresh",url))
        return 200,json.dumps({
            "access_token":"mock_access_token_1234",
            "refresh_token":"new_refresh_token",
        }).encode()
    def http(url,method,headers,payload,timeout):
        assert urlpart in url and method=="POST"
        assert headers["Authorization"]=="Bearer mock_access_token_1234"
        if provider=="gmail_delegated":
            raw=payload["raw"]
            padded=raw+"="*((-len(raw))%4)
            mime=message_from_bytes(base64.urlsafe_b64decode(padded))
            assert mime["From"]==sender
            assert mime["To"]=="learner@example.org"
            assert mime["Subject"]=="Visit"
        else:
            assert payload["message"]["toRecipients"][0]["emailAddress"]["address"]=="learner@example.org"
        calls.append(("send",url))
        return success,b"{}"
    service=DelegatedOAuthSender(
        provider=provider,sender=sender,client_id="local_client_app_id",
        client_secret_path=None,vault=vault,transport=http,token_transport=refresh,
    )
    service.send(to="learner@example.org",subject="Visit",body="Continue your quiz")
    assert [x[0] for x in calls]==["refresh","send"]
    with vault.exclusive():
        assert vault.load(provider,sender)["refresh_token"]=="new_refresh_token"
    path=next((private/"vault").glob("*.token.enc"))
    assert b"new_refresh_token" not in path.read_bytes()


def test_delegated_graph_never_sends_as_gmail_login_alias(tmp_path):
    _,vault=_private(tmp_path)
    with pytest.raises(MailConfigurationError,match="alias"):
        DelegatedOAuthSender(
            provider="graph_delegated",sender="davisjosep767@gmail.com",
            client_id="microsoft_public_client_id",client_secret_path=None,
            vault=vault
        )


def test_graph_permission_failures_are_terminal_not_retryable(tmp_path):
    _,vault=_private(tmp_path)
    sender="researcher@outlook.com"
    with vault.exclusive():
        vault.store("graph_delegated",sender,"existing_refresh_token",identity=sender)
    def refresh(url,data,headers,timeout):
        return 200,b'{"access_token":"access_token_long_enough"}'
    calls=[]
    def http(url,method,headers,payload,timeout):
        calls.append(url)
        return 403,b""
    client=DelegatedOAuthSender(provider="graph_delegated",sender=sender,
        client_id="graph_client_identifier",client_secret_path=None,
        vault=vault,transport=http,token_transport=refresh)
    with pytest.raises(MailDeliveryError,match="403"):
        client.send(to="recipient@example.org",subject="Test",body="hello")
    assert len(calls)==1


def _sign(root,record):
    import shutil
    if shutil.which("openssl") is None:
        pytest.skip("OpenSSL unavailable")
    key=root/"private.key"
    pub=root/"public.pem"
    manifest=root/"policy.json"
    sig=root/"policy.sig"
    manifest.write_text(json.dumps(record))
    manifest.chmod(0o600)
    subprocess.run(["openssl","genpkey","-algorithm","RSA","-out",str(key),
                    "-pkeyopt","rsa_keygen_bits:2048"],check=True,capture_output=True)
    subprocess.run(["openssl","pkey","-in",str(key),
                    "-pubout","-out",str(pub)],check=True,capture_output=True)
    subprocess.run(["openssl","dgst","-sha256","-sign",str(key),"-out",str(sig),
                    str(manifest)],check=True,capture_output=True)
    sig.chmod(0o600)
    return manifest,sig,pub


def test_signed_mailbox_policy_requires_exact_owner_and_release(tmp_path):
    private,_=_private(tmp_path)
    commit="a"*40
    sender="wiam.belouard@aivancity.education"
    secret=private/"client.secret"
    secret.write_text("a-test-client-secret-length-24-plus")
    secret.chmod(0o600)
    cfg=private/"routes.json"
    cfg.write_text(json.dumps({
        "schema":"IJCAI2027_MAIL_ROUTES_V1",
        "default":"wiam",
        "routes":{"wiam":{
            "provider":"graph_application","email":sender,
            "tenant":"11111111-1111-1111-1111-111111111111",
            "client_id":"22222222-2222-2222-2222-222222222222",
            "client_secret_file":str(secret)}},
        "by_actor":{}
    }))
    cfg.chmod(0o600)
    rec={"schema":"IJCAI2027_MAILBOX_AUTHORIZATION_V1",
         "decision":"approved","release_commit":commit,
         "senders":{"wiam":{"provider":"graph_application","email":sender,
                              "owner_authorized":True,
                              "institutional_scope_verified":True,
                              "owner_evidence_sha256":"b"*64}}}
    manifest,sig,pub=_sign(private,rec)
    found=verify_signed_mail_policy(cfg,manifest,sig,pub,release_commit=commit)
    assert found["default"]=="wiam"
    router=build_mail_router(config_file=cfg,approval_file=manifest,
        approval_signature=sig,institution_key=pub,release_commit=commit)
    assert router.routes["wiam"].email==sender
    with pytest.raises(MailConfigurationError):
        build_mail_router(config_file=cfg,approval_file=manifest,
            approval_signature=sig,institution_key=pub,release_commit="c"*40)
    # A named research account can never add Sara as a sender by changing
    # the unsigned route file alone.
    data=json.loads(cfg.read_text())
    data["routes"]["sara"]={"provider":"graph_application",
        "email":"sara.elkardi@aivancity.education",
        "tenant":"11111111-1111-1111-1111-111111111111",
        "client_id":"22222222-2222-2222-2222-222222222222",
        "client_secret_file":str(secret)}
    cfg.write_text(json.dumps(data))
    with pytest.raises(MailConfigurationError,match="unsigned"):
        verify_signed_mail_policy(cfg,manifest,sig,pub,release_commit=commit)
    # Invalidating institution's signature also fails closed.
    cfg.write_text(json.dumps(found))
    manifest.write_text(json.dumps(rec,indent=2))
    with pytest.raises(MailConfigurationError,match="signature"):
        verify_signed_mail_policy(cfg,manifest,sig,pub,release_commit=commit)


def test_local_oauth_flow_uses_pkce_state_and_nonfunctional_secrets(tmp_path):
    private,_=_private(tmp_path)
    state=private/"oauth.pending"
    auth=start(provider="gmail_delegated",
        sender="davisjoseph767@gmail.com",client_id="gmail_local_oauth_client",
        state_path=state)
    query=parse_qs(auth.split("?",1)[1])
    assert query["code_challenge_method"]==["S256"]
    assert query["access_type"]==["offline"]
    assert "gmail.send" in query["scope"][0]
    assert state.stat().st_mode&0o077==0
    with pytest.raises(MailConfigurationError,match="unoccupied|File exists"):
        start(provider="gmail_delegated",sender="davisjoseph767@gmail.com",
              client_id="gmail_local_oauth_client",state_path=state)
    # The authorization code is not exchanged until the human verifies
    # the redirect state. This test calls no external OAuth endpoint.
    from src.prototype.supervisor_mail_providers import EncryptedRefreshVault
    vault=EncryptedRefreshVault(private/"vault",private/"oauth.key")
    with pytest.raises(MailConfigurationError,match="state mismatch"):
        finish(session_file=state,
               redirect_url="http://127.0.0.1:8765/callback?code=mock&state=wrong",
               vault=vault)
