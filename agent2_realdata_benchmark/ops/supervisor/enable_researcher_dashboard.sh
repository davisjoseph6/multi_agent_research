#!/usr/bin/env bash
# Opt-in administrative visualization, never exposed by Caddy.
# Authenticated Basic credentials over a per-researcher SSH tunnel ONLY.
set -Eeuo pipefail
[[ "$EUID" -eq 0 ]] || { echo "Run with sudo" >&2; exit 2; }
PREFIX=/srv/ijcai-supervisor-staging
ROOT=/var/lib/ijcai-supervisor-staging
ENV_DIR=/etc/ijcai-supervisor-staging
ADMIN_ENV=${ENV_DIR}/researcher.env
SERVICE=ijcai-supervisor-researcher
[[ -d "$ROOT" && ! -L "$ROOT" && -d "$PREFIX/current/agent2_realdata_benchmark" ]] ||
  { echo "Staging release and private database must exist first" >&2; exit 2; }
[[ -f "$ROOT/supervisor_operational_study.sqlite3" ]] ||
  { echo "Existing study research database required" >&2; exit 2; }
id ijcai-supervisor >/dev/null
[[ -x "$PREFIX/venv/bin/gunicorn" ]] || { echo "Gunicorn missing" >&2; exit 2; }
if [[ -e "$ADMIN_ENV" ]]; then
  echo "Researcher secret is already configured; refusing silent replacement" >&2
  echo "Stop this unit and archive the old secret manually to perform an authorized rotation." >&2
  exit 2
fi
cd "$PREFIX/current/agent2_realdata_benchmark"
umask 077
# The password never appears in shell command arguments or command history.
hash="$("$PREFIX/venv/bin/python" - <<'PY'
from getpass import getpass
from src.prototype.supervisor_research_monitor import password_hash
secret=getpass("New independent researcher password (min 18 characters): ")
confirmed=getpass("Repeat independent researcher password: ")
if secret != confirmed:
    raise SystemExit("Passwords do not match; no change made")
print(password_hash(secret))
PY
)"
[[ "$hash" == pbkdf2_sha256\$* ]] || exit 2
temp="$(mktemp "$ENV_DIR/.researcher.env.XXXXXXXX")"
trap 'rm -f -- "$temp"' EXIT
printf 'SUPERVISOR_VPS_ROOT=%s\nSUPERVISOR_ADMIN_PASSWORD_HASH=%s\n' "$ROOT" "$hash" > "$temp"
chown root:ijcai-supervisor "$temp"
chmod 0640 "$temp"
mv -n "$temp" "$ADMIN_ENV"
cat > "/etc/systemd/system/${SERVICE}.service" <<UNIT
[Unit]
Description=Read-only researcher BKT dashboard (SSH tunnel only)
After=network-online.target ijcai-supervisor-staging.service
Wants=network-online.target

[Service]
Type=simple
User=ijcai-supervisor
Group=ijcai-supervisor
WorkingDirectory=${PREFIX}/current/agent2_realdata_benchmark
EnvironmentFile=${ADMIN_ENV}
UMask=0077
ExecStart=${PREFIX}/venv/bin/gunicorn --bind 127.0.0.1:8790 --workers 1 --threads 4 --timeout 30 --access-logfile /dev/null 'scripts.supervisor_research_monitor_wsgi:make_wsgi_app()'
Restart=on-failure
RestartSec=5
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=true
RestrictSUIDSGID=true
LockPersonality=true

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"
sleep 2
systemctl is-active --quiet "$SERVICE" || { journalctl -u "$SERVICE" -n 35 --no-pager; exit 2; }
code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 6 http://127.0.0.1:8790/admin/)"
[[ "$code" == 401 ]] || { echo "Unauthenticated researcher endpoint MUST return 401, got $code" >&2; exit 2; }
echo "Authenticated BKT researcher monitor enabled locally on 127.0.0.1:8790."
echo "No Caddy route created. Use SSH -L 8790:127.0.0.1:8790 and your separate researcher password."
