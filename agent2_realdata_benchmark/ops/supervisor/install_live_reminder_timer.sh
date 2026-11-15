#!/usr/bin/env bash
# Install ONLY the scheduled 3/4/7-day mail + attendance worker on a
# separately authorized LIVE deployment. Does not install Caddy routes,
# create users, deploy code, change staging, or send any email during setup.
set -Eeuo pipefail
[[ "${EUID}" -eq 0 ]] || { echo "Run under sudo" >&2; exit 2; }
[[ "$#" -eq 1 && "$1" =~ ^[0-9]{1,3}$ ]] || {
  echo "Usage: sudo bash install_live_reminder_timer.sh APPROVED_GRACE_HOURS" >&2
  exit 2
}
GRACE_HOURS="$1"
[[ "$GRACE_HOURS" -ge 1 && "$GRACE_HOURS" -le 168 ]] || {
  echo "Approved grace hours out of range 1..168" >&2; exit 2;
}
PREFIX=/srv/ijcai-supervisor-live
STATE=/var/lib/ijcai-supervisor-live
ENV_FILE=/etc/ijcai-supervisor-live/live.env
ACCOUNT=ijcai-supervisor-live
WORK="$PREFIX/current/agent2_realdata_benchmark"
PY="$PREFIX/venv/bin/python"
SERVICE=/etc/systemd/system/ijcai-supervisor-live-reminders.service
TIMER=/etc/systemd/system/ijcai-supervisor-live-reminders.timer
command -v flock >/dev/null
command -v runuser >/dev/null
command -v systemctl >/dev/null
exec 9>/run/lock/ijcai-supervisor-live-reminders-install.lock
flock -n 9 || { echo "Reminder timer installer already running" >&2; exit 2; }
if [[ ! -f "$ENV_FILE" || -L "$ENV_FILE" ||
      ! -d "$STATE" || -L "$STATE" ||
      ! -x "$PY" || ! -f "$WORK/scripts/supervisor_vps_daily.py" ||
      ! -d "$PREFIX/current/.git" && ! -f "$PREFIX/current/.git" ]]; then
  echo "A trusted, clean, signed LIVE Git checkout and protected environment are required" >&2
  exit 2
fi
id "$ACCOUNT" >/dev/null 2>&1 || { echo "Dedicated live service user missing" >&2; exit 2; }
[[ "$(stat -c '%a' "$STATE")" == 700 ]] || { echo "LIVE state must be mode 0700" >&2; exit 2; }
[[ "$(stat -c '%U' "$STATE")" == "$ACCOUNT" ]] || { echo "LIVE state owner mismatch" >&2; exit 2; }
# These exact values are expected in the trusted root-owned environment.
[[ "$(stat -c '%U' "$ENV_FILE")" == root ]] || {
  echo "LIVE environment must be root-owned" >&2; exit 2;
}
[[ ! -w "$ENV_FILE" || "$(stat -c '%a' "$ENV_FILE")" == 640 ]] || {
  echo "LIVE environment must not be writable by untrusted users" >&2; exit 2;
}
grep -qx 'SUPERVISOR_VPS_MODE=live' "$ENV_FILE" || {
  echo "LIVE mode is not configured" >&2; exit 2;
}
grep -qx "SUPERVISOR_VPS_ROOT=$STATE" "$ENV_FILE" || {
  echo "LIVE state directory mismatch" >&2; exit 2;
}
grep -qx 'SUPERVISOR_MAIL_TRANSPORT=provider_router' "$ENV_FILE" || {
  echo "Signed provider-neutral mail router is not configured" >&2; exit 2;
}
for required in SUPERVISOR_MAIL_CONFIG SUPERVISOR_MAIL_APPROVAL SUPERVISOR_MAIL_APPROVAL_SIGNATURE SUPERVISOR_MAIL_AUDIT_DB SUPERVISOR_MAIL_AUDIT_KEY_FILE SUPERVISOR_DOC_BUNDLE_ROOT; do
  grep -q "^${required}=" "$ENV_FILE" || {
    echo "Required live environment setting missing: $required" >&2; exit 2;
  }
done
if [[ -e "$SERVICE" || -e "$TIMER" ]]; then
  echo "Existing timer or service present; review it manually before replacement" >&2
  exit 2
fi
# Fail CLOSED if signed 14-item release evidence or PI content is unverified.
# Source only the trusted, private administrator-maintained environment file.
# This checks the LIVE gate offline and does not instantiate a sender.
runuser -u "$ACCOUNT" -- bash -c '
  set -Eeuo pipefail
  set -a
  source "$1"
  set +a
  cd "$2"
  "$3" -c "from scripts.supervisor_vps_admin import load; from scripts.supervisor_recruitment_wsgi import make_wsgi_app; load(); make_wsgi_app()"
' bash "$ENV_FILE" "$WORK" "$PY"
# systemd timer creates a new process each hour. Persistent=true catches
# missed schedule windows on VPS reboot. The worker handles idempotency in SQLite.
# All recipient and token data remain in private vaults; no credentials in unit.
cat > "$SERVICE" <<UNIT
[Unit]
Description=Signed-live researcher attendance and reminder reconciliation
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$ACCOUNT
Group=$ACCOUNT
WorkingDirectory=$WORK
EnvironmentFile=$ENV_FILE
UMask=0077
ExecStart=/usr/bin/flock -n $STATE/.reminders.lock $PY -m scripts.supervisor_vps_daily --grace-hours $GRACE_HOURS --send
ProtectSystem=strict
ReadWritePaths=$STATE
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=true
RestrictSUIDSGID=true
LockPersonality=true
TimeoutStartSec=180
UNIT
cat > "$TIMER" <<'UNIT'
[Unit]
Description=Hourly supervisor LIVE reminder/attendance schedule

[Timer]
OnCalendar=hourly
Persistent=true
RandomizedDelaySec=5m
Unit=ijcai-supervisor-live-reminders.service

[Install]
WantedBy=timers.target
UNIT
chmod 0644 "$SERVICE" "$TIMER"
systemctl daemon-reload
systemctl enable --now ijcai-supervisor-live-reminders.timer
systemctl is-active --quiet ijcai-supervisor-live-reminders.timer || {
  echo "Timer is not active" >&2; exit 2;
}
echo "PASS: installed separate LIVE-only timer (no email sent by installer)."
echo "Check: systemctl list-timers ijcai-supervisor-live-reminders.timer"
echo "After the next tick inspect the service result; do not claim delivery based only on Graph 202."
