"""Offline, authenticated AES-256-GCM paired database backup and restore drill.

This tool refuses backups while the production-structured staging service
is running. Stop that service first. The tool never overwrites or restores
the production databases; verification decrypts entirely in process memory.
Offsite replication and scheduled operations require institution approval.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.prototype.supervisor_operational_backup import (
    snapshot_pair, verify_encrypted_backup,
)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--create",action="store_true")
    mode.add_argument("--verify",action="store_true")
    parser.add_argument("--state-dir",type=Path)
    parser.add_argument("--encrypted-file",required=True,type=Path)
    parser.add_argument("--key-file",required=True,type=Path)
    args=parser.parse_args()
    if args.create:
        if args.state_dir is None:
            parser.error("--state-dir required for paired database snapshot")
        summary=snapshot_pair(args.state_dir,args.encrypted_file,args.key_file)
    else:
        summary=verify_encrypted_backup(args.encrypted_file,args.key_file)
        summary={
            "verified_encrypted_restore":summary["restore_integrity"]=="ok",
            "database_count":len(summary["source_files"]),
            "production_database_not_modified":True,
            "offsite_replication_not_verified":True,
        }
    print(json.dumps(summary,sort_keys=True,indent=2))


if __name__=="__main__":
    main()
