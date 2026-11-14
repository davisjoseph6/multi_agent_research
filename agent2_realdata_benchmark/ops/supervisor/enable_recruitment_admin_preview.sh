#!/usr/bin/env bash
# Opt-in, loopback-only recruitment researcher preview. Never exposes student
# PII over public Caddy and never enables real public questionnaire intake.
# Requires previously installed staging service + read-only source pin.
set -Eeuo pipefail

[[ "$EUID" -eq 0 ]] || { echo "Run as root with sudo"; exit 2; }
PREFIX=/srv/ijcai-supervisor-staging
ROOT=/var/lib/ijcai-supervisor-staging
ENV_FILE=/etc/ijcai-supervisor-staging/staging.env
UNIT=/etc/systemd/system/ijcai-supervisor-recruitment.service
PY="$PREFIX/venv/bin/python"
[[ -d "$ROOT" && ! -L "$ROOT" && -f "$ENV_FILE" &&
   -x "$PY" && -d "$PREFIX/current/agent2_realdata_benchmark" ]] || {
    echo "Original read-only staging release and protected environment required" >&2
    exit 2
}
id ijcai-supervisor >/dev/null 2>&1 || {
  echo "Existing dedicated service account required" >&2;exit 2;
}
[[ "$(stat -c %a "$ROOT")" == 700 ]] || {
  echo "Private research data directory must be 0700" >&2;exit 2;
}
[[ -f "$PREFIX/current/agent2_realdata_benchmark/scripts/supervisor_recruitment_wsgi.py" ]] || {
  echo "Commit with isolated recruitment preview was not installed" >&2;exit 2;
}
# Never start this service with live enrollment mode. Staging is the only
# supported install via this script. A different independently signed release
# process is required before public questionnaire deployment.
grep -qx 'SUPERVISOR_VPS_MODE=staging' "$ENV_FILE" || {
  echo "Staging-mode environment required";exit 2;
}
cd "$PREFIX/current/agent2_realdata_benchmark"
runuser -u ijcai-supervisor -- "$PY" -c   'from src.prototype.supervisor_recruitment import RecruitmentLedger;from pathlib import Path;RecruitmentLedger(Path("/var/lib/ijcai-supervisor-staging"))'
cat > "$UNIT" <<'UNIT'
[Unit]
Description=Researcher-only recruitment preview (SSH tunnel)
After=network-online.target ijcai-supervisor-staging.service
Wants=network-online.target

[Service]
Type=simple
User=ijcai-supervisor
Group=ijcai-supervisor
WorkingDirectory=/srv/ijcai-supervisor-staging/current/agent2_realdata_benchmark
EnvironmentFile=/etc/ijcai-supervisor-staging/staging.env
Environment=SUPERVISOR_RECRUITMENT_HOST=localhost
UMask=0077
ExecStart=/srv/ijcai-supervisor-staging/venv/bin/gunicorn --bind 127.0.0.1:8791 --workers 1 --threads 4 --timeout 45 --access-logfile /dev/null 'scripts.supervisor_recruitment_wsgi:make_wsgi_app()'
Restart=on-failure
RestartSec=5
ProtectSystem=strict
# The private SQLite ledger must remain writable under ProtectSystem=strict.
# All other filesystem paths are read-only; do not grant write access to
# source releases, Caddy, or operator data outside this protected directory.
ReadWritePaths=/var/lib/ijcai-supervisor-staging
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=true
RestrictSUIDSGID=true
LockPersonality=true

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable ijcai-supervisor-recruitment
systemctl restart ijcai-supervisor-recruitment
# Type=simple is considered active before Gunicorn has finished importing the
# app and bound its socket. Give it a bounded startup window and preserve the
# original service/journal diagnostics when the boot never becomes healthy.
# Do not read or print participant data, cookies, or administrator passwords.
http_code() {
  curl --silent --show-error --max-time 2 -o /dev/null \
    -w '%{http_code}' "http://127.0.0.1:8791$1" 2>/dev/null
}
ready=0
for attempt in {1..25}; do
  if systemctl is-active --quiet ijcai-supervisor-recruitment; then
    if login_status="$(http_code /control/)" && [[ "$login_status" == 200 ]]; then
      ready=1
      break
    fi
  fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  echo "FAIL: researcher dashboard did not bind and respond within 25 seconds." >&2
  systemctl --no-pager --full status ijcai-supervisor-recruitment >&2 || true
  journalctl -u ijcai-supervisor-recruitment -n 40 --no-pager >&2 || true
  ss -ltn '( sport = :8791 )' >&2 || true
  exit 2
fi
private_status="$(http_code /control/api/overview)" || {
  echo "FAIL: unauthorized researcher API check could not connect" >&2;exit 2;
}
form_status="$(http_code /interest/school)" || {
  echo "FAIL: disabled student interest route check could not connect" >&2;exit 2;
}
[[ "$private_status" == 409 && "$form_status" == 404 ]] || {
  echo "FAIL: forbidden route security status: private=$private_status form=$form_status" >&2
  exit 2
}
echo "PASS: private researcher preview on 127.0.0.1:8791 (SSH tunnel only)."
echo "PASS: anonymous PII query rejected; public questionnaire intake disabled."
echo "Original study /study/, Caddy, SMTP, participant accounts, and RCT databases unchanged."
