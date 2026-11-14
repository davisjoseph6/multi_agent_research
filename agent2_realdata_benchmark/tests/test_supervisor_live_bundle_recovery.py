"""Offline regression for the VPS failed checkout; no network, sudo or VPS access."""
from __future__ import annotations

import subprocess
from pathlib import Path
import pytest

HELPER = Path(__file__).resolve().parents[1] / "ops/supervisor/materialize_live_bundle.sh"
INSTALLER = HELPER.parent / "install_live_services.sh"
REF = "refs/remotes/origin/research/ijcai2027-supervisor-consent-gdpr-20261112"


def git(*args, directory: Path):
    return subprocess.run(["git", "-C", str(directory), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def fixture(tmp_path):
    source = tmp_path / "origin"
    source.mkdir()
    git("init", "-q", directory=source)
    git("config", "user.name", "Test Fixture", directory=source)
    git("config", "user.email", "fixture@example.test", directory=source)
    (source / "README").write_text("TEST ONLY\n")
    git("add", "README", directory=source)
    git("commit", "-qm", "test only", directory=source)
    sha = git("rev-parse", "HEAD", directory=source)
    git("update-ref", REF, sha, directory=source)
    bundle = tmp_path / "release.bundle"
    git("bundle", "create", str(bundle), REF, directory=source)
    return bundle, sha


def materialize(bundle, sha, destination, ref=REF):
    return subprocess.run(["bash", str(HELPER), str(bundle), sha,
                           str(destination), ref],
                          capture_output=True, text=True, check=False)


def test_remote_tracking_only_bundle_recovers_aborted_git_clone(tmp_path):
    bundle, sha = fixture(tmp_path)
    checkout = tmp_path / "checkout"
    # Reproduce the exact user's failure: clone warns 'empty repository'.
    clone = subprocess.run(["git", "clone", "-q", str(bundle), str(checkout)],
                           text=True, capture_output=True, check=False)
    assert clone.returncode == 0
    assert "empty repository" in clone.stderr.lower()
    assert subprocess.run(["git", "-C", str(checkout), "rev-parse",
                           "--verify", "HEAD"], capture_output=True).returncode != 0
    recovery = materialize(bundle, sha, checkout)
    assert recovery.returncode == 0, recovery.stderr
    assert git("rev-parse", "HEAD", directory=checkout) == sha
    assert (checkout / "README").read_text() == "TEST ONLY\n"
    # Idempotency is refusal, never reset a completed release.
    again = materialize(bundle, sha, checkout)
    assert again.returncode != 0
    assert git("rev-parse", "HEAD", directory=checkout) == sha


def test_bundle_materializer_rejects_wrong_sha_and_user_data(tmp_path):
    bundle, sha = fixture(tmp_path)
    checkout = tmp_path / "checkout"
    bad = materialize(bundle, "f"*40, checkout)
    assert bad.returncode != 0
    assert not checkout.exists()
    checkout.mkdir()
    git("init", "-q", directory=checkout)
    private = checkout / "DO_NOT_DELETE_PARTICIPANTS.sqlite3"
    private.write_text("existing private data sentinel")
    denied = materialize(bundle, sha, checkout)
    assert denied.returncode != 0
    assert private.read_text() == "existing private data sentinel"
    assert git("status", "--porcelain", directory=checkout).startswith("??")


def test_installer_uses_bundle_helper_not_plain_clone():
    source = INSTALLER.read_text()
    assert "materialize_live_bundle.sh" in source
    assert "git clone --quiet --no-local" not in source
    for script in (INSTALLER, HELPER):
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True)
        assert result.returncode == 0
