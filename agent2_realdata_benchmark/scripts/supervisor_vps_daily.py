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
from src.prototype.supervisor_graph_mail import GraphMailSender
from src.prototype.supervisor_recruitment import RecruitmentLedger
from src.prototype.supervisor_inactivity_worker import reconcile_inactivity


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
    parser.add_argument("--manual-ref",help="verified LIVE only: manually encourage one student after four days")
    args=parser.parse_args()
    intake,mode=load()
    if args.send and mode!="live":
        parser.error("network mail disabled in staging")
    if args.at and mode=="live":
        parser.error("historical or simulated time disabled in live mode")
    when=datetime.fromisoformat(args.at) if args.at else datetime.now(timezone.utc)
    if when.tzinfo is None:
        parser.error("timezone-aware time required")
    if args.manual_ref and (mode!="live" or not args.send):
        parser.error("--manual-ref requires an approved LIVE Graph send")
    if mode=="staging":
        result=reconcile(
            intake.store,at=when,grace_hours=args.grace_hours,
            send=None,
        )
        print(json.dumps(result,indent=2,sort_keys=True))
        return
    # The same independently signed LIVE gate was just evaluated by load().
    if args.send:
        if os.environ.get("SUPERVISOR_MAIL_TRANSPORT")!="microsoft_graph":
            parser.error("Graph mail API, not legacy SMTP, required in LIVE mode")
        graph=GraphMailSender(
            tenant_id=os.environ["SUPERVISOR_GRAPH_TENANT_ID"],
            client_id=os.environ["SUPERVISOR_GRAPH_CLIENT_ID"],
            client_secret=os.environ["SUPERVISOR_GRAPH_CLIENT_SECRET"],
            sender_email=os.environ["SUPERVISOR_GRAPH_SENDER_EMAIL"],
            live_release_verified=True,
        )
        callback=graph.send
    else:
        callback=None
    if args.manual_ref:
        sessions=dict(skipped="manual targeted check")
    else:
        sessions=reconcile(
            intake.store,at=when,grace_hours=args.grace_hours,
            send=(lambda to,subject,body:
                  callback(to=to,subject=subject,body=body))
                  if callback else None,
        )
    ledger=RecruitmentLedger(intake.store.folder)
    inactivity=reconcile_inactivity(
        intake.store,ledger,at=when,send=callback,
        live_verified=True,manual_ref=args.manual_ref,
    )
    print(json.dumps(dict(scheduled_visits=sessions,
                          incomplete_sessions=inactivity),
                     indent=2,sort_keys=True))


if __name__=="__main__":
    main()
