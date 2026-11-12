#!/usr/bin/env bash
# Controlled AES-256-GCM paired study database backup and memory-only drill.
# Requires existing institutionally protected key + private backup directory.
# Manual maintenance only: no auto key creation and no offsite copy.
set -Eeuo pipefail

SERVICE=ijcai-supervisor-staging
SERVICE_USER=ijcai-supervisor
ROOT=/srv/ijcai-supervisor-staging/current/agent2_realdata_benchmark
PY=/srv/ijcai-supervisor-staging/venv/bin/python
STATE=/var/lib/ijcai-supervisor-staging

[[ "$EUID" -eq 0 ]] || { echo "Root required" >&2; exit 2; }
[[ "$#" -eq 2 ]] || { echo "Usage: sudo bash $0 KEY_PATH NEW_ENCRYPTED_FILE" >&2; exit 2; }
KEY="$1"
DEST="$2"
[[ "$KEY" = /* && "$DEST" = /* ]] || { echo "Both paths must be absolute" >&2; exit 2; }
[[ -f "$KEY" && ! -L "$KEY" && ! -e "$DEST" && ! -L "$DEST" ]] || {
    echo "Existing key and NEW backup file path required" >&2; exit 2;
}
[[ -d "$ROOT" && -x "$PY" && -d "$STATE" ]] || {
    echo "Deployed staging code/SQLite state unavailable" >&2; exit 2;
}
command -v flock >/dev/null
command -v systemctl >/dev/null
command -v runuser >/dev/null

# Refuse concurrent paired snapshots.
exec 9>/run/lock/ijcai-supervisor-paired-backup.lock
flock -n 9 || { echo "Another paired backup is already running" >&2; exit 2; }

# Arrange a supervised quiet period before running. Never stop unknown units.
systemctl is-active --quiet "$SERVICE" || {
    echo "Study service is not active; investigate before taking backup" >&2; exit 2;
}
stopped=0
restart_on_exit() {
    local exit_status="$?"
    trap - EXIT
    if [[ "$stopped" -eq 1 ]]; then
        if ! systemctl start "$SERVICE" || ! systemctl is-active --quiet "$SERVICE"; then
            echo "CRITICAL: study service could not be restarted; escalate" >&2
            exit 1
        fi
    fi
    exit "$exit_status"
}
trap restart_on_exit EXIT

# Set before stop, to restart even if systemctl partially fails.
stopped=1
systemctl stop "$SERVICE"
if systemctl is-active --quiet "$SERVICE"; then
    echo "Service remained active; refusing inconsistent snapshot" >&2
    exit 2
fi

cd "$ROOT"
runuser -u "$SERVICE_USER" -- "$PY" -m scripts.supervisor_operational_backup_cli \
    --create --state-dir "$STATE" --key-file "$KEY" --encrypted-file "$DEST"

# Run the in-memory restore drill again after closing the encrypted backup.
runuser -u "$SERVICE_USER" -- "$PY" -m scripts.supervisor_operational_backup_cli \
    --verify --key-file "$KEY" --encrypted-file "$DEST"

systemctl start "$SERVICE"
systemctl is-active --quiet "$SERVICE" || {
    echo "CRITICAL: study service did not return to active" >&2; exit 1;
}
stopped=0
trap - EXIT
echo "PASS: encrypted paired snapshot and memory-only restore verification."
echo "PASS: study service restarted; no plaintext backup written."
echo "NOT VERIFIED: offsite storage, independent host restore, retention or GDPR erasure."
