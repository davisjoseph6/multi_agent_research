"""Ensure the operational backup wrapper is safe and syntactically valid."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops" / "supervisor" / "run_safe_encrypted_backup.sh"


def test_wrapper_never_leaves_study_stopped_on_backup_error():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'trap restart_on_exit EXIT' in text
    assert 'stopped=1\nsystemctl stop "$SERVICE"' in text
    assert 'if [[ "$stopped" -eq 1 ]]' in text
    assert 'systemctl start "$SERVICE"' in text
    assert '--create --state-dir "$STATE"' in text
    assert '--verify --key-file "$KEY"' in text
    assert '--encrypted-file "$DEST"' in text
    assert 'flock -n 9' in text
    assert 'PY=/srv/ijcai-supervisor-backup/venv/bin/python' in text
    assert 'PY=/srv/ijcai-supervisor-staging/venv/bin/python' not in text
    assert 'from cryptography.hazmat.primitives.ciphers.aead import AESGCM' in text
    assert 'Service account cannot read the protected backup key' in text
    assert 'NOT VERIFIED: offsite storage' in text
