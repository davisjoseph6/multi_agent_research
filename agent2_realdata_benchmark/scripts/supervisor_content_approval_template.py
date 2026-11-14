"""Generate an UNSIGNED PI review inventory for exact source/content files.

This is NOT a release authorizer. Only the institution may review the
resources and sign the finalized, commit-pinned approval using a separately
verified institutional key. Existing source Annex placeholders block live.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from src.prototype.supervisor_content_approval import FILES
from src.prototype.supervisor_consent_texts import (
    CONSENT_VERSION, NONREWARD_CONSENT_VERSION,
)
from src.prototype.supervisor_recovery_content import CONTENT_VERSION

ROOT=Path(__file__).resolve().parents[1]


def build_inventory(root: Path, commit: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{40}",commit):
        raise ValueError("full exact commit SHA is required")
    digests={}
    blockers=[]
    for relative in FILES:
        file=root/relative
        if not file.is_file() or file.is_symlink():
            raise ValueError("missing or symlinked study resource: "+relative)
        data=file.read_bytes()
        digests[relative]=sha256(data).hexdigest()
        if relative.endswith(".html") and re.search(
            r"\[[^\[\]\r\n]{2,100}\]",data.decode("utf-8")
        ):
            blockers.append(relative+": contains unfilled legal placeholders")
    return {
        "schema":"SUPERVISOR_APPROVED_CONTENT_V1",
        "decision":"pending",
        "candidate_commit":commit,
        "content_version":CONTENT_VERSION,
        "consent_versions":[CONSENT_VERSION,NONREWARD_CONSENT_VERSION],
        "reviewer":"",
        "role":"principal_investigator",
        "approved_at":None,
        "files_sha256":digests,
        "blocking_issues":blockers,
        "warning":"UNSIGNED REVIEW TEMPLATE; NEVER evidence of approval.",
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--commit",required=True)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    if not args.output.is_absolute() or args.output.exists() or args.output.is_symlink():
        p.error("new absolute private output path required")
    data=build_inventory(ROOT,args.commit)
    old=os.umask(0o077)
    try:
        fd=os.open(args.output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(data,f,indent=2,sort_keys=True,ensure_ascii=False)
            f.write("\n")
    finally:
        os.umask(old)
    print("Unsigned PI review inventory created with",len(data["files_sha256"]),"files.")
    print("Unfilled Annex files:",len(data["blocking_issues"]))
    print("No decision has been approved or signed; live enrollment remains disabled.")


if __name__=="__main__":
    main()
