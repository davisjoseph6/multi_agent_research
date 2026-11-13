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
systemctl is-active --quiet ijcai-supervisor-recruitment || {
  journalctl -u ijcai-supervisor-recruitment -n 20 --no-pager;exit 2;
}
login_status="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8791/control/)"
private_status="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8791/control/api/overview)"
form_status="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8791/interest/school)"
[[ "$login_status" == 200 && "$private_status" == 409 && "$form_status" == 404 ]] || {
 echo "Bad preview security status: login=$login_status private=$private_status forms=$form_status" >&2;exit 2;
}
echo "PASS: private researcher preview on 127.0.0.1:8791 (SSH tunnel only)."
echo "PASS: anonymous PII query rejected; public questionnaire intake disabled."
echo "Original study /study/, Caddy, SMTP, participant accounts, and RCT databases unchanged."
