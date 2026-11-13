"""Regression for 2026-11-12 VPS systemd status=200/CHDIR.

The upload is deliberately private (0700). GNU cp -a SOURCE/. DEST/
preserves SOURCE's directory mode on DEST, so installing into an initially
0755 release directory silently changes it to 0700 and blocks the separate
systemd service account. The fix must run for both new and existing releases.
"""
from pathlib import Path
import os
import stat
import subprocess

INSTALLER = Path(__file__).resolve().parents[1] / "ops/supervisor/install_staging.sh"


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_cpa_private_upload_regression_reproduced_and_normalized(tmp_path):
    source = tmp_path / "private_upload"
    release = tmp_path / "srv" / "releases" / "fake-commit"
    (source / "agent2_realdata_benchmark" / "scripts").mkdir(parents=True)
    (source / "agent2_realdata_benchmark" / "scripts"
            / "supervisor_vps_wsgi.py").write_text("app = None\n", encoding="utf-8")
    release.mkdir(parents=True, mode=0o755)
    source.chmod(0o700)
    assert mode(source) == 0o700
    assert mode(release) == 0o755

    subprocess.run(["cp", "-a", str(source) + "/.", str(release) + "/"],
                   check=True)
    subprocess.run(["chmod", "-R", "go-w", str(release)], check=True)
    assert mode(release) == 0o700  # Original installer fault.

    subprocess.run(["chmod", "0755", str(release)], check=True)
    assert mode(release) == 0o755
    assert mode(source) == 0o700  # Protected SSH upload stays private.
    assert (release / "agent2_realdata_benchmark" / "scripts"
            / "supervisor_vps_wsgi.py").is_file()


def test_installer_fixes_preexisting_release_before_systemd_restart():
    text = INSTALLER.read_text(encoding="utf-8")
    copy = text.index('cp -a "$SOURCE/." "$RELEASE/"')
    normalization = text.index('\nchmod 0755 "$RELEASE"\n')
    preflight = text.index('runuser -u ijcai-supervisor -- test -x')
    link = text.index('ln -s "${PREFIX}/releases/${SHA}" "${PREFIX}/.next-current.$"')
    swap = text.index('mv -Tf "${PREFIX}/.next-current.$" "${PREFIX}/current"')
    restart = text.index('systemctl restart "${SERVICE}"')
    assert copy < normalization < preflight < link < swap < restart
    assert "trap rollback EXIT" in text
    assert "SUPERVISOR_VPS_MODE" in text
    assert "Expected an exact pre-existing STAGING environment value" in text
    assert 'cp -a "$ROLLBACK_DIR/staging.env" "$ENV_FILE"' in text
    assert 'cp -a "$ROLLBACK_DIR/Caddyfile" "$CADDY"' in text
    assert "CHANGED=0" in text
    # The normalization is outside the new-release branch, and therefore
    # applies if an existing release was previously installed incorrectly.
    assert text.index('\nfi\n\n# cp -a') < normalization
    assert 'systemctl enable --now' not in text.split("systemctl daemon-reload",1)[1]
    assert 'chmod -R 777' not in text
    assert 'chmod 0777' not in text


def test_systemd_service_remains_immutable_and_state_private():
    text = INSTALLER.read_text(encoding="utf-8")
    assert 'User=ijcai-supervisor' in text
    assert 'Group=ijcai-supervisor' in text
    assert 'WorkingDirectory=${PREFIX}/current/agent2_realdata_benchmark' in text
    assert 'UMask=0077' in text
    assert 'ProtectSystem=strict' in text
    assert 'ReadWritePaths=${STATE}' in text
    assert 'StateDirectoryMode=0700' in text
    assert '127.0.0.1:8788' in text and '--bind 0.0.0.0' not in text
