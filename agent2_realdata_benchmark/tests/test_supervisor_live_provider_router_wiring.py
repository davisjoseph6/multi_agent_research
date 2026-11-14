"""Source regression for the signed LIVE recruitment startup path.

The isolated PREPARE test installs units but does not import the LIVE WSGI
with real signed evidence; this test guards against mutually exclusive
transport checks that would make approved activation impossible.

No network, mailbox, private credentials, or participant data are used.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WSGI = ROOT / "scripts/supervisor_recruitment_wsgi.py"


def test_live_wsgi_uses_single_provider_neutral_transport_gate():
    source = WSGI.read_text(encoding="utf-8")
    assert 'os.environ.get("SUPERVISOR_MAIL_TRANSPORT") != "provider_router"' in source
    assert 'os.environ.get("SUPERVISOR_MAIL_TRANSPORT")!="microsoft_graph"' not in source
    assert "build_mail_router(" in source
    assert "approval_signature=os.environ[\"SUPERVISOR_MAIL_APPROVAL_SIGNATURE\"]" in source
    assert "institution_key=os.environ[\"SUPERVISOR_INSTITUTION_PUBLIC_KEY\"]" in source
    assert "release_commit=commit" in source


def test_live_notices_come_from_signed_bilingual_document_bundle():
    source = WSGI.read_text(encoding="utf-8")
    assert "verify_current(" in source
    assert 'bundle.file(f"recruitment_privacy_{language}")' in source
    assert 'for language in ("en","fr")' in source
    # A legacy marker is not an independent signature or approved PDF.
    assert "SUPERVISOR_APPROVED_RECRUITMENT_NOTICE" not in source


def test_live_release_and_public_intake_still_fail_closed():
    source = WSGI.read_text(encoding="utf-8")
    assert "if not _release_verified(commit):" in source
    assert "if dirty:" in source
    assert "live_verified=mode==\"live\"" in source
    assert "public_intake_enabled=mode==\"live\" and not control_only" in source
    assert "privacy_notices=None if control_only else privacy_notices" in source
    assert 'if control_only and mode!="live":' in source
