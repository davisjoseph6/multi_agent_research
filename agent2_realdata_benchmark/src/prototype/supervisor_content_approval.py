"""Cryptographic approval of the EXACT deployed instructional content.

The committed teaching resources are draft-labelled because review evidence
was not supplied with the source. Once an institution approves their exact
bytes, the separately signed manifest must bind the PI, all content files,
consent versions and the release commit. No editable JSON flag alone
authorizes enrollment. No keys or signed evidence are stored in Git.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from hmac import compare_digest
import json
from pathlib import Path
import re
import subprocess

from .supervisor_recovery_content import CONTENT_VERSION
from .supervisor_consent_texts import CONSENT_VERSION, NONREWARD_CONSENT_VERSION

FILES = (
    "src/prototype/supervisor_recovery_content.py",
    "src/prototype/supervisor_fr_resources.py",
    *(f"content/i18n/fr/C{i}.tsv" for i in range(1,9)),
    "content/consent/info_sheet_en_v1.0.html",
    "content/consent/info_sheet_fr_v1.0.html",
    "content/consent/info_sheet_en_v1.1_nonreward.html",
    "content/consent/info_sheet_fr_v1.1_nonreward.html",
)
SHA=re.compile(r"[a-f0-9]{64}\Z")
COMMIT=re.compile(r"[a-f0-9]{40}\Z")


def verify_signed_content_approval(root: Path, index: Path, signature: Path,
                                   public_key: Path, commit: str) -> dict:
    if not COMMIT.fullmatch(commit):
        raise ValueError("exact deployed source revision required")
    if not root.is_dir() or root.is_symlink():
        raise ValueError("trusted source root required")
    for path in (index,signature,public_key):
        if not path.is_absolute() or not path.is_file() or path.is_symlink():
            raise ValueError("signed approval evidence must be existing absolute files")
    result=subprocess.run(
        ["openssl","dgst","-sha256","-verify",str(public_key),
         "-signature",str(signature),str(index)],
        capture_output=True,text=True,timeout=15,check=False,
    )
    if result.returncode or "Verified OK" not in result.stdout:
        raise ValueError("content approval signature cannot be verified")
    data=json.loads(index.read_text(encoding="utf-8"))
    if (type(data) is not dict
        or data.get("schema")!="SUPERVISOR_APPROVED_CONTENT_V1"
        or data.get("decision")!="approved"
        or data.get("candidate_commit")!=commit
        or data.get("content_version")!=CONTENT_VERSION
        or data.get("consent_versions")!=[
            CONSENT_VERSION, NONREWARD_CONSENT_VERSION
        ]
        or type(data.get("reviewer")) is not str
        or len(data["reviewer"].strip())<3
        or data.get("role")!="principal_investigator"):
        raise ValueError("institutional content approval does not bind this release")
    try:
        reviewed=datetime.fromisoformat(data["approved_at"])
        if reviewed.tzinfo is None or reviewed.utcoffset() is None:
            raise ValueError("approval timestamp must include timezone")
    except (KeyError,TypeError,ValueError):
        raise ValueError("timezone-aware review timestamp required") from None
    actual=data.get("files_sha256")
    if type(actual) is not dict or set(actual)!=set(FILES):
        raise ValueError("missing or additional content files in signed approval")
    for relative in FILES:
        f=root/relative
        digest=actual[relative]
        if (not f.is_file() or f.is_symlink()
            or not isinstance(digest,str) or not SHA.fullmatch(digest)):
            raise ValueError("missing or malformed approved instructional file")
        content=f.read_bytes()
        if relative.endswith(".html"):
            # A signed index must never certify an Annex that still tells
            # prospective participants [email], [date], [host], etc.
            if re.search(r"\\[[^\\[\\]\\r\\n]{2,100}\\]", content.decode("utf-8")):
                raise ValueError("approved information sheet contains unfilled placeholders")
        h=sha256(content).hexdigest()
        if not compare_digest(h,digest):
            raise ValueError("deployed content differs from signed approval")
    return {
        "content_approved":True,
        "reviewer_role":"principal_investigator",
        "content_version":CONTENT_VERSION,
        "candidate_commit":commit,
        "files_verified":len(FILES),
        "institutional_signature_verified":True,
        "real_study_release_authorized_by_this_check":False,
    }
