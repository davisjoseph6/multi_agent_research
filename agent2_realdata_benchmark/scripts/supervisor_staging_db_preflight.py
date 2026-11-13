"""Read-only staging database preflight.

Run as the restricted study service user. All queries use SQLite mode=ro;
no invitation tokens, email addresses, student names, or raw responses are
included in the output. This is NOT institutional ethics or live-release
approval and does not change any study or Caddy configuration.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import quote


def _file_uri(path: Path) -> str:
    return "file:" + quote(str(path), safe="/") + "?mode=ro"


def inspect_state(root: Path) -> dict:
    root=Path(root)
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise ValueError("absolute nonsymlink existing state directory required")
    study=root/"supervisor_operational_study.sqlite3"
    contacts=root/"supervisor_operational_contacts.sqlite3"
    for item in (study,contacts):
        if not item.is_file() or item.is_symlink():
            raise ValueError("both non-symlink operational SQLite databases required")
    db=sqlite3.connect(_file_uri(study),uri=True,timeout=10)
    db.row_factory=sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("ATTACH DATABASE ? AS pii",(_file_uri(contacts),))
        research_check=db.execute("PRAGMA main.quick_check").fetchone()[0]
        contact_check=db.execute("PRAGMA pii.quick_check").fetchone()[0]
        fk_issues=db.execute("PRAGMA main.foreign_key_check").fetchall()
        group_counts={row["grp"]:row["n"] for row in db.execute(
            "SELECT grp,COUNT(*) AS n FROM participants GROUP BY grp")}
        states={row["status"]:row["n"] for row in db.execute(
            "SELECT status,COUNT(*) AS n FROM participants GROUP BY status")}
        missing_contact=db.execute(
            "SELECT COUNT(*) FROM participants p LEFT JOIN pii.contacts c "
            "ON c.learner_id=p.learner_id WHERE c.learner_id IS NULL"
        ).fetchone()[0]
        mismatch=db.execute(
            "SELECT COUNT(*) FROM pii.invitations i JOIN pii.contacts c "
            "ON i.learner_id=c.learner_id "
            "WHERE i.state='registered' AND i.token_hash!=c.token_hash"
        ).fetchone()[0]
        completed_without_end=db.execute(
            "SELECT COUNT(*) FROM sessions "
            "WHERE status='completed' AND ended_at IS NULL"
        ).fetchone()[0]
        wrong_session_count=db.execute(
            "SELECT COUNT(*) FROM participants p WHERE "
            "(SELECT COUNT(*) FROM sessions s "
            "WHERE s.learner_id=p.learner_id)!=3"
        ).fetchone()[0]
        unused=db.execute(
            "SELECT COUNT(*) FROM pii.invitations WHERE state='invited'"
        ).fetchone()[0]
        checked={
            "research_sqlite_integrity":research_check=="ok",
            "contacts_sqlite_integrity":contact_check=="ok",
            "research_foreign_keys":len(fk_issues)==0,
            "every_participant_has_private_contact":missing_contact==0,
            "registered_credentials_consistent":mismatch==0,
            "completed_sessions_have_end_times":completed_without_end==0,
            "three_session_rows_per_participant":wrong_session_count==0,
        }
        return {
            "technical_db_checks":checked,
            "passed":all(checked.values()),
            "participant_counts_by_status":states,
            "allocation_counts_by_arm":group_counts,
            "unclaimed_invitation_count":unused,
            "contains_identifying_contact_details":False,
            "mutated_database":False,
            "real_human_recruitment_approved":False,
            "institutional_release_evidence_reviewed":False,
        }
    finally:
        db.close()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir",type=Path,
        default=Path(os.environ.get("SUPERVISOR_VPS_ROOT","/nonexistent")))
    a=parser.parse_args()
    result=inspect_state(a.state_dir)
    print(json.dumps(result,indent=2,sort_keys=True))
    if not result["passed"]:
        raise SystemExit(1)


if __name__=="__main__":
    main()
