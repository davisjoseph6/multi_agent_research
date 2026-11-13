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
    return make_recruitment_app(
        RecruitmentLedger(root),
        hostname=host,proxy_mode=mode=="live",
        public_intake_enabled=mode=="live",
        research_db=root/"supervisor_operational_study.sqlite3",
        contacts_db=root/"supervisor_operational_contacts.sqlite3",
    )
