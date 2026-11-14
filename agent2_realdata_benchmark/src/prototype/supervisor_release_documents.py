"""Versioned private, institution-signed study document bundles.

A new document is an immutable new revision, never an overwrite. A refreshed
candidate is ALWAYS PENDING, even when copied from an approved predecessor.
Real activation requires both this signature and the pre-existing independent
14-category + PI instructional-content release gate. No signing keys are
generated or held by this software.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import uuid

SCHEMA = "IJCAI2027_SIGNED_STUDY_DOCUMENTS_V1"
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[A-Za-z0-9_-]{8,72}\Z")

# PDFs are external versioned legal/supporting study documents. Executable
# assessment bank, adaptive policy and consent checkbox text still require
# their separately approved exact-source content hash / release signature.
REQUIRED = {
    "participant_information_school_en",
    "participant_information_school_fr",
    "participant_information_external_en",
    "participant_information_external_fr",
    "consent_record_school_en",
    "consent_record_school_fr",
    "consent_record_external_en",
    "consent_record_external_fr",
    "privacy_participant_en",
    "privacy_participant_fr",
    "recruitment_privacy_en",
    "recruitment_privacy_fr",
    "instructional_review_en",
    "instructional_review_fr",
    "fatigue_instrument_en",
    "fatigue_instrument_fr",
}


class DocumentReleaseError(RuntimeError):
    pass


def _folder(path: Path, *, permissions: bool = True):
    if not path.is_absolute() or not path.is_dir() or path.is_symlink():
        raise DocumentReleaseError("absolute nonsymlink private directory required")
    if permissions and path.stat().st_mode & 0o077:
        raise DocumentReleaseError("private document directory must be mode 0700")
    return path


def _verified_file(path: Path, root: Path):
    if (not path.is_file() or path.is_symlink()
            or not path.resolve().is_relative_to(root.resolve())):
        raise DocumentReleaseError("missing/symlinked or escaped document")
    if path.stat().st_mode & 0o007:
        raise DocumentReleaseError("document must not be world-accessible")
    return path


def _write_new(path: Path, content: bytes):
    fd = os.open(path, os.O_CREAT|os.O_WRONLY|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _dump(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2,
                       ensure_ascii=False) + "\n").encode("utf-8")


def _stamp():
    return datetime.now(timezone.utc).isoformat()


def _candidate(root: Path, *, release_commit: str, sources: Path,
               previous: Path | None = None) -> Path:
    if not COMMIT.fullmatch(release_commit):
        raise DocumentReleaseError("full exact source commit required")
    _folder(root)
    if not sources.is_absolute() or not sources.is_dir() or sources.is_symlink():
        raise DocumentReleaseError("existing source document folder required")
    version_root = root / "versions"
    version_root.mkdir(mode=0o700, exist_ok=True)
    _folder(version_root)
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
    directory = version_root / identifier
    directory.mkdir(mode=0o700)
    (directory / "files").mkdir(mode=0o700)
    old = json.loads((previous/"manifest.json").read_text()) if previous else None
    records={}
    for key in sorted(REQUIRED):
        target=directory/"files"/f"{key}.pdf"
        candidate=sources/f"{key}.pdf"
        # For a new revision, inherit untouched previous documents by copy.
        if not candidate.exists() and previous:
            candidate=previous/"files"/f"{key}.pdf"
        if candidate.exists():
            _verified_file(candidate, candidate.parent)
            data = candidate.read_bytes()
            if not data.startswith(b"%PDF-") or len(data)>15_000_000:
                raise DocumentReleaseError("final document must be valid-sized PDF")
            _write_new(target,data)
            digest=sha256(data).hexdigest()
        else:
            digest=None
        records[key]=dict(path=f"files/{key}.pdf",sha256=digest,
                          status="pending",version=identifier)
    manifest = dict(schema=SCHEMA,decision="pending",release_commit=release_commit,
                    bundle_id=identifier,created_at=_stamp(),
                    supersedes=old["bundle_id"] if old else None,
                    reviewer=None,reviewed_at=None,
                    documents=records)
    _write_new(directory/"manifest.json",_dump(manifest))
    _write_new(directory/"REVIEW_REQUIRED.txt",
               b"DRAFT - no release authorization. Do not self-sign, enable mail or enroll humans.\n"
               b"Approval requires independent document review, signed manifest, and exact release gates.\n")
    return directory


def new_draft(root: str | Path, *, release_commit: str, source_dir: str | Path):
    return _candidate(Path(root),release_commit=release_commit,
                      sources=Path(source_dir))


def revise(root: str | Path, *, release_commit: str, source_dir: str | Path):
    registry=_folder(Path(root))
    prior=current_version(registry)
    if prior is None:
        # A genuine approval is expected to arrive AFTER several draft
        # iterations. Select the most recent private candidate without
        # activating it or retroactively marking any draft approved.
        versions=registry/"versions"
        if versions.is_dir() and not versions.is_symlink():
            candidates=sorted(
                (p for p in versions.iterdir()
                 if p.is_dir() and not p.is_symlink() and
                 (p/"manifest.json").is_file()),
                key=lambda p:p.name)
            prior=candidates[-1] if candidates else None
        if prior is None:
            raise DocumentReleaseError("no previous draft version to revise")
    prior=_folder(prior)
    # Existing historical revisions are never overwritten or mutated.
    return _candidate(registry,release_commit=release_commit,
                      sources=Path(source_dir),previous=prior)


@dataclass(frozen=True)
class SignedDocumentBundle:
    version_dir: Path
    manifest_sha256: str
    bundle_id: str
    release_commit: str
    documents: dict

    def file(self, key: str) -> Path:
        if key not in self.documents:
            raise DocumentReleaseError("document not included in signed bundle")
        return self.version_dir / self.documents[key]["path"]

    def digest(self, key: str) -> str:
        return self.documents[key]["sha256"]


def _verify_signature(index: Path, signature: Path, key: Path):
    for p in (signature,key):
        if not p.is_absolute() or not p.is_file() or p.is_symlink():
            raise DocumentReleaseError("independently provided signature/key required")
    result=subprocess.run(
        ["openssl","dgst","-sha256","-verify",str(key),
         "-signature",str(signature),str(index)],
        capture_output=True,text=True,timeout=15,check=False)
    if result.returncode != 0 or "Verified OK" not in result.stdout:
        raise DocumentReleaseError("document bundle institutional signature invalid")


def verify(version: str | Path, *, release_commit: str,
           signature: str | Path, institutional_public_key: str | Path):
    folder=_folder(Path(version))
    manifest_file=_verified_file(folder/"manifest.json",folder)
    data=manifest_file.read_bytes()
    _verify_signature(manifest_file,Path(signature),Path(institutional_public_key))
    try:
        record=json.loads(data)
    except ValueError:
        raise DocumentReleaseError("invalid signed document manifest") from None
    if (record.get("schema")!=SCHEMA or record.get("decision")!="approved"
            or record.get("release_commit")!=release_commit
            or not COMMIT.fullmatch(release_commit)
            or not isinstance(record.get("reviewer"),str)
            or len(record["reviewer"].strip())<3
            or not ID.fullmatch(record.get("bundle_id",""))
            or record["bundle_id"]!=folder.name):
        raise DocumentReleaseError("bundle not approved for this exact source")
    try:
        at=datetime.fromisoformat(record["reviewed_at"])
        if at.utcoffset() is None:
            raise ValueError("timezone required")
    except (KeyError,ValueError,TypeError,AttributeError):
        raise DocumentReleaseError("timezone-aware institutional review time required") from None
    if (not isinstance(record.get("documents"),dict)
            or set(record["documents"])!=REQUIRED):
        raise DocumentReleaseError("incomplete/replaced document set")
    for key, entry in record["documents"].items():
        if (not isinstance(entry,dict) or entry.get("status")!="approved"
                or entry.get("version")!=folder.name
                or entry.get("path")!=f"files/{key}.pdf"
                or not isinstance(entry.get("sha256"),str)
                or not SHA.fullmatch(entry["sha256"])):
            raise DocumentReleaseError("document record is incomplete or stale")
        p=_verified_file(folder/entry["path"],folder)
        with p.open("rb") as file:
            first=file.read(5)
            h=sha256(first)
            for block in iter(lambda:file.read(1024*1024),b""):
                h.update(block)
        if first!=b"%PDF-" or h.hexdigest()!=entry["sha256"]:
            raise DocumentReleaseError("signed document bytes changed")
    return SignedDocumentBundle(folder,sha256(data).hexdigest(),
                                folder.name,release_commit,record["documents"])


def current_version(root: Path) -> Path | None:
    _folder(root)
    current=root/"current"
    if not current.is_symlink():
        if current.exists():
            raise DocumentReleaseError("active document pointer is not symlink")
        return None
    target=current.resolve(strict=True)
    versions=root/"versions"
    if not target.is_relative_to(versions.resolve()) or target.parent!=versions.resolve():
        raise DocumentReleaseError("active document revision escaped registry")
    return _folder(target)


def verify_current(*, registry_root: str | Path, release_commit: str,
                   public_key: str | Path):
    root=_folder(Path(registry_root))
    version=current_version(root)
    if version is None:
        raise DocumentReleaseError("no institutionally activated document bundle")
    return verify(version,release_commit=release_commit,
                  signature=version/"manifest.sig",
                  institutional_public_key=public_key)


def activate(*, registry_root: str | Path, version: str | Path,
             release_commit: str, public_key: str | Path,
             institutional_release_check):
    """Atomic revision pointer switch AFTER authentic independent release check.

    An operator callback must check the pre-existing 14/14 signed release and
    PI content approvals. An arbitrary callback must not be used in LIVE ops.
    """
    root=_folder(Path(registry_root))
    version=_folder(Path(version))
    if version.parent.resolve() != (root/"versions").resolve():
        raise DocumentReleaseError("new bundle must belong to registry")
    candidate=verify(version,release_commit=release_commit,
                     signature=version/"manifest.sig",
                     institutional_public_key=public_key)
    if institutional_release_check(release_commit) is not True:
        raise DocumentReleaseError("independent core study release not verified")
    lock=root/".activation.lock"
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        prior=current_version(root)
        next_link=root/(".next-"+uuid.uuid4().hex)
        os.symlink(str(Path("versions")/version.name),next_link)
        os.replace(next_link,root/"current")
        audit=root/"activation_audit.jsonl"
        record=dict(at=_stamp(),bundle=candidate.bundle_id,
                    sha256=candidate.manifest_sha256,release_commit=release_commit,
                    previous=prior.name if prior else None,
                    institutional_release_verified=True)
        flags=os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW
        descriptor=os.open(audit,flags,0o600)
        with os.fdopen(descriptor,"ab") as log:
            log.write(_dump(record).rstrip(b"\n")+b"\n")
            log.flush()
            os.fsync(log.fileno())
        return candidate
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)
