"""Encrypted consistent export and read-only recovery drill for study databases.

Offline operator-only. Stop the /study/ Gunicorn worker BEFORE calling
backup; this module explicitly refuses online SQLite snapshots to avoid a
cross-file inconsistent research/PII pair. Uses authenticated AES-256-GCM
and key material from a separate mode-0600 binary secret file. The plaintext
database images live only in memory and are never copied into the backup
folder. This utility cannot certify offsite storage, disaster recovery,
physical erasure, legal retention or GDPR compliance by itself.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import zipfile

MAGIC=b"SUPERVISOR_SQLITE_AES256GCM_V1\n"
DATA_NAMES={
    "research": "supervisor_operational_study.sqlite3",
    "contacts": "supervisor_operational_contacts.sqlite3",
}


def _private_folder(path: Path):
    if not path.is_dir() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("pre-existing private folder with no group/other permissions required")


def _private_key(path: Path) -> bytes:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise ValueError("absolute existing nonsymlink backup key required")
    if path.stat().st_mode & 0o077:
        raise ValueError("backup key file must not be readable by other users")
    secret=path.read_bytes()
    if len(secret)!=32:
        raise ValueError("AES-256-GCM key must contain exactly 32 random binary bytes")
    return secret


def _assert_service_quiesced() -> None:
    # Do not rely on --force, test flags or operator-provided attestations to
    # decide if a production worker may still be writing the paired DBs.
    command=["systemctl","is-active","--quiet","ijcai-supervisor-staging"]
    result=subprocess.run(command,check=False,capture_output=True,timeout=8)
    if result.returncode==0:
        raise ValueError("stop the study service before paired database backup")


def _integrity(blob: bytes) -> str:
    if not blob.startswith(b"SQLite format 3\0"):
        raise ValueError("decrypted data is not SQLite")
    conn=sqlite3.connect(":memory:")
    try:
        conn.deserialize(blob)
        ok=conn.execute("PRAGMA integrity_check").fetchone()[0]
        if ok!="ok":
            raise ValueError("SQLite restore integrity check failed")
        return ok
    finally:
        conn.close()


def snapshot_pair(root: Path, backup: Path, key_path: Path) -> dict:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not root.is_absolute() or root.is_symlink():
        raise ValueError("absolute nonsymlink study state root required")
    _private_folder(root)
    backup=Path(backup)
    _private_folder(backup.parent)
    if not backup.is_absolute() or backup.exists() or backup.is_symlink():
        raise ValueError("backup must have a new absolute private path")
    key=_private_key(key_path)
    _assert_service_quiesced()

    data={}
    for kind,name in DATA_NAMES.items():
        path=root/name
        if not path.is_file() or path.is_symlink():
            raise ValueError("expected operational database file missing")
        # sqlite3.serialize takes a transaction-consistent snapshot while
        # systemd service is stopped, keeping plaintext in process memory.
        con=sqlite3.connect(path)
        try:
            if con.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("corrupt database; refusing backup")
            data[name]=con.serialize()
        finally:
            con.close()
        _integrity(data[name])

    report={
        "schema":"SUPERVISOR_OP_BACKUP_AES256GCM_V1",
        "created_at":datetime.now(timezone.utc).isoformat(),
        "source_files":{name:{"bytes":len(blob),"sha256":sha256(blob).hexdigest()}
                        for name,blob in data.items()},
        "contains_personal_contact_data":True,
        "online_backup_used":False,
        "authorized_human_study_approval":False,
    }
    memory=io.BytesIO()
    with zipfile.ZipFile(memory,"w",compression=zipfile.ZIP_STORED,
                         allowZip64=True) as archive:
        for name,blob in data.items():
            archive.writestr(name,blob)
        archive.writestr("manifest.json",json.dumps(report,sort_keys=True))
    nonce=os.urandom(12)
    ciphertext=AESGCM(key).encrypt(nonce,memory.getvalue(),MAGIC)
    contents=MAGIC+nonce+ciphertext
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):
        flags|=os.O_NOFOLLOW
    old_umask=os.umask(0o077)
    try:
        fd=os.open(backup,flags,0o600)
        try:
            with os.fdopen(fd,"wb") as out:
                out.write(contents)
                out.flush()
                os.fsync(out.fileno())
        except BaseException:
            backup.unlink(missing_ok=True)
            raise
    finally:
        os.umask(old_umask)
    result=verify_encrypted_backup(backup,key_path)
    if result["source_files"]!=report["source_files"]:
        backup.unlink(missing_ok=True)
        raise ValueError("encrypted backup self-verification failed")
    return {"backup_created":True,"encrypted":True,"restore_test":True,
            "database_count":2,"pii_in_output":True,
            "encrypted_size":len(contents),
            "offsite_copy_verified":False}


def verify_encrypted_backup(backup: Path, key_path: Path) -> dict:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not backup.is_file() or backup.is_symlink():
        raise ValueError("encrypted backup file missing")
    key=_private_key(key_path)
    data=backup.read_bytes()
    if not data.startswith(MAGIC) or len(data)<len(MAGIC)+12+16:
        raise ValueError("invalid encrypted backup format")
    offset=len(MAGIC)
    raw=AESGCM(key).decrypt(
        data[offset:offset+12],data[offset+12:],MAGIC
    )
    with zipfile.ZipFile(io.BytesIO(raw)) as container:
        if set(container.namelist())!=set(DATA_NAMES.values())|{"manifest.json"}:
            raise ValueError("unexpected backup package members")
        meta=json.loads(container.read("manifest.json"))
        if meta.get("schema")!="SUPERVISOR_OP_BACKUP_AES256GCM_V1":
            raise ValueError("unknown backup manifest")
        names={}
        for name in DATA_NAMES.values():
            blob=container.read(name)
            _integrity(blob)
            if meta["source_files"][name]!={
                "bytes":len(blob),"sha256":sha256(blob).hexdigest()
            }:
                raise ValueError("backup file digest mismatch")
            names[name]=meta["source_files"][name]
        return {"schema":meta["schema"],"restore_integrity":"ok",
                "source_files":names,"contains_personal_contact_data":True,
                "restored_to_production":False}
