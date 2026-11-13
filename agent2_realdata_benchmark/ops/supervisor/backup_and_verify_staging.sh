#!/usr/bin/env bash
# Staging-only encrypted backup with guaranteed service restart on EXIT.
# Requires an EXISTING, separately custodied 32-byte key and an empty
# private output filename. NEVER create or overwrite a backup key here.
set -Eeuo pipefail
[[ "${EUID}" -eq 0 ]] || { echo "Run with sudo" >&2; exit 2; }
[[ "$#" -eq 2 ]] || {
  echo "Usage: sudo bash backup_and_verify_staging.sh /private/key.bin /private/new.enc" >&2
  exit 2
}
KEY="$1"
OUT="$2"
PREFIX=/srv/ijcai-supervisor-staging
SERVICE=ijcai-supervisor-staging
ENV=/etc/ijcai-supervisor-staging/staging.env
[[ -f "$ENV" && ! -L "$ENV" ]] || { echo "Missing staging configuration" >&2; exit 2; }
grep -qx 'SUPERVISOR_VPS_MODE=staging' "$ENV" || {
  echo "Refusing automated backup on a non-staging deployment" >&2; exit 2;
}
[[ "$KEY" = /* && "$OUT" = /* ]] || { echo "Absolute paths required" >&2; exit 2; }
[[ -f "$KEY" && ! -L "$KEY" && ! -e "$OUT" && ! -L "$OUT" ]] || {
  echo "Existing private key and NEW output filename required" >&2; exit 2;
}
[[ -x "$PREFIX/venv/bin/python" && -d "$PREFIX/current/agent2_realdata_benchmark" ]] || {
  echo "Study Python and deployed source required" >&2; exit 2;
}
systemctl is-active --quiet "$SERVICE" || {
  echo "Study service must be active before controlled backup" >&2; exit 2;
}
RESTORE_SERVICE=1
restore_service() {
  local exit_status=$?
  trap - EXIT
  if [[ "${RESTORE_SERVICE}" -eq 1 ]]; then
    systemctl start "$SERVICE" || exit_status=1
    systemctl is-active --quiet "$SERVICE" || exit_status=1
  fi
  exit "$exit_status"
}
trap restore_service EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
systemctl stop "$SERVICE"
# Avoid exposing the key, decrypted data or personal contacts in command logs.
runuser -u ijcai-supervisor -- env \
  PYTHONDONTWRITEBYTECODE=1 \
  "$PREFIX/venv/bin/python" -m scripts.supervisor_operational_backup_cli \
  --create --state-dir /var/lib/ijcai-supervisor-staging \
  --key-file "$KEY" --encrypted-file "$OUT"
runuser -u ijcai-supervisor -- env \
  PYTHONDONTWRITEBYTECODE=1 \
  "$PREFIX/venv/bin/python" -m scripts.supervisor_operational_backup_cli \
  --verify --key-file "$KEY" --encrypted-file "$OUT"
echo "Encrypted paired snapshot and in-memory integrity verification succeeded."
echo "This is not proof of an offsite copy, independent restore, or retention approval."
