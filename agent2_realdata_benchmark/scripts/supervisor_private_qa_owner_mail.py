"""Deliver ONE already prepared, localhost-only private QA link to the owner.

The recipient is intentionally an exact owner-declared *self-test* school
address. Never uses the LIVE recruitment dispatcher, never sends a real
research invitation, and never changes enrollment approval. Tokens and
OAuth credentials are never printed or placed on the command line.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import stat
from urllib.parse import urlsplit, parse_qs

from src.prototype.supervisor_mail_providers import (
    DelegatedOAuthSender, EncryptedRefreshVault, MailConfigurationError,
    private_file,
)

SENDER="davisjoseph767@gmail.com"
RECIPIENT="davis.joseph@aivancity.education"


def _private_dir(path: Path) -> None:
    if (not path.parent.is_dir() or path.parent.is_symlink() or
            stat.S_IMODE(path.parent.stat().st_mode)!=0o700):
        raise MailConfigurationError("private QA files require a 0700 parent")


def _read_qa_url(path: Path) -> str:
    _private_dir(path)
    text=private_file(path).read_text(encoding="utf-8").strip()
    if len(text)>900:
        raise MailConfigurationError("test link is unexpectedly long")
    parsed=urlsplit(text)
    if (parsed.scheme!="http" or parsed.netloc!="127.0.0.1:8897"
            or parsed.path!="/study/" or parsed.query
            or parsed.username or parsed.password):
        raise MailConfigurationError("only a localhost QA invitation is permitted")
    fragment=parse_qs(parsed.fragment,keep_blank_values=True)
    if set(fragment)!={"invite"} or len(fragment["invite"])!=1 or (
            re.fullmatch(r"[A-Za-z0-9_-]{40,256}",fragment["invite"][0])
            is None):
        raise MailConfigurationError("private QA fragment token is invalid")
    return text


def send_owner_qa_link(sender: DelegatedOAuthSender, *,
                       recipient: str, link_file: Path, receipt_file: Path) -> dict:
    if (sender.provider!="gmail_delegated" or sender.sender!=SENDER or
            recipient!=RECIPIENT or sender.outbound_from!=SENDER):
        raise MailConfigurationError("exact owner-Gmail to own-school QA route required")
    link=_read_qa_url(link_file)
    _private_dir(receipt_file)
    if receipt_file.exists() or receipt_file.is_symlink():
        raise MailConfigurationError("QA receipt already exists; never auto-resend")
    attempt=secrets.token_hex(12)
    details={
        "purpose":"PERSONAL_QA_INVITATION_ONLY_NOT_HUMAN_STUDY",
        "attempt_id":attempt,
        "recipient_rule":"owner_declared_school_selftest",
        "state":"uncertain",
        "created_at":datetime.now(timezone.utc).isoformat(),
    }
    fd=os.open(receipt_file,os.O_CREAT|os.O_WRONLY|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as output:
        json.dump(details,output)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    sender.send(
        to=recipient,
        subject="PRIVATE QA ONLY: IJCAI self-test invitation (not research enrollment)",
        body=(
            "This is a self-addressed engineering test, not permission to "
            "enroll in the real IJCAI research study. Its link only works "
            "while your private SSH tunnel to localhost:8897 is open.\n\n"
            +link+"\n\nNo participant grades or real study enrollment result "
            "from this test.\n"
        ),
    )
    details["state"]="provider_accepted_not_inbox_verified"
    tmp=receipt_file.parent/(receipt_file.name+"."+attempt+".tmp")
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as output:
            json.dump(details,output)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp,receipt_file)
    finally:
        tmp.unlink(missing_ok=True)
    return dict(accepted_by_provider=True,real_enrollment_authorized=False,
                real_invitation_sent=False,inbox_delivery_verified=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--link-file",type=Path,required=True)
    parser.add_argument("--receipt-file",type=Path,required=True)
    parser.add_argument("--vault-dir",type=Path,required=True)
    parser.add_argument("--vault-key-file",type=Path,required=True)
    parser.add_argument("--client-id-file",type=Path,required=True)
    parser.add_argument("--client-secret-file",type=Path,required=True)
    parser.add_argument("--recipient",required=True)
    parser.add_argument("--send",action="store_true")
    parser.add_argument("--confirm-owner-qa-only",action="store_true")
    args=parser.parse_args()
    if args.recipient!=RECIPIENT:
        parser.error("private self-test recipient must match the exact owner school account")
    link=_read_qa_url(args.link_file)
    if not args.send:
        print(json.dumps(dict(valid_private_qa_url=True,mail_sent=False,
                              release_approved=False)))
        return
    if not args.confirm_owner_qa_only:
        parser.error("explicit --confirm-owner-qa-only required")
    vault=EncryptedRefreshVault(args.vault_dir,args.vault_key_file)
    client_id=private_file(args.client_id_file).read_text().strip()
    sender=DelegatedOAuthSender(
        provider="gmail_delegated",sender=SENDER,client_id=client_id,
        client_secret_path=str(args.client_secret_file),vault=vault,
    )
    try:
        result=send_owner_qa_link(
            sender,recipient=args.recipient,
            link_file=args.link_file,receipt_file=args.receipt_file,
        )
    except Exception as exc:
        # A receipt may have been reserved: never automatically retry an
        # uncertain provider response.
        print(json.dumps(dict(result="REFUSED_OR_UNCERTAIN_DO_NOT_RESEND",
                              reason_class=type(exc).__name__)))
        raise SystemExit(2) from None
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
