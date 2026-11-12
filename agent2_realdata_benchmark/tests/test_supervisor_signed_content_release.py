"""Signed PI approval of exact content, never an editable config toggle."""
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import pytest

from src.prototype.supervisor_content_approval import (
    FILES,verify_signed_content_approval,
)
from src.prototype.supervisor_recovery_content import CONTENT_VERSION
from src.prototype.supervisor_consent_texts import (
    CONSENT_VERSION,NONREWARD_CONSENT_VERSION,
)

COMMIT="a"*40


def signing_keys(tmp_path):
    if not shutil.which("openssl"):
        pytest.skip("OpenSSL not installed")
    secret=tmp_path/"test_only_signing_key.pem"
    public=tmp_path/"test_only_public.pem"
    subprocess.run(["openssl","genpkey","-algorithm","RSA",
                    "-pkeyopt","rsa_keygen_bits:2048",
                    "-out",str(secret)],
                   check=True,capture_output=True)
    subprocess.run(["openssl","pkey","-in",str(secret),"-pubout",
                    "-out",str(public)],check=True,capture_output=True)
    return secret,public


def sign(secret,manifest,signature):
    subprocess.run(["openssl","dgst","-sha256","-sign",str(secret),
                    "-out",str(signature),str(manifest)],
                   check=True,capture_output=True)


def prepared(tmp_path):
    root=tmp_path/"source"
    root.mkdir()
    digests={}
    for name in FILES:
        f=root/name
        f.parent.mkdir(exist_ok=True,parents=True)
        f.write_text("RESEARCH TEST FIXTURE — "+name+"\n",encoding="utf-8")
        digests[name]=sha256(f.read_bytes()).hexdigest()
    manifest=tmp_path/"approved_content.json"
    payload={
        "schema":"SUPERVISOR_APPROVED_CONTENT_V1",
        "candidate_commit":COMMIT,
        "decision":"approved",
        "content_version":CONTENT_VERSION,
        "consent_versions":[CONSENT_VERSION,NONREWARD_CONSENT_VERSION],
        "reviewer":"Synthetic PI, Unit Test Only",
        "role":"principal_investigator",
        "approved_at":datetime.now(timezone.utc).isoformat(),
        "files_sha256":digests,
    }
    manifest.write_text(json.dumps(payload,sort_keys=True),encoding="utf-8")
    secret,public=signing_keys(tmp_path)
    signature=tmp_path/"approved_content.sig"
    sign(secret,manifest,signature)
    return root,manifest,signature,secret,public,payload


def test_signed_approval_binds_all_14_files_and_specific_commit(tmp_path):
    root,manifest,signature,_,public,payload=prepared(tmp_path)
    result=verify_signed_content_approval(root,manifest,signature,public,COMMIT)
    assert result["content_approved"] is True
    assert result["files_verified"]==len(FILES)
    assert result["institutional_signature_verified"] is True
    assert result["real_study_release_authorized_by_this_check"] is False
    with pytest.raises(ValueError,match="bind"):
        verify_signed_content_approval(root,manifest,signature,public,"b"*40)


def test_signed_content_rejects_tampering_and_removed_files(tmp_path):
    root,manifest,signature,secret,public,payload=prepared(tmp_path)
    f=root/FILES[0]
    f.write_text("altered without PI review")
    with pytest.raises(ValueError,match="differs"):
        verify_signed_content_approval(root,manifest,signature,public,COMMIT)
    f.write_text("RESEARCH TEST FIXTURE — "+FILES[0]+"\n")
    f.unlink()
    with pytest.raises(ValueError,match="missing"):
        verify_signed_content_approval(root,manifest,signature,public,COMMIT)


def test_mutated_review_and_different_key_are_not_approvals(tmp_path):
    root,manifest,signature,secret,public,payload=prepared(tmp_path)
    payload["decision"]="pending"
    manifest.write_text(json.dumps(payload),encoding="utf-8")
    with pytest.raises(ValueError,match="signature"):
        verify_signed_content_approval(root,manifest,signature,public,COMMIT)
    sign(secret,manifest,signature)
    with pytest.raises(ValueError,match="bind"):
        verify_signed_content_approval(root,manifest,signature,public,COMMIT)


def test_real_staging_remains_disabled_without_evidence(monkeypatch):
    from scripts.supervisor_vps_wsgi import _release_verified
    monkeypatch.delenv("SUPERVISOR_RELEASE_EVIDENCE",raising=False)
    monkeypatch.delenv("SUPERVISOR_CONTENT_APPROVAL",raising=False)
    with pytest.raises(RuntimeError,match="institutional evidence"):
        _release_verified(COMMIT)


def test_even_a_valid_signature_cannot_approve_an_unfilled_annex(tmp_path):
    root,manifest,signature,secret,public,payload=prepared(tmp_path)
    name="content/consent/info_sheet_en_v1.0.html"
    file=root/name
    file.write_text("The contact is [email].",encoding="utf-8")
    payload["files_sha256"][name]=sha256(file.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(payload,sort_keys=True),encoding="utf-8")
    sign(secret,manifest,signature)
    with pytest.raises(ValueError,match="unfilled placeholders"):
        verify_signed_content_approval(root,manifest,signature,public,COMMIT)
