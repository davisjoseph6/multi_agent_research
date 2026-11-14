"""Static fail-closed checks for deployment templates; never call VPS."""
from pathlib import Path
import json
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/"ops/supervisor"

def test_live_scripts_parse_and_prepare_does_not_send():
    for path in ("install_live_services.sh", "install_live_reminder_timer.sh"):
        subprocess.run(["bash","-n",str(OPS/path)],check=True)
    script=(OPS/"install_live_services.sh").read_text()
    assert "MODE" in script and "prepare" in script and "activate" in script
    assert "/srv/ijcai-supervisor-live" in script
    assert "/var/lib/ijcai-supervisor-live" in script
    assert "127.0.0.1:8888" in script and "127.0.0.1:8889" in script
    assert "127.0.0.1:8890" in script
    assert "SUPERVISOR_RECRUITMENT_CONTROL_ONLY" in script
    assert '8890/control/api/overview' in script
    assert '8890/interest/school' in script
    assert "scripts.supervisor_live_readiness" in script
    assert "SUPERVISOR_VPS_MODE" in script
    assert "caddy validate" in script and "systemctl reload caddy" in script
    assert "rollback()" in script and "systemctl stop" in script
    assert "install_live_reminder_timer.sh" in script
    assert "ijcai-supervisor-staging.service" not in script
    assert "8077" not in script

def test_draft_email_templates_have_no_live_valid_sender_authorization():
    routes=json.loads((OPS/"templates/mail_routes.DRAFT.json").read_text())
    policy=json.loads((OPS/"templates/mail_owner_authorizations.DRAFT.json").read_text())
    assert routes["default"]=="not-configured"
    assert policy["decision"]=="pending"
    assert not any(x["owner_authorized"] for x in policy["senders"].values())
    assert not any(x["institutional_scope_verified"] for x in policy["senders"].values())
    env=(OPS/"templates/live.env.DRAFT").read_text()
    assert "SUPERVISOR_VPS_MODE=staging" in env
    assert "SUPERVISOR_MAIL_TRANSPORT=disabled" in env

def test_exact_research_admin_identity_allowlist_unchanged():
    from src.prototype.supervisor_recruitment import ADMIN_EMAILS
    assert ADMIN_EMAILS == {
        "wiam.belouard@aivancity.education":"researcher",
        "sara.elkardi@aivancity.education":"researcher",
        "davis.joseph@aivancity.education":"researcher",
        "yaacoub@aivancity.ai":"supervisor",
    }

def test_wsgis_and_reminder_use_shared_mail_routes_and_signed_doc_registry():
    for name in ("supervisor_recruitment_wsgi.py","supervisor_vps_daily.py"):
        s=(ROOT/"scripts"/name).read_text()
        assert "build_mail_router" in s
        assert "SUPERVISOR_MAIL_APPROVAL_SIGNATURE" in s
    assert "verify_current" in (ROOT/"scripts/supervisor_vps_wsgi.py").read_text()
    assert "verify_current" in (ROOT/"scripts/supervisor_recruitment_wsgi.py").read_text()
    assert "DocumentReleaseError" in (ROOT/"src/prototype/supervisor_release_documents.py").read_text()
