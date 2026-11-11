"""Quiescent private backup and end-of-collection fake-contact purge only.

This does NOT implement encrypted, remotely monitored, production daily
backups. The operator must stop the fictional web server before backup.
Real contacts, live database names, and public destinations are rejected.
"""
from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from .supervisor_synthetic_store import SupervisorSyntheticStore,SyntheticStudyError

BACKUPS=(
    ("research","supervisor_fictional_study.sqlite3"),
    ("contacts","supervisor_fictional_contacts.sqlite3"),
)


def _check_only_fake(store):
    with store._tx() as db:
        contacts=db.execute(
            "SELECT email FROM pii.contacts ORDER BY learner_id"
        ).fetchall()
        if any(not str(r["email"]).lower().endswith(".test") for r in contacts):
            raise SyntheticStudyError("nonfictional contact blocks backup/purge")
        if db.execute(
            "SELECT COUNT(*) FROM participants "
            "WHERE learner_id NOT LIKE 'SYN_SUPERVISOR_P%'"
        ).fetchone()[0]:
            raise SyntheticStudyError("nonfictional participant blocks backup/purge")
        return len(contacts)


def backup_private_fictional(
    store: SupervisorSyntheticStore, destination: str | Path,
) -> dict:
    if not isinstance(store,SupervisorSyntheticStore):
        raise TypeError("isolated synthetic store required")
    target=Path(destination)
    if (not target.is_dir() or target.is_symlink()
            or target.stat().st_mode & 0o077):
        raise SyntheticStudyError("pre-existing 0700 local backup folder required")
    _check_only_fake(store)
    if any((target/name).exists() for _,name in BACKUPS):
        raise SyntheticStudyError("refusing to overwrite an existing backup")
    manifest=target/"fictional_backup_manifest.json"
    if manifest.exists():
        raise SyntheticStudyError("backup manifest already exists")
    hashes={}
    for _kind,name in BACKUPS:
        source=store.folder/name
        output=target/name
        if not source.is_file() or source.is_symlink():
            raise SyntheticStudyError("missing or symlinked local database")
        with sqlite3.connect(source) as src,sqlite3.connect(output) as dst:
            src.backup(dst)
            ok=dst.execute("PRAGMA integrity_check").fetchone()[0]
            if ok!="ok":
                raise SyntheticStudyError("SQLite backup failed integrity check")
        output.chmod(0o600)
        hashes[name]=sha256(output.read_bytes()).hexdigest()
    report={
        "kind":"FICTIONAL_PRIVATE_BACKUP_NOT_PRODUCTION",
        "created_at":datetime.now(timezone.utc).isoformat(),
        "sha256":hashes,
        "human_enrollment_authorized":False,
        "contains_real_contacts":False,
    }
    manifest.write_text(json.dumps(report,sort_keys=True,indent=2),encoding="utf-8")
    manifest.chmod(0o600)
    return report


def purge_fake_contacts_after_collection(
    store: SupervisorSyntheticStore, *, collection_closed: bool,
) -> int:
    if collection_closed is not True:
        raise SyntheticStudyError("explicit fictional end-of-collection gate required")
    _check_only_fake(store)
    with store._tx() as db:
        rows=db.execute(
            "SELECT COUNT(*) FROM participants WHERE status='active'"
        ).fetchone()[0]
        if rows:
            raise SyntheticStudyError("cannot purge while fictional learners active")
        count=db.execute(
            "SELECT COUNT(*) FROM pii.contacts"
        ).fetchone()[0]
        db.execute("DELETE FROM pii.contacts")
    return count
