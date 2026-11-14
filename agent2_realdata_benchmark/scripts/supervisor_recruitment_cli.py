"""Create one-time independent administrator credentials in private files.

Example from VPS, run as ijcai-supervisor after provisioning a private 0700
directory. Does NOT create students, send email, enable public intake or
change the existing study service.
python -m scripts.supervisor_recruitment_cli --state-dir /private/state \\
    --bootstrap-all --output-dir /private/state/initial-admin-secrets

For each researcher, transmit *only their own* secret through a secure
individual channel, then delete the protected bootstrap secret file.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import os
import secrets

from src.prototype.supervisor_recruitment import (
    ADMIN_EMAILS, RecruitmentLedger, RecruitmentError,
)


def write_private(path: Path, content: str):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as output:
            output.write(content)
    except BaseException:
        try:path.unlink(missing_ok=True)
        finally:raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir",type=Path,required=True)
    parser.add_argument("--bootstrap-all",action="store_true")
    parser.add_argument("--output-dir",type=Path)
    parser.add_argument("--counts",action="store_true")
    args=parser.parse_args()
    if args.bootstrap_all==args.counts:
        parser.error("choose exactly one of --bootstrap-all or --counts")
    ledger=RecruitmentLedger(args.state_dir)
    if args.counts:
        with ledger._tx() as db:
            n=db.execute("SELECT COUNT(*) FROM administrators").fetchone()[0]
            applicants=db.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        print(f"Registered admin accounts: {n}; confidential candidate records: {applicants}.")
        return
    directory=args.output_dir
    if (not directory or not directory.is_absolute() or directory.is_symlink()
            or not directory.is_dir() or directory.stat().st_mode&0o077):
        parser.error("bootstrap credentials require an existing private 0700 directory")
    with ledger._tx() as db:
        existing={r[0] for r in db.execute("SELECT email FROM administrators")}
    if existing:
        parser.error("bootstrap refused: administrator accounts already exist")
    for address in ADMIN_EMAILS:
        password=secrets.token_urlsafe(32)
        secret_file=directory/(address.replace("@","_at_")+".txt")
        write_private(secret_file,
                      f"Login: {address}\nTemporary password: {password}\n"
                      "Change your password at first sign-in.\n")
        ledger.provision(email=address,temporary_password=password,
                         at=datetime.now(timezone.utc))
    print("Four individual credentials provisioned. Secret files are 0600; "
          "transfer privately and securely, then destroy the originals. "
          "No passwords printed or emailed.")


if __name__=="__main__":
    main()
