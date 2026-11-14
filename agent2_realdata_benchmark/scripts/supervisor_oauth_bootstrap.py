"""Local-only user-consented OAuth bootstrap for Graph delegated and Gmail.

No ChatGPT connector, browser automation, public callback, or VPS listener.
Only the OWNER signs in on their local computer. The short-lived redirect URL
is pasted into this CLI via a hidden prompt, never into Git/chat.
Tokens are encrypted before moving the vault to a protected LIVE service.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone, timedelta
import getpass
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import secrets
import stat
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from cryptography.fernet import Fernet

from src.prototype.supervisor_mail_providers import (
    EncryptedRefreshVault, _form_http, private_file,
    MailConfigurationError, MailDeliveryUnknown, GRAPH_TOKEN, GMAIL_TOKEN,
)
from src.prototype.supervisor_recruitment import canonical_email

REDIRECT = "http://127.0.0.1:8765/callback"
MS_AUTH = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"


def _new_private_file(path: Path, content: str):
    if not path.is_absolute() or path.is_symlink() or not path.parent.is_dir():
        raise MailConfigurationError("private absolute path with existing parent required")
    if path.parent.stat().st_mode & 0o077:
        raise MailConfigurationError("OAuth session parent must be mode 0700")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as stream:
        stream.write(content)


def init_vault(*, vault_dir: Path, key_file: Path):
    if (not vault_dir.is_absolute() or not key_file.is_absolute()
            or vault_dir.exists() or key_file.exists()
            or not key_file.parent.is_dir()
            or key_file.parent.stat().st_mode & 0o077):
        raise MailConfigurationError("new separate, private vault dir and key path required")
    vault_dir.mkdir(mode=0o700)
    _new_private_file(key_file, Fernet.generate_key().decode("ascii")+"\n")
    return dict(vault=str(vault_dir),key_location=str(key_file),
                status="PRIVATE_KEY_GENERATED_NO_MAIL_PERMISSIONS_GRANTED")


def start(*, provider: str, sender: str, client_id: str,
          state_path: Path, tenant: str = "consumers",
          client_secret_file: str | None = None):
    address = canonical_email(sender)
    if provider not in ("graph_delegated","gmail_delegated"):
        raise MailConfigurationError("delegated OAuth only")
    if provider == "graph_delegated" and address.endswith("@gmail.com"):
        raise MailConfigurationError(
            "a Gmail Microsoft-login alias is not a Microsoft-hosted mailbox")
    if len(client_id) < 8:
        raise MailConfigurationError("OAuth app client ID required")
    if client_secret_file:
        private_file(client_secret_file)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    scope = ("offline_access Mail.Send User.Read"
             if provider == "graph_delegated" else
             "openid email https://www.googleapis.com/auth/gmail.send")
    host = (MS_AUTH.format(tenant=tenant) if provider=="graph_delegated"
            else GOOGLE_AUTH)
    params = dict(client_id=client_id,response_type="code",
                  redirect_uri=REDIRECT,scope=scope,state=state,
                  code_challenge=challenge,code_challenge_method="S256")
    if provider == "gmail_delegated":
        params.update(access_type="offline",prompt="consent")
    else:
        params.update(response_mode="query",prompt="consent")
    _new_private_file(state_path, json.dumps(dict(
        provider=provider,sender=address,client_id=client_id,
        tenant=tenant,client_secret_file=client_secret_file,
        issued_at=datetime.now(timezone.utc).isoformat(),
        redirect_uri=REDIRECT,verifier=verifier,state=state
    ))+"\n")
    # Safe to show the public authorization URL ONLY on the owner's machine.
    # This is not a refresh token or credential.
    return host+"?"+urlencode(params)


def _profile(provider: str, token: str) -> str:
    # Verify the exact mailbox owner through the provider's authenticated
    # profile endpoint. Do not decode an unsigned JWT as identity evidence.
    url = ("https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName"
           if provider=="graph_delegated"
           else "https://openidconnect.googleapis.com/v1/userinfo")
    req = Request(url,headers={"Authorization":"Bearer "+token})
    try:
        with urlopen(req,timeout=20) as response:
            info=json.loads(response.read(32768))
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        raise MailConfigurationError("OAuth identity verification failed") from None
    if provider=="gmail_delegated":
        if info.get("email_verified") not in (True, "true"):
            raise MailConfigurationError("Google account email not verified")
        return canonical_email(info["email"])
    # Microsoft /me mail can be empty for some accounts. Never assume the
    # sign-in alias is a Graph-accessible Exchange/Outlook mailbox.
    address=info.get("mail") or info.get("userPrincipalName")
    return canonical_email(address)


def finish(*, session_file: Path, redirect_url: str,
           vault: EncryptedRefreshVault):
    pending=json.loads(private_file(session_file,writable=True).read_text())
    if (datetime.now(timezone.utc)-
        datetime.fromisoformat(pending["issued_at"]) > timedelta(minutes=12)):
        raise MailConfigurationError("OAuth authorization session expired")
    parsed=urlsplit(redirect_url.strip())
    expected=urlsplit(pending["redirect_uri"])
    if (parsed.scheme,parsed.netloc,parsed.path)!=(expected.scheme,expected.netloc,expected.path):
        raise MailConfigurationError("OAuth redirect origin/path mismatch")
    query=parse_qs(parsed.query)
    if not hmac.compare_digest(query.get("state",[""])[0],pending["state"]):
        raise MailConfigurationError("OAuth anti-forgery state mismatch")
    if "error" in query or not query.get("code"):
        raise MailConfigurationError("OAuth consent was refused or incomplete")
    fields=dict(client_id=pending["client_id"],
                grant_type="authorization_code",
                code=query["code"][0],
                code_verifier=pending["verifier"],
                redirect_uri=pending["redirect_uri"])
    path=pending.get("client_secret_file")
    if path:
        fields["client_secret"]=private_file(path).read_text().strip()
    endpoint=(GRAPH_TOKEN.format(tenant=pending["tenant"])
              if pending["provider"]=="graph_delegated" else GMAIL_TOKEN)
    result=_form_http(endpoint,fields)
    refreshed=result.get("refresh_token")
    if not isinstance(refreshed,str) or len(refreshed)<12:
        raise MailConfigurationError(
            "offline refresh grant missing; verify app consent/publishing state")
    subject=_profile(pending["provider"],result["access_token"])
    if subject != pending["sender"]:
        raise MailConfigurationError(
            "signed-in OAuth identity is not the configured sender mailbox")
    with vault.exclusive():
        vault.store(pending["provider"],pending["sender"],refreshed,
                    identity=subject)
    session_file.unlink()
    return dict(provider=pending["provider"],sender=pending["sender"],
                account_ownership_verified=True,
                token_saved_encrypted=True,
                production_send_enabled=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    choices=p.add_subparsers(dest="action",required=True)
    start_cmd=choices.add_parser("start")
    start_cmd.add_argument("--provider",choices=("graph_delegated","gmail_delegated"),required=True)
    start_cmd.add_argument("--sender",required=True)
    start_cmd.add_argument("--client-id",required=True)
    start_cmd.add_argument("--tenant",default="consumers")
    start_cmd.add_argument("--client-secret-file")
    start_cmd.add_argument("--session-file",type=Path,required=True)
    finish_cmd=choices.add_parser("finish")
    finish_cmd.add_argument("--session-file",type=Path,required=True)
    finish_cmd.add_argument("--vault-dir",type=Path,required=True)
    finish_cmd.add_argument("--vault-key-file",type=Path,required=True)
    init=choices.add_parser("init-vault")
    init.add_argument("--vault-dir",type=Path,required=True)
    init.add_argument("--vault-key-file",type=Path,required=True)
    args=p.parse_args()
    if args.action=="init-vault":
        print(json.dumps(init_vault(vault_dir=args.vault_dir,key_file=args.vault_key_file)))
    elif args.action=="start":
        print("Open this URL in your own browser; do not send it in chat:")
        print(start(provider=args.provider,sender=args.sender,
                    client_id=args.client_id,tenant=args.tenant,
                    state_path=args.session_file,
                    client_secret_file=args.client_secret_file))
        print("After consent, run the finish command and enter the full browser redirect URL.")
    else:
        redirect=getpass.getpass("Paste full redirected localhost URL (hidden): ")
        print(json.dumps(finish(
            session_file=args.session_file,redirect_url=redirect,
            vault=EncryptedRefreshVault(args.vault_dir,args.vault_key_file))))
if __name__=="__main__":
    main()
