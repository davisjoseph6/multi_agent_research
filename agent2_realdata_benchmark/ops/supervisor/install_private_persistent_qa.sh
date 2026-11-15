#!/usr/bin/env bash
# Set up a dedicated, persistent SSH-only QA service, never an institutional release.
set -Eeuo pipefail
umask 077
[[ "$EUID" -eq 0 && "$#" -eq 2 ]] || {
  echo "Usage: sudo bash install_private_persistent_qa.sh SCHOOL_EMAIL EXTERNAL_EMAIL" >&2
  exit 2
}
SCHOOL="$1"; EXTERNAL="$2"
[[ "$SCHOOL" =~ ^[A-Za-z0-9._%+-]+@aivancity\.education$ &&
   "$EXTERNAL" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$ &&
   "$EXTERNAL" != *@aivancity.education && "$EXTERNAL" != "$SCHOOL" ]] || {
  echo "Two different QA addresses, one school and one external, required" >&2
  exit 2
}
UNIT=ijcai-supervisor-private-qa
APPUSER=ijcai-supervisor-private-qa
STATE=/var/lib/ijcai-supervisor-private-qa
PRIVATE=/etc/ijcai-supervisor-private-qa
CODE=/srv/ijcai-supervisor-live/current/agent2_realdata_benchmark
PY=/srv/ijcai-supervisor-live/venv/bin/python
UNITFILE=/etc/systemd/system/ijcai-supervisor-private-qa.service
exec 9>/run/lock/ijcai-supervisor-private-qa-install.lock
flock -n 9 || { echo "QA installer locked" >&2; exit 2; }
[[ -d "$CODE" && -x "$PY" &&
   -f "$CODE/scripts/supervisor_private_qa.py" ]] || {
  echo "Install the pending exact Git source and virtualenv first" >&2
  exit 2
}
[[ ! -e "$UNITFILE" && ! -L "$UNITFILE" &&
   ! -e "$PRIVATE/qa.env" && ! -L "$PRIVATE/qa.env" &&
   ! -e /etc/caddy/ijcai-supervisor-private-qa.caddy ]] || {
  echo "Existing service/configuration: refusing to overwrite, restart or reset it" >&2
  exit 2
}
if ! id "$APPUSER" >/dev/null 2>&1; then
  useradd --system --no-create-home --home-dir /nonexistent \
    --shell /usr/sbin/nologin "$APPUSER"
fi
if [[ -e "$STATE" || -L "$STATE" ]]; then
  [[ -d "$STATE" && ! -L "$STATE" &&
     "$(stat -c '%U:%a' "$STATE")" == "$APPUSER:700" ]] || {
    echo "Existing QA state is not the dedicated owner-only directory" >&2
    exit 2
  }
else
  install -d -o "$APPUSER" -g "$APPUSER" -m 0700 "$STATE"
fi
if [[ -e "$PRIVATE" || -L "$PRIVATE" ]]; then
  [[ -d "$PRIVATE" && ! -L "$PRIVATE" &&
     "$(stat -c '%U:%a' "$PRIVATE")" == root:750 ]] || {
    echo "Existing QA private configuration directory mismatched" >&2
    exit 2
  }
else
  install -d -o root -g "$APPUSER" -m 0750 "$PRIVATE"
fi
(cd "$CODE" && "$PY" -c 'import cryptography,flask,scripts.supervisor_private_qa')
tmp="$(mktemp "$PRIVATE/.qa.env.XXXXXX")"
chmod 0640 "$tmp"
chown root:"$APPUSER" "$tmp"
printf 'SUPERVISOR_QA_SCHOOL_EMAIL=%s\nSUPERVISOR_QA_EXTERNAL_EMAIL=%s\n' \
  "$SCHOOL" "$EXTERNAL" >"$tmp"
mv -T -- "$tmp" "$PRIVATE/qa.env"
tmp="$(mktemp /etc/systemd/system/.ijcai-qa.XXXXXX)"
cat >"$tmp" <<'UNITFILE'
[Unit]
Description=IJCAI persistent private self-acceptance QA (NOT LIVE)
After=network.target
AssertPathExists=/srv/ijcai-supervisor-live/current/agent2_realdata_benchmark/scripts/supervisor_private_qa.py

[Service]
Type=simple
User=ijcai-supervisor-private-qa
Group=ijcai-supervisor-private-qa
WorkingDirectory=/srv/ijcai-supervisor-live/current/agent2_realdata_benchmark
EnvironmentFile=/etc/ijcai-supervisor-private-qa/qa.env
ExecStart=/srv/ijcai-supervisor-live/venv/bin/python -m scripts.supervisor_private_qa --port 8897 --school-email $SUPERVISOR_QA_SCHOOL_EMAIL --external-email $SUPERVISOR_QA_EXTERNAL_EMAIL --persistent-state-dir /var/lib/ijcai-supervisor-private-qa --acknowledge-private-qa-only
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/var/lib/ijcai-supervisor-private-qa
InaccessiblePaths=-/var/lib/ijcai-supervisor-live -/etc/ijcai-supervisor-live
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
LockPersonality=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
IPAddressDeny=any
IPAddressAllow=localhost

[Install]
WantedBy=multi-user.target
UNITFILE
chmod 0644 "$tmp"
mv -T -- "$tmp" "$UNITFILE"
systemctl daemon-reload
systemctl enable --now "$UNIT.service"
for _ in {1..20}; do
  if systemctl is-active --quiet "$UNIT.service" &&
     [[ "$(curl --silent --max-time 2 -o /dev/null -w '%{http_code}' \
       http://127.0.0.1:8897/interest/school || :)" == 200 ]]; then
    break
  fi
  sleep 1
done
systemctl is-active --quiet "$UNIT.service"
[[ "$(curl --silent --max-time 5 -o /dev/null -w '%{http_code}' \
  http://127.0.0.1:8897/questionnaire/student)" == 302 ]]
[[ "$(curl --silent --max-time 5 -o /dev/null -w '%{http_code}' \
  http://127.0.0.1:8897/control/api/overview)" == 409 ]]
[[ "$(curl --silent --max-time 5 -o /dev/null -w '%{http_code}' \
  http://127.0.0.1:8897/study/health)" == 200 ]]
ss -ltn | grep -Eq '127\.0\.0\.1:8897[[:space:]]'
! ss -ltn | grep -Eq '(^|[[:space:]])(0\.0\.0\.0|\[::\]):8897[[:space:]]'
echo "PASS: persistent private QA is bound to loopback port 8897; no public route."
echo "Four QA researcher accounts and participant responses now survive system restarts."
echo "No LIVE approval, enrollment, email or Caddy configuration changed."
echo "SSH tunnel: ssh -N -L 8897:127.0.0.1:8897 -i YOUR_KEY davis@YOUR_VPS"
