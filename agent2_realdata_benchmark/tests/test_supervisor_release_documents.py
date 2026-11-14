"""Signed document swap / audit / live consent provenance; all fictional/offline."""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import subprocess
import pytest

from src.prototype.supervisor_release_documents import (
    DocumentReleaseError, REQUIRED, new_draft, revise,
    verify, verify_current, activate,
)
from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_operational_intake import OperationalIntake
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore

COMMIT="c"*40
BANK=Path(__file__).resolve().parents[1]/"data"/"supervisor_20261111"


def _prepare(tmp_path):
    registry=tmp_path/"registry"
    registry.mkdir(mode=0o700)
    source=tmp_path/"sources"
    source.mkdir(mode=0o700)
    for i,key in enumerate(REQUIRED):
        p=source/f"{key}.pdf"
        # Unit-test fixture only: production PDF validation/review is external.
        p.write_bytes(b"%PDF-1.7\n"+(key+str(i)).encode()+b"\n%%EOF\n")
        p.chmod(0o600)
    return registry,source


def _approve_for_test(version):
    """Ephemeral TEST-only signing key, never an institutional approval."""
    manifest=version/"manifest.json"
    d=json.loads(manifest.read_text())
    d["decision"]="approved"
    d["reviewer"]="TEST SIGNER, NOT AN INSTITUTION"
    d["reviewed_at"]=datetime.now(timezone.utc).isoformat()
    for record in d["documents"].values():
        record["status"]="approved"
    manifest.write_text(json.dumps(d,sort_keys=True,indent=2))
    manifest.chmod(0o600)
    key=version.parent.parent/"test-only.key"
    public=version.parent.parent/"test-only-public.pem"
    sig=version/"manifest.sig"
    subprocess.run(["openssl","genpkey","-algorithm","RSA","-out",str(key),
                   "-pkeyopt","rsa_keygen_bits:2048"],check=True,capture_output=True)
    subprocess.run(["openssl","pkey","-in",str(key),"-pubout","-out",str(public)],
                   check=True,capture_output=True)
    subprocess.run(["openssl","dgst","-sha256","-sign",str(key),
                    "-out",str(sig),str(manifest)],check=True,capture_output=True)
    sig.chmod(0o600)
    return public


def test_placeholder_snapshot_is_pending_and_cannot_be_activated(tmp_path):
    registry,source=_prepare(tmp_path)
    version=new_draft(registry,release_commit=COMMIT,source_dir=source)
    assert version.is_dir() and version.stat().st_mode&0o077==0
    d=json.loads((version/"manifest.json").read_text())
    assert d["decision"]=="pending"
    assert set(d["documents"])==REQUIRED
    assert all(x["status"]=="pending" for x in d["documents"].values())
    with pytest.raises(DocumentReleaseError,match="signature"):
        verify(version,release_commit=COMMIT,
               signature=version/"manifest.sig",
               institutional_public_key=registry/"nonexistent.pem")
    assert not (registry/"current").exists()
    assert not list(version.glob("*.sig"))


def test_signed_document_refresh_preserves_previous_revision_and_blocks_tampering(tmp_path):
    registry,source=_prepare(tmp_path)
    v1=new_draft(registry,release_commit=COMMIT,source_dir=source)
    pub=_approve_for_test(v1)
    signed=verify(v1,release_commit=COMMIT,
                  signature=v1/"manifest.sig",institutional_public_key=pub)
    assert signed.digest("privacy_participant_en")==sha256(
        (v1/"files/privacy_participant_en.pdf").read_bytes()).hexdigest()
    with pytest.raises(DocumentReleaseError,match="independent core"):
        activate(registry_root=registry,version=v1,release_commit=COMMIT,
                 public_key=pub,institutional_release_check=lambda _: False)
    assert not (registry/"current").exists()
    active=activate(registry_root=registry,version=v1,release_commit=COMMIT,
                    public_key=pub,institutional_release_check=lambda _: True)
    assert active.bundle_id==v1.name
    assert verify_current(registry_root=registry,release_commit=COMMIT,
                          public_key=pub).bundle_id==v1.name
    with sqlite3.connect(":memory:") as db:
        assert len(list((registry/"versions").iterdir()))==1
    newsource=tmp_path/"changes"
    newsource.mkdir(mode=0o700)
    modified=newsource/"privacy_participant_en.pdf"
    modified.write_bytes(b"%PDF-1.7\nUpdated real document byte fixture\n%%EOF\n")
    modified.chmod(0o600)
    v2=revise(registry,release_commit=COMMIT,source_dir=newsource)
    new=json.loads((v2/"manifest.json").read_text())
    assert new["decision"]=="pending" and new["supersedes"]==v1.name
    assert new["documents"]["privacy_participant_en"]["sha256"]!=signed.digest("privacy_participant_en")
    assert verify_current(registry_root=registry,release_commit=COMMIT,
                          public_key=pub).bundle_id==v1.name
    assert (v1/"files/privacy_participant_en.pdf").read_bytes().startswith(b"%PDF-")
    # Tamper with the signed v1 bytes: all subsequent checks block.
    (v1/"files/privacy_participant_en.pdf").write_bytes(b"%PDF-1.7\nTAMPERED\n%%EOF\n")
    with pytest.raises(DocumentReleaseError,match="bytes changed"):
        verify_current(registry_root=registry,release_commit=COMMIT,
                       public_key=pub)


def test_operational_consent_records_signed_document_hash_and_deletes_on_erasure(tmp_path):
    private=tmp_path/"state"
    private.mkdir(mode=0o700)
    store=SupervisorSyntheticStore(private,bank=SupervisorBank(BANK),operational=True)
    class ApprovedBundleFixture:
        manifest_sha256="f"*64
        bundle_id="test-only-approved-bundle"
        def digest(self,key):
            assert key in REQUIRED
            return "e"*64
    intake=OperationalIntake(store,programs=("Fictional approved study",),
                             document_bundle=ApprovedBundleFixture())
    now=datetime.now(timezone.utc)
    token=intake.issue("test-doc-consent@example.example",at=now,allow_example=True)
    intake.consent(token,checks=[True]*5,optional=False,language="en",at=now)
    answers={q.question_id:(q.correct_answer if i<4 else
             next(x for x in "ABCD" if x!=q.correct_answer))
             for i,q in enumerate(store.bank.forms["screening"])}
    assert intake.screening(token,answers=answers,at=now)["eligible"]
    intake.register(token,age=24,program="Fictional approved study",at=now)
    with store._tx() as db:
        found=db.execute(
            "SELECT learner_id,bundle_sha256,information_sha256,document_version "
            "FROM pii.consent_document_history"
        ).fetchone()
        assert found is not None and found["bundle_sha256"]=="f"*64
        assert found["information_sha256"]=="e"*64
        assert found["document_version"]=="test-only-approved-bundle"
        learner=found["learner_id"]
    result=store.withdraw(learner,token,delete=True,at=now)
    assert result["data_deleted"] is True
    with store._tx() as db:
        assert db.execute("SELECT COUNT(*) FROM pii.consent_document_history").fetchone()[0]==0


def test_signed_release_document_bundle_rejects_wrong_commit_and_symlink(tmp_path):
    registry,source=_prepare(tmp_path)
    candidate=new_draft(registry,release_commit=COMMIT,source_dir=source)
    pub=_approve_for_test(candidate)
    with pytest.raises(DocumentReleaseError,match="exact source"):
        verify(candidate,release_commit="d"*40,
               signature=candidate/"manifest.sig",
               institutional_public_key=pub)
    file=candidate/"files/privacy_participant_en.pdf"
    original=file.read_bytes()
    file.unlink()
    file.symlink_to(source/"privacy_participant_en.pdf")
    with pytest.raises(DocumentReleaseError,match="symlink"):
        verify(candidate,release_commit=COMMIT,
               signature=candidate/"manifest.sig",
               institutional_public_key=pub)
