"""Offline-only administrative controls for a separately gated VPS study.

Never expose these commands as web routes. STAGING generates reserved .example
links into a mode-0600 file; it never delivers mail. LIVE sending requires
institutional release verification, an authorized sender and SMTP STARTTLS.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.message import EmailMessage
import json
import os
from pathlib import Path
import smtplib
import ssl

from scripts.supervisor_vps_wsgi import BANK, _release_verified
from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_operational_intake import OperationalIntake
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore


def load():
    root=Path(os.environ["SUPERVISOR_VPS_ROOT"])
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise ValueError("existing non-symlink absolute private state directory needed")
    mode=os.environ.get("SUPERVISOR_VPS_MODE","staging")
    if mode not in ("staging","live"):
        raise ValueError("unknown mode")
    programs=tuple(v.strip() for v in os.environ.get(
        "SUPERVISOR_PROGRAMS",""
    ).split("|") if v.strip())
    if not programs:
        raise ValueError("one approved academic program required")
    if mode=="live":
        if not _release_verified(os.environ["SUPERVISOR_VPS_COMMIT"]):
            raise ValueError("institutional release is not approved")
    store=SupervisorSyntheticStore(root,bank=SupervisorBank(BANK),operational=True)
    return OperationalIntake(store,programs=programs),mode


def write_private(path: Path, value: str):
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("private output must be absolute, not a symlink")
    flags=os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):
        flags|=os.O_NOFOLLOW
    fd=os.open(str(path),flags,0o600)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as file:
            file.write(value+"\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def deliver(recipient: str, link: str, *, mode: str):
    if mode!="live":
        raise ValueError("SMTP delivery disabled outside live approved release")
    host=os.environ["SUPERVISOR_SMTP_HOST"]
    port=int(os.environ.get("SUPERVISOR_SMTP_PORT","587"))
    sender=os.environ["SUPERVISOR_SMTP_FROM"]
    user=os.environ["SUPERVISOR_SMTP_USER"]
    password=os.environ["SUPERVISOR_SMTP_PASSWORD"]
    if not (host and sender and user and password) or not 1<=port<=65535:
        raise ValueError("authenticated STARTTLS sender required")
    msg=EmailMessage()
    msg["From"]=sender
    msg["To"]=recipient
    msg["Subject"]="Private link for the Adaptive Learning Study"
    msg.set_content(
        "Hello,\n\n"
        "You have been invited to a three-session adaptive learning study. "
        "Read the information sheet and complete consent before registering.\n\n"
        "Your personal link (do not share):\n"+link+"\n\n"
        "You may stop taking part at any time using the link at the bottom "
        "of the participant portal. Please reply to this email with any "
        "questions about the study or your data rights.\n\n"
        "Study coordination team\n"
    )
    with smtplib.SMTP(host,port,timeout=25) as client:
        client.ehlo()
        client.starttls(context=ssl.create_default_context())
        client.ehlo()
        client.login(user,password)
        client.send_message(msg)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--issue",metavar="EMAIL")
    group.add_argument("--counts",action="store_true")
    group.add_argument("--withdraw-verified-ref",metavar="STUDY_PNNN")
    parser.add_argument("--withdraw-mode",choices=("keep","delete"))
    parser.add_argument("--verification-record",type=Path,
                        help="absolute private JSON evidence reviewed by authorized staff")
    parser.add_argument("--output",type=Path,
                        help="absolute, new mode-0600 file containing secret link")
    parser.add_argument("--send",action="store_true",
                        help="LIVE only, deliver invitation via verified SMTP")
    args=parser.parse_args()
    intake,mode=load()
    if args.counts:
        with intake.store._tx() as db:
            counts={row["status"]:row["n"] for row in db.execute(
                "SELECT status, COUNT(*) AS n FROM participants GROUP BY status")}
            invitations=db.execute(
                "SELECT COUNT(*) FROM pii.invitations WHERE state='invited'"
            ).fetchone()[0]
        print(json.dumps(dict(mode=mode,participant_counts=counts,
                              unclaimed_invitations=invitations,
                              no_personal_details=True),indent=2))
        return
    if args.withdraw_verified_ref:
        evidence=args.verification_record
        if not args.withdraw_mode or evidence is None:
            parser.error("withdrawal mode and identity-verification record required")
        if not evidence.is_absolute() or not evidence.is_file() or evidence.is_symlink():
            parser.error("existing private identity-verification record required")
        record=json.loads(evidence.read_text(encoding="utf-8"))
        if (type(record) is not dict or record.get("identity_verified") is not True
                or record.get("channel")!="email"
                or not isinstance(record.get("reviewer"),str)
                or len(record["reviewer"].strip())<3
                or not isinstance(record.get("institutional_ticket"),str)
                or not record["institutional_ticket"].strip()):
            parser.error("independent staff verification record incomplete")
        result=intake.store.offline_admin_withdraw(
            args.withdraw_verified_ref,
            delete=(args.withdraw_mode=="delete"),
            at=datetime.now(timezone.utc),channel="email",
        )
        print(json.dumps({
            "withdrawn":result["withdrawn"],
            "data_deleted":result["data_deleted"],
            "channel":"verified_offline_email",
            "email_sent":False,
            "identity_authority_verified_by_software":False,
        },indent=2))
        return
    if args.send and mode!="live":
        parser.error("--send is disabled for all staging deployments")
    if args.output is None:
        parser.error("--output is required for an invitation")
    host=os.environ["SUPERVISOR_VPS_HOST"]
    if not host or "/" in host or ":" in host:
        parser.error("canonical host is required")
    token=intake.issue(args.issue,at=datetime.now(timezone.utc),
                       allow_example=(mode=="staging"))
    link=f"https://{host}/study/#invite={token}"
    write_private(args.output,link)
    print("Private invitation file created (mode 0600); no token printed.")
    if args.send:
        deliver(args.issue,link,mode=mode)
        print("SMTP server accepted the message. Delivery to inbox is not guaranteed.")
    else:
        print("No email sent. Staging links are for reserved test identities only.")


if __name__=="__main__":
    main()
