"""Release-gated, one-shot operational reminder and missed-session job.

Run from a systemd timer under the dedicated service account. No SMTP in
staging. LIVE mode requires the same institutional signature check as WSGI.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.message import EmailMessage
import json
import os
import smtplib
import ssl

from scripts.supervisor_vps_admin import load
from src.prototype.supervisor_operational_scheduler import reconcile


def send_notice(to: str, subject: str, body: str):
    host=os.environ["SUPERVISOR_SMTP_HOST"]
    port=int(os.environ.get("SUPERVISOR_SMTP_PORT","587"))
    sender=os.environ["SUPERVISOR_SMTP_FROM"]
    username=os.environ["SUPERVISOR_SMTP_USER"]
    password=os.environ["SUPERVISOR_SMTP_PASSWORD"]
    if not host or not sender or not username or not password:
        raise RuntimeError("approved SMTP sender is not configured")
    mail=EmailMessage()
    mail["From"]=sender
    mail["To"]=to
    mail["Subject"]=subject
    mail["Message-ID"]=f"<supervisor-reminder-{os.urandom(12).hex()}@{sender.split('@')[-1]}>"
    mail.set_content(body)
    with smtplib.SMTP(host,port,timeout=25) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(username,password)
        smtp.send_message(mail)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grace-hours",type=int,required=True)
    parser.add_argument("--send",action="store_true")
    parser.add_argument("--at",help="timezone-aware ISO time, TEST ONLY")
    args=parser.parse_args()
    intake,mode=load()
    if args.send and mode!="live":
        parser.error("network mail disabled in staging")
    if args.at and mode=="live":
        parser.error("historical or simulated time disabled in live mode")
    when=datetime.fromisoformat(args.at) if args.at else datetime.now(timezone.utc)
    if when.tzinfo is None:
        parser.error("timezone-aware time required")
    result=reconcile(
        intake.store,at=when,grace_hours=args.grace_hours,
        send=send_notice if args.send else None,
    )
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
