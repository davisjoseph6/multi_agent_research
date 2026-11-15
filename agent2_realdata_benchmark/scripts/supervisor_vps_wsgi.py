"""Gunicorn entrypoint for the persistent supervisor /study/ service.

Staging is safe for *reserved* .example identities. A real-human deployment
requires 14/14 independent evidence, a trusted institutional digital signature,
the precise deployed commit, and separately reviewed teaching/instrument text.
No one in this repository can self-certify an institutional research release.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from src.prototype.pilot_release_evidence_gate import inspect_evidence_index
from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_operational_intake import OperationalIntake
from src.prototype.supervisor_content_approval import verify_signed_content_approval
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore
from src.prototype.supervisor_release_documents import verify_current
from src.prototype.supervisor_vps_web import make_supervisor_vps_app

ROOT=Path(__file__).resolve().parents[1]
BANK=ROOT/"data"/"supervisor_20261111"


def _release_verified(commit: str) -> bool:
    index=os.environ.get("SUPERVISOR_RELEASE_EVIDENCE")
    public_key=os.environ.get("SUPERVISOR_INSTITUTION_PUBLIC_KEY")
    signature=os.environ.get("SUPERVISOR_INSTITUTION_SIGNATURE")
    if not all((index,public_key,signature)):
        raise RuntimeError("institutional evidence and cryptographic signature required")
    for candidate in (index,public_key,signature):
        p=Path(candidate)
        if not p.is_file() or p.is_symlink():
            raise RuntimeError("only existing non-symlink private approval files allowed")
    report=inspect_evidence_index(index)
    if (report["gates_complete"]!=14 or report["issues"]
            or report["candidate_commit"]!=commit):
        raise RuntimeError("14 signed release categories must match deployed commit")
    # This authenticates the exact bytes of the indexed manifest, assuming
    # the institutional public key was verified out-of-band. A signature is
    # NOT a substitute for independent review of the underlying documents.
    verified=subprocess.run(
        ["openssl","dgst","-sha256","-verify",public_key,
         "-signature",signature,index],
        capture_output=True,text=True,timeout=10,check=False,
    )
    if verified.returncode:
        raise RuntimeError("institutional release signature verification failed")
    # A source file may still carry its historical DRAFT label. Never simply
    # flip a code flag: require a distinct institutional signature attesting
    # to the exact deployed recovery text, both language banks and BOTH
    # immutable consent versions. An index alone cannot enable live mode.
    content_manifest=os.environ.get("SUPERVISOR_CONTENT_APPROVAL")
    content_signature=os.environ.get("SUPERVISOR_CONTENT_SIGNATURE")
    if not content_manifest or not content_signature:
        raise RuntimeError("separately signed PI content approval required")
    approval=verify_signed_content_approval(
        ROOT,Path(content_manifest),Path(content_signature),
        Path(public_key),commit,
    )
    if not approval["content_approved"]:
        raise RuntimeError("content review is not approved")
    return True


def make_wsgi_app():
    mode=os.environ.get("SUPERVISOR_VPS_MODE","staging")
    if mode not in ("staging","live"):
        raise RuntimeError("invalid release mode")
    root=Path(os.environ.get("SUPERVISOR_VPS_ROOT",""))
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise RuntimeError("existing private absolute state directory required")
    host=os.environ.get("SUPERVISOR_VPS_HOST","")
    if not host:
        raise RuntimeError("canonical HTTPS hostname required")
    commit=os.environ.get("SUPERVISOR_VPS_COMMIT","")
    if not commit or len(commit)!=40:
        raise RuntimeError("full deployed commit SHA must be pinned")
    if mode=="live":
        local=subprocess.run(
            ["git","rev-parse","HEAD"],cwd=ROOT.parent,
            capture_output=True,text=True,timeout=5,check=True,
        ).stdout.strip()
        status=subprocess.run(
            ["git","status","--porcelain"],cwd=ROOT.parent,
            capture_output=True,text=True,timeout=10,check=True,
        ).stdout.strip()
        if status:
            raise RuntimeError("live checkout must be clean and reproducible")
    else:
        # A reviewed staging archive can be deployed without its .git tree.
        # Live remains restricted to an exact signed Git commit checkout.
        revision=ROOT.parent/".supervisor-source-revision"
        if not revision.is_file() or revision.is_symlink():
            raise RuntimeError("staging artifact revision must be pinned")
        local=revision.read_text(encoding="utf-8").strip()
    if local!=commit:
        raise RuntimeError("deployed source does not match pinned commit")
    programs=tuple(v.strip() for v in os.environ.get(
        "SUPERVISOR_PROGRAMS",""
    ).split("|") if v.strip())
    if not programs:
        raise RuntimeError("at least one institutionally chosen program required")
    release_ok=_release_verified(commit) if mode=="live" else False
    document_bundle=(
        verify_current(
            registry_root=os.environ["SUPERVISOR_DOC_BUNDLE_ROOT"],
            release_commit=commit,
            public_key=os.environ["SUPERVISOR_INSTITUTION_PUBLIC_KEY"],
        ) if mode=="live" else None
    )
    store=SupervisorSyntheticStore(root,bank=SupervisorBank(BANK),operational=True)
    intake=OperationalIntake(
        store,programs=programs,
        inactivity_days=7 if mode=="live" else None,
        document_bundle=document_bundle,
    )
    app=make_supervisor_vps_app(
        intake,hostname=host,proxy_mode=True,release_mode=mode,
        release_authorized=release_ok,
    )
    return app
