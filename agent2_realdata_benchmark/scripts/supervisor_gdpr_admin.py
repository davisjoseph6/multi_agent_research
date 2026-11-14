"""Offline private GDPR admin CLI for fictional .test participants ONLY.

This is NOT an authenticated institutional admin interface. Never run with
real student records. A real PI-controlled platform needs distinct operator
credentials, review/audit trails and a verified email provider.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_synthetic_store import (
    SupervisorSyntheticStore, SyntheticStudyError,
)
from src.prototype.supervisor_consent_texts import (
    KEEP_CONFIRMATION, DELETE_CONFIRMATION,
)


BANK=Path(__file__).resolve().parents[1]/"data"/"supervisor_20261111"


def private_folder(path: Path) -> Path:
    path=path.expanduser()
    if not path.is_dir() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise SyntheticStudyError("existing 0700 nonsymlink local directory required")
    return path


def export_points(store: SupervisorSyntheticStore, output: Path) -> int:
    """Refuse overwrite and create a 0600 CSV with email/completed_at only."""
    output=Path(output).expanduser()
    if output.name!="points_export.csv" or output.is_symlink():
        raise SyntheticStudyError("private points_export.csv output path required")
    private_folder(output.parent)
    rows=store.points_export()
    fd=os.open(output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="") as file:
            writer=csv.DictWriter(file,fieldnames=["email","completed_at"])
            writer.writeheader()
            writer.writerows(rows)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return len(rows)


def close_fictional_collection(
    store: SupervisorSyntheticStore, *,
    backups: Path, points_file: Path,
) -> dict:
    """Close after points export, purge known fictional contact backup copy."""
    backups=private_folder(Path(backups))
    points_file=Path(points_file).expanduser()
    if (points_file.name!="points_export.csv" or points_file.is_symlink()
            or not points_file.is_file() or points_file.stat().st_mode & 0o077):
        raise SyntheticStudyError("private points export must precede closure")
    with store._tx() as db:
        active=db.execute(
            "SELECT COUNT(*) FROM participants WHERE status='active'"
        ).fetchone()[0]
        all_fake=db.execute(
            "SELECT COUNT(*) FROM participants WHERE learner_id "
            "NOT LIKE 'SYN_SUPERVISOR_P%'"
        ).fetchone()[0]
        if active or all_fake:
            raise SyntheticStudyError(
                "all fictional sessions must be closed before contact purge"
            )
    response=store.close_collection()
    removed=[]
    for filename in (
        "supervisor_fictional_contacts.sqlite3",
        "fictional_backup_manifest.json",
    ):
        target=backups/filename
        if target.is_symlink():
            raise SyntheticStudyError("refusing symlinked backup artifact")
        if target.is_file():
            target.unlink()
            removed.append(filename)
    return {**response,"fictional_contact_backups_purged":removed,
            "physical_media_wipe_certified":False}


def main(argv=None):
    parser=argparse.ArgumentParser(
        description="PRIVATE FICTIONAL GDPR admin; real student data forbidden")
    parser.add_argument("--state-dir",type=Path,required=True)
    operations=parser.add_subparsers(dest="action",required=True)
    withdraw=operations.add_parser("withdraw")
    withdraw.add_argument("learner_id")
    withdraw.add_argument("--delete",action="store_true")
    withdraw.add_argument("--confirm",action="store_true")
    points=operations.add_parser("points_export")
    points.add_argument("--out",type=Path,required=True)
    close=operations.add_parser("close_collection")
    close.add_argument("--backups-dir",type=Path,required=True)
    close.add_argument("--points-export",type=Path,required=True)
    close.add_argument("--confirm",action="store_true")
    args=parser.parse_args(argv)
    root=private_folder(args.state_dir)
    store=SupervisorSyntheticStore(root,bank=SupervisorBank(BANK))
    if args.action=="withdraw":
        if not args.confirm:
            parser.error("must pass --confirm to proceed")
        result=store.offline_admin_withdraw(
            args.learner_id,delete=args.delete,
            at=datetime.now(timezone.utc),channel="email",
        )
        text=DELETE_CONFIRMATION if args.delete else KEEP_CONFIRMATION
        print(json.dumps({
            "fictional_action":"withdrawal_delete" if args.delete else "withdrawal_keep",
            "fictional_recipient":result["fictional_confirmation_recipient"],
            "confirmation_preview":text,
            "real_email_sent":False,
        },ensure_ascii=False))
    elif args.action=="points_export":
        print(json.dumps({"fictional_completed_export_rows":
                          export_points(store,args.out),"real_email_sent":False}))
    else:
        if not args.confirm:
            parser.error("must pass --confirm to close collection")
        print(json.dumps(close_fictional_collection(
            store,backups=args.backups_dir,
            points_file=args.points_export,
        ),ensure_ascii=False))


if __name__=="__main__":
    main()
