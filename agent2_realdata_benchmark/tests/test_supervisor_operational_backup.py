"""Encrypted paired research/PII backups, offline only; all data fictional."""
from __future__ import annotations
from pathlib import Path
import os
import sqlite3
import stat
from types import SimpleNamespace

import pytest

from src.prototype.supervisor_operational_backup import (
    MAGIC,snapshot_pair,verify_encrypted_backup,
)

pytest.importorskip("cryptography")


def fixture(tmp_path):
    root=tmp_path/"research_state"
    target=tmp_path/"backups"
    root.mkdir(mode=0o700)
    target.mkdir(mode=0o700)
    for name in (
        "supervisor_operational_study.sqlite3",
        "supervisor_operational_contacts.sqlite3",
    ):
        path=root/name
        db=sqlite3.connect(path)
        db.execute("CREATE TABLE synthetic_only(key TEXT,value TEXT)")
        db.execute("INSERT INTO synthetic_only VALUES(?,?)",("fixture","fake"))
        db.commit();db.close()
        path.chmod(0o600)
    key=tmp_path/"admin_backup_key"
    key.write_bytes(os.urandom(32))
    key.chmod(0o600)
    return root,target,key


def test_encrypted_pair_and_memory_only_restore(tmp_path,monkeypatch):
    root,target,key=fixture(tmp_path)
    from src.prototype import supervisor_operational_backup as backup
    monkeypatch.setattr(backup,"_assert_service_quiesced",lambda:None)
    output=target/"first.encrypted"
    result=snapshot_pair(root,output,key)
    assert result["encrypted"] and result["restore_test"]
    assert result["database_count"]==2
    assert result["offsite_copy_verified"] is False
    assert stat.S_IMODE(output.stat().st_mode)==0o600
    assert output.read_bytes().startswith(MAGIC)
    assert b"SQLite format 3\0" not in output.read_bytes()
    verify=verify_encrypted_backup(output,key)
    assert verify["restore_integrity"]=="ok"
    assert len(verify["source_files"])==2
    assert verify["restored_to_production"] is False
    # A second run does not overwrite a prior encrypted archive.
    with pytest.raises(ValueError,match="new absolute"):
        snapshot_pair(root,output,key)


def test_rejects_authenticated_ciphertext_tampering_and_wrong_key(tmp_path,monkeypatch):
    root,target,key=fixture(tmp_path)
    from src.prototype import supervisor_operational_backup as backup
    monkeypatch.setattr(backup,"_assert_service_quiesced",lambda:None)
    output=target/"first.encrypted"
    snapshot_pair(root,output,key)
    alternate=target/"different.key"
    alternate.write_bytes(os.urandom(32));alternate.chmod(0o600)
    with pytest.raises(Exception):
        verify_encrypted_backup(output,alternate)
    blob=bytearray(output.read_bytes());blob[-3]^=1
    output.write_bytes(blob)
    with pytest.raises(Exception):
        verify_encrypted_backup(output,key)


def test_refuse_open_database_service_and_bad_permissions(tmp_path,monkeypatch):
    root,target,key=fixture(tmp_path)
    from src.prototype import supervisor_operational_backup as backup
    monkeypatch.setattr(backup.subprocess,"run",
        lambda *a,**k:SimpleNamespace(returncode=0))
    with pytest.raises(ValueError,match="stop the study service"):
        snapshot_pair(root,target/"opened.enc",key)
    assert not (target/"opened.enc").exists()
    monkeypatch.setattr(backup,"_assert_service_quiesced",lambda:None)
    key.chmod(0o644)
    with pytest.raises(ValueError,match="key file"):
        snapshot_pair(root,target/"world-readable.enc",key)
    key.chmod(0o600)
    target.chmod(0o755)
    with pytest.raises(ValueError,match="private folder"):
        snapshot_pair(root,target/"unprotected.enc",key)


def test_missing_or_malformed_research_state_never_generates_backup(tmp_path,monkeypatch):
    root,target,key=fixture(tmp_path)
    from src.prototype import supervisor_operational_backup as backup
    monkeypatch.setattr(backup,"_assert_service_quiesced",lambda:None)
    (root/"supervisor_operational_contacts.sqlite3").unlink()
    with pytest.raises(ValueError,match="expected operational"):
        snapshot_pair(root,target/"missing.enc",key)
    assert not (target/"missing.enc").exists()
