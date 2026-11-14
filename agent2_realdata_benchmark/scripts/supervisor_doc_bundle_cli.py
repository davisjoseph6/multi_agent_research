"""Private release-document staging, verification and authorized activation CLI.

No command signs on behalf of the institution. No command accepts placeholders
as approved PDFs. Production activation additionally runs the original 14-gate
signed release + PI content gate, exact Git commit and LIVE environment checks.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess

from src.prototype.supervisor_release_documents import (
    DocumentReleaseError,new_draft,revise,verify,verify_current,activate,
)
from scripts.supervisor_vps_wsgi import _release_verified, ROOT


def _verify_live_environment(release_commit):
    if os.environ.get("SUPERVISOR_VPS_MODE") != "live":
        raise DocumentReleaseError("real release activation is forbidden outside LIVE")
    if os.environ.get("SUPERVISOR_VPS_COMMIT") != release_commit:
        raise DocumentReleaseError("exact release environment/source mismatch")
    actual=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT.parent,
                          check=True,text=True,capture_output=True,timeout=8).stdout.strip()
    dirty=subprocess.run(["git","status","--porcelain"],cwd=ROOT.parent,
                         check=True,text=True,capture_output=True,timeout=8).stdout.strip()
    if actual!=release_commit or dirty:
        raise DocumentReleaseError("source checkout is not exact and clean")
    return _release_verified(release_commit)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry",type=Path,required=True)
    p.add_argument("--commit",required=True)
    p.add_argument("--institution-public-key",type=Path)
    action=p.add_mutually_exclusive_group(required=True)
    action.add_argument("--draft-source",type=Path)
    action.add_argument("--refresh-source",type=Path)
    action.add_argument("--verify-version",type=Path)
    action.add_argument("--verify-current",action="store_true")
    action.add_argument("--activate-version",type=Path)
    args=p.parse_args()
    if args.draft_source:
        folder=new_draft(args.registry,release_commit=args.commit,
                         source_dir=args.draft_source)
        result=dict(version=str(folder),status="pending",
                    signing_permitted_by_software=False,
                    human_enrollment_authorized=False)
    elif args.refresh_source:
        folder=revise(args.registry,release_commit=args.commit,
                      source_dir=args.refresh_source)
        result=dict(version=str(folder),status="pending",
                    previous_version_preserved=True,
                    human_enrollment_authorized=False)
    else:
        if not args.institution_public_key:
            p.error("trusted institutional public key required for verification")
        if args.verify_current:
            bundle=verify_current(registry_root=args.registry,
                                  release_commit=args.commit,
                                  public_key=args.institution_public_key)
        elif args.verify_version:
            bundle=verify(args.verify_version,release_commit=args.commit,
                          signature=args.verify_version/"manifest.sig",
                          institutional_public_key=args.institution_public_key)
        else:
            if not args.activate_version:
                p.error("activation revision is required")
            bundle=activate(
                registry_root=args.registry,version=args.activate_version,
                release_commit=args.commit,public_key=args.institution_public_key,
                institutional_release_check=_verify_live_environment,
            )
        result=dict(bundle_id=bundle.bundle_id,
                    manifest_sha256=bundle.manifest_sha256,
                    source_commit=bundle.release_commit,
                    signed_documents=len(bundle.documents),
                    mode="activated" if args.activate_version else "verified",
                    human_enrollment_authorized_by_this_tool=False)
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
