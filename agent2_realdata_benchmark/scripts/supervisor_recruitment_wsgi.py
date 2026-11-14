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
from src.prototype.supervisor_mail_providers import (
    build_mail_router, EncryptedRefreshVault, MailDeliveryJournal,
)
from scripts.supervisor_vps_wsgi import BANK
from src.prototype.supervisor_release_documents import verify_current

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
        bundle=verify_current(
            registry_root=os.environ["SUPERVISOR_DOC_BUNDLE_ROOT"],
            release_commit=commit,
            public_key=os.environ["SUPERVISOR_INSTITUTION_PUBLIC_KEY"],
        )
        # Institutionally signed manifest binds all bilingual privacy PDF
        # hashes, so no single unapproved notice can be substituted.
        privacy_notices={
            language:bundle.file(f"recruitment_privacy_{language}")
            for language in ("en","fr")
        }
    ledger=RecruitmentLedger(root)
    dispatcher=None
    mailer=None
    store=None
    if mode=="live":
        if os.environ.get("SUPERVISOR_MAIL_TRANSPORT")!="microsoft_graph":
            raise RuntimeError("institutionally authorized Microsoft Graph transport required")
        if os.environ.get("SUPERVISOR_MAIL_TRANSPORT") != "provider_router":
            raise RuntimeError("signed, provider-neutral email route configuration required")
        vault=None
        if os.environ.get("SUPERVISOR_MAIL_VAULT_DIR"):
            vault=EncryptedRefreshVault(
                os.environ["SUPERVISOR_MAIL_VAULT_DIR"],
                os.environ["SUPERVISOR_MAIL_VAULT_KEY_FILE"],
            )
        journal=MailDeliveryJournal(
            os.environ["SUPERVISOR_MAIL_AUDIT_DB"],
            os.environ["SUPERVISOR_MAIL_AUDIT_KEY_FILE"],
        )
        mailer=build_mail_router(
            config_file=os.environ["SUPERVISOR_MAIL_CONFIG"],
            approval_file=os.environ["SUPERVISOR_MAIL_APPROVAL"],
            approval_signature=os.environ["SUPERVISOR_MAIL_APPROVAL_SIGNATURE"],
            institution_key=os.environ["SUPERVISOR_INSTITUTION_PUBLIC_KEY"],
            release_commit=commit,vault=vault,journal=journal,
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
        intake_rate_secret=(
            os.environ["SUPERVISOR_INTAKE_RATE_SECRET"].encode("utf-8")
            if mode=="live" else None
        ),
    )
