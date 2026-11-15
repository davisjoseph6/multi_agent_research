"""Signed LIVE runtime preflight: no mail sent and no participant enrolled.

Run as the dedicated service user with approved root-owned EnvironmentFile.
Actual approvals, exact code, signed legal PDFs, mailbox-owner policies,
encrypted OAuth grant and private databases must all be present. This does
not attest to independent pentest, DPIA or institutional signatory identity.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
from scripts.supervisor_vps_wsgi import ROOT, make_wsgi_app as study_wsgi
from scripts.supervisor_recruitment_wsgi import make_wsgi_app as recruit_wsgi
from src.prototype.supervisor_release_documents import verify_current
from src.prototype.supervisor_mail_providers import (
    verify_signed_mail_policy, MailConfigurationError
)

def report():
    if os.environ.get("SUPERVISOR_VPS_MODE")!="live":
        raise RuntimeError("NOT READY: real LIVE mode is not configured")
    commit=os.environ.get("SUPERVISOR_VPS_COMMIT","")
    actual=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT.parent,
                          text=True,capture_output=True,check=True,timeout=8).stdout.strip()
    dirty=subprocess.run(["git","status","--porcelain"],cwd=ROOT.parent,
                         text=True,capture_output=True,check=True,timeout=8).stdout.strip()
    if commit!=actual or dirty or len(commit)!=40:
        raise RuntimeError("NOT READY: source checkout is not exact/clean")
    docs=verify_current(
        registry_root=os.environ["SUPERVISOR_DOC_BUNDLE_ROOT"],
        release_commit=commit,
        public_key=os.environ["SUPERVISOR_INSTITUTION_PUBLIC_KEY"])
    route=verify_signed_mail_policy(
        os.environ["SUPERVISOR_MAIL_CONFIG"],
        os.environ["SUPERVISOR_MAIL_APPROVAL"],
        os.environ["SUPERVISOR_MAIL_APPROVAL_SIGNATURE"],
        os.environ["SUPERVISOR_INSTITUTION_PUBLIC_KEY"],
        release_commit=commit)
    if os.environ.get("SUPERVISOR_MAIL_TRANSPORT")!="provider_router":
        raise RuntimeError("NOT READY: provider-neutral signed mail route required")
    # Instantiating both WSGI apps runs their exact 14/14 core evidence,
    # PI content, signed notices, mail owner permission and config gates.
    # Do not issue any HTTP request, OAuth refresh or sendMail call.
    study=study_wsgi()
    admin=recruit_wsgi()
    assert study and admin
    return {
        "state":"ENGINEERING_PREFLIGHT_PASSED",
        "source_commit":commit,
        "signed_document_bundle":docs.bundle_id,
        "signed_document_count":len(docs.documents),
        "mail_routes_authorized":len(route["routes"]),
        "mail_default_route_defined":route["default"] in route["routes"],
        "live_wsgi_imports":"passed",
        "mail_sent":False,
        "real_participant_enrolled":False,
        "note":"Independent operator DNS/TLS/security/backup/recovery acceptance still required."
    }

if __name__=="__main__":
    try:
        print(json.dumps(report(),sort_keys=True,indent=2))
    except Exception as exc:
        # Do not echo exception text; it can reveal secret file paths.
        print(json.dumps({"state":"BLOCKED", "passed":False,
                          "error_class":type(exc).__name__,
                          "mail_sent":False,"enrollment_enabled":False}))
        raise SystemExit(2)
