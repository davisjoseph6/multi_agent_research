"""One-shot fictional daily reminder and missed-session job.

Cron/systemd can call this local dry-run with an explicitly selected synthetic
0700 state directory and approved-for-TEST grace interval. No email is sent.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.supervisor_gdpr_admin import BANK, private_folder
from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore
from src.prototype.supervisor_daily_operations import dry_run_daily


def main(argv=None):
    p=argparse.ArgumentParser(description="Private synthetic session scheduler")
    p.add_argument("--state-dir",required=True,type=Path)
    p.add_argument("--grace-hours",required=True,type=int)
    p.add_argument("--at",help="timezone-aware ISO date/time; default current UTC")
    a=p.parse_args(argv)
    at=(datetime.fromisoformat(a.at) if a.at
        else datetime.now(timezone.utc))
    store=SupervisorSyntheticStore(
        private_folder(a.state_dir),bank=SupervisorBank(BANK),
    )
    print(json.dumps(dry_run_daily(
        store,at=at,grace_hours=a.grace_hours,
    ),ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
