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


def test_researcher_portal_does_not_assume_every_sender_is_outlook():
    static = ROOT / "src/prototype/static/supervisor_recruitment_admin.js"
    ui = static.read_text(encoding="utf-8")
    assert "accepted by the email provider" in ui
    assert "authorized email provider" in ui
    assert "Outlook" not in ui
    service = (ROOT / "src/prototype/supervisor_recruitment_web.py").read_text(encoding="utf-8")
    assert "signed live invitation sending is not configured" in service
    assert "signed live reminder sender is not configured" in service


def test_pending_upgrade_preserves_state_and_requires_disabled_services():
    import subprocess
    script = ROOT / "ops/supervisor/upgrade_pending_live_release.sh"
    assert subprocess.run(["bash", "-n", str(script)], check=False).returncode == 0
    body = script.read_text(encoding="utf-8")
    assert "flock -n 9" in body
    assert "systemctl is-active --quiet" in body
    assert "systemctl is-enabled --quiet" in body
    assert '! -e "$STATE/document_registry/current"' in body
    assert '! -e "$PRIVATE/live.env"' in body
    assert '! -e /etc/caddy/ijcai-supervisor-live.caddy' in body
    assert 'materialize_live_bundle.sh' in body
    assert 'git -C "$PREFIX/releases/$OLD" status --porcelain' in body
    assert "scripts.supervisor_doc_bundle_cli" in body
    assert 'mv -Tf -- "$TEMP" "$PREFIX/current"' in body
    assert "systemctl enable" not in body
    assert "systemctl start" not in body
    assert "systemctl reload" not in body
    assert "rm -rf" not in body
    assert "install_live_services.sh activate" not in body
