"""Separate Gunicorn entrypoint for protected recruitment and admin preview.

No public questionnaire or email delivery in staging. LIVE can be enabled
ONLY after the same cryptographic institutional and content approval check
used by the participant /study/ WSGI, plus a reviewed privacy notice and
individually configured Microsoft/Outlook mailbox permissions.

Do not add this service to the existing Caddy public routes automatically.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

from scripts.supervisor_vps_wsgi import _release_verified
from src.prototype.supervisor_recruitment import RecruitmentLedger
from src.prototype.supervisor_recruitment_web import make_recruitment_app
from src.prototype.supervisor_recruitment_dispatch import InvitationDispatcher
from src.prototype.supervisor_operational_intake import OperationalIntake
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore
from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_graph_mail import GraphMailSender
from scripts.supervisor_vps_wsgi import BANK

ROOT=Path(__file__).resolve().parents[1]


def make_wsgi_app():
    mode=os.environ.get("SUPERVISOR_VPS_MODE","staging")
    if mode not in ("staging","live"):
        raise RuntimeError("invalid study release mode")
    root=Path(os.environ.get("SUPERVISOR_VPS_ROOT",""))
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise RuntimeError("existing protected state directory required")
    host=os.environ.get("SUPERVISOR_RECRUITMENT_HOST","localhost")
    commit=os.environ.get("SUPERVISOR_VPS_COMMIT","")
    if len(commit)!=40:
        raise RuntimeError("exact source revision required")
    if mode=="live":
        actual=subprocess.run(["git","rev-parse","HEAD"],
                     cwd=ROOT.parent,capture_output=True,
                     text=True,check=True,timeout=5).stdout.strip()
        if actual!=commit:
            raise RuntimeError("LIVE recruitment commit does not match reviewed release")
        dirty=subprocess.run(["git","status","--porcelain"],cwd=ROOT.parent,
                     capture_output=True,text=True,check=True,
                     timeout=5).stdout.strip()
        if dirty:
            raise RuntimeError("LIVE recruitment checkout is modified")
        if not _release_verified(commit):
            raise RuntimeError("institutional signed LIVE release required")
        if not os.environ.get("SUPERVISOR_APPROVED_RECRUITMENT_NOTICE"):
            raise RuntimeError("approved public recruitment privacy notice required")
        if host in ("localhost","demo.selfhealing-edu.fr") or "demo" in host:
            raise RuntimeError("non-demo canonical recruitment domain required")
    else:
        record=ROOT.parent/".supervisor-source-revision"
        if not record.is_file() or record.read_text().strip()!=commit:
            raise RuntimeError("staging source marker mismatch")
    privacy_notices=None
    if mode=="live":
        privacy_notices={}
        public_key=Path(os.environ["SUPERVISOR_INSTITUTION_PUBLIC_KEY"])
        if not public_key.is_file() or public_key.is_symlink():
            raise RuntimeError("trusted institutional signing key required")
        for language in ("en","fr"):
            document=Path(os.environ[f"SUPERVISOR_RECRUITMENT_NOTICE_{language.upper()}"])
            signature=Path(os.environ[f"SUPERVISOR_RECRUITMENT_NOTICE_SIGNATURE_{language.upper()}"])
            if (not document.is_absolute() or document.suffix.lower()!=".pdf"
                    or not document.is_file() or document.is_symlink()
                    or not signature.is_file() or signature.is_symlink()):
                raise RuntimeError("approved bilingual recruitment notice and signature required")
            check=subprocess.run([
                "openssl","dgst","-sha256","-verify",str(public_key),
                "-signature",str(signature),str(document)],
                capture_output=True,text=True,timeout=10,check=False)
            if check.returncode!=0:
                raise RuntimeError("institutional bilingual recruitment notice signature invalid")
            privacy_notices[language]=document
    ledger=RecruitmentLedger(root)
    dispatcher=None
    mailer=None
    store=None
    if mode=="live":
        if os.environ.get("SUPERVISOR_MAIL_TRANSPORT")!="microsoft_graph":
            raise RuntimeError("institutionally authorized Microsoft Graph transport required")
        mailer=GraphMailSender(
            tenant_id=os.environ["SUPERVISOR_GRAPH_TENANT_ID"],
            client_id=os.environ["SUPERVISOR_GRAPH_CLIENT_ID"],
            client_secret=os.environ["SUPERVISOR_GRAPH_CLIENT_SECRET"],
            sender_email=os.environ["SUPERVISOR_GRAPH_SENDER_EMAIL"],
            live_release_verified=True,
        )
        study_host=os.environ.get("SUPERVISOR_VPS_HOST","")
        if not study_host or "demo" in study_host:
            raise RuntimeError("real participant study must use canonical non-demo domain")
        store=SupervisorSyntheticStore(
            root,bank=SupervisorBank(BANK),operational=True)
        programs=tuple(v.strip() for v in os.environ.get(
            "SUPERVISOR_PROGRAMS",""
        ).split("|") if v.strip())
        intake=OperationalIntake(store,programs=programs,inactivity_days=7)
        dispatcher=InvitationDispatcher(
            intake=intake,ledger=ledger,sender=mailer,
            hostname=study_host,live_verified=True,
        )
    return make_recruitment_app(
        ledger,
        hostname=host,proxy_mode=mode=="live",
        public_intake_enabled=mode=="live",
        research_db=root/"supervisor_operational_study.sqlite3",
        contacts_db=root/"supervisor_operational_contacts.sqlite3",
        dispatcher=dispatcher,inactivity_sender=mailer,
        operational_store=store,live_verified=mode=="live",
        privacy_notices=privacy_notices,
    )
