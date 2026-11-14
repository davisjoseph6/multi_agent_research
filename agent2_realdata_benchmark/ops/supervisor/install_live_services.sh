#!/usr/bin/env bash
# PREPARE an isolated real-human service with NO public activation, or ACTIVATE
# only after exact independently signed institutional release gates succeed.
# This installer does not replace current staging, demo, tokens or databases.
set -Eeuo pipefail
[[ "$EUID" -eq 0 ]] || { echo "sudo required" >&2; exit 2; }
[[ "$#" -ge 1 ]] || { echo "Usage: prepare BUNDLE_PATH COMMIT | activate APPROVED_GRACE_HOURS" >&2; exit 2; }
MODE="$1"
PREFIX=/srv/ijcai-supervisor-live
STATE=/var/lib/ijcai-supervisor-live
PRIVATE=/etc/ijcai-supervisor-live
APPUSER=ijcai-supervisor-live
PY="$PREFIX/venv/bin/python"
ENV="$PRIVATE/live.env"
STUDY=ijcai-supervisor-live-study
ADMIN=ijcai-supervisor-live-recruitment
CADDY=/etc/caddy/Caddyfile
SNIPPET="$PRIVATE/Caddyfile.fragment"
exec 9>/run/lock/ijcai-supervisor-live-install.lock
flock -n 9 || { echo "Another release installation is in progress" >&2; exit 2; }

if [[ "$MODE" == prepare ]]; then
  [[ "$#" -eq 3 ]] || { echo "Usage: prepare GIT_BUNDLE FULL_SHA" >&2; exit 2; }
  BUNDLE="$2"
  SHA="$3"
  [[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "Full Git SHA required" >&2; exit 2; }
  [[ -f "$BUNDLE" && ! -L "$BUNDLE" ]] || { echo "Locally uploaded Git bundle missing" >&2; exit 2; }
  [[ ! -e /etc/systemd/system/${STUDY}.service &&
     ! -e /etc/systemd/system/${ADMIN}.service ]] || {
    echo "An existing LIVE service exists; use a separately reviewed rollback/upgrade process" >&2;exit 2;
  }
  id "$APPUSER" >/dev/null 2>&1 || useradd --system --no-create-home \
    --home-dir /nonexistent --shell /usr/sbin/nologin "$APPUSER"
  install -d -o root -g root -m 0755 "$PREFIX" "$PREFIX/releases"
  install -d -o "$APPUSER" -g "$APPUSER" -m 0700 "$STATE"
  install -d -o "$APPUSER" -g "$APPUSER" -m 0700 "$STATE/oauth_vault"
  install -d -o "$APPUSER" -g "$APPUSER" -m 0700 "$STATE/document_registry"
  install -d -o root -g "$APPUSER" -m 0750 "$PRIVATE" "$PRIVATE/approvals" "$PRIVATE/mail"
  RELEASE="$PREFIX/releases/$SHA"
  [[ ! -e "$RELEASE" ]] || { echo "Release already prepared; do not overwrite" >&2; exit 2; }
  git clone --quiet --no-local "$BUNDLE" "$RELEASE"
  git -C "$RELEASE" checkout --quiet --detach "$SHA"
  [[ "$(git -C "$RELEASE" rev-parse HEAD)" == "$SHA" ]] || exit 2
  [[ -z "$(git -C "$RELEASE" status --porcelain)" ]] || exit 2
  chmod 0755 "$RELEASE"
  python3 -m venv "$PREFIX/venv"
  "$PY" -m pip install --disable-pip-version-check --quiet \
    Flask==3.1.3 gunicorn==23.0.0 cryptography==50.0.2
  ln -s "releases/$SHA" "$PREFIX/current"
  for name in study recruitment; do
    if [[ "$name" == study ]]; then
      PORT=8888
      WSGI='scripts.supervisor_vps_wsgi:make_wsgi_app()'
      UNIT="$STUDY"
    else
      PORT=8889
      WSGI='scripts.supervisor_recruitment_wsgi:make_wsgi_app()'
      UNIT="$ADMIN"
    fi
    cat > "/etc/systemd/system/${UNIT}.service" <<UNITFILE
[Unit]
Description=Signed IJCAI 2027 LIVE $name service
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=$APPUSER
Group=$APPUSER
WorkingDirectory=$PREFIX/current/agent2_realdata_benchmark
EnvironmentFile=$ENV
ExecStart=$PREFIX/venv/bin/gunicorn --bind 127.0.0.1:$PORT --workers 2 --threads 4 --timeout 45 --access-logfile /dev/null '$WSGI'
Restart=on-failure
RestartSec=5
UMask=0077
ProtectSystem=strict
ReadWritePaths=$STATE
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=true
RestrictSUIDSGID=true
LockPersonality=true
[Install]
WantedBy=multi-user.target
UNITFILE
  done
  systemctl daemon-reload
  echo "PREPARED ONLY: no LIVE systemd services, Caddy routes, emails or enrollment were activated."
  echo "Import final signed docs, approved institution mail policy, OAuth credentials, separate LIVE environment, and DNS before activate."
  exit 0
fi

[[ "$MODE" == activate && "$#" -eq 2 && "$2" =~ ^[0-9]{1,3}$ ]] || {
  echo "Usage: activate APPROVED_GRACE_HOURS" >&2; exit 2;
}
GRACE="$2"
[[ "$GRACE" -ge 1 && "$GRACE" -le 168 ]] || exit 2
[[ -f "$ENV" && ! -L "$ENV" && -L "$PREFIX/current" ]] || {
 echo "Missing trusted LIVE deployment source or environment" >&2;exit 2;
}
[[ "$(stat -c '%U' "$ENV")" == root ]] || exit 2
[[ "$(stat -c '%a' "$ENV")" == 640 ]] || exit 2
[[ "$(stat -c '%G' "$ENV")" == "$APPUSER" ]] || exit 2
# Source ONLY the root-owned, mode-0640, service-readable approved file.
set -a
source "$ENV"
set +a
[[ "${SUPERVISOR_VPS_MODE:-}" == live && "${SUPERVISOR_VPS_ROOT:-}" == "$STATE" ]] || exit 2
[[ "${SUPERVISOR_VPS_COMMIT:-}" == "$(git -C "$PREFIX/current" rev-parse HEAD)" ]] || exit 2
STUDY_HOST="${SUPERVISOR_VPS_HOST:-}"
RECRUIT_HOST="${SUPERVISOR_RECRUITMENT_HOST:-}"
for host in "$STUDY_HOST" "$RECRUIT_HOST"; do
  [[ "$host" =~ ^[a-z0-9-]+(\.[a-z0-9-]+)+$ ]] || { echo "Invalid LIVE domain" >&2;exit 2; }
  [[ "$host" != *demo* ]] || { echo "Demo hostname forbidden" >&2;exit 2; }
  getent ahostsv4 "$host" >/dev/null || { echo "LIVE DNS unresolved" >&2;exit 2; }
done
# The offline verifier imports both actual production WSGI apps and
# cryptographically rejects placeholder documents and unscoped mailbox grants.
runuser -u "$APPUSER" -- bash -c '
  set -Eeuo pipefail
  set -a
  source "$1"
  set +a
  cd "$2"
  exec "$3" -m scripts.supervisor_live_readiness
' bash "$ENV" "$PREFIX/current/agent2_realdata_benchmark" "$PY"

[[ -f "$CADDY" && ! -L "$CADDY" ]] || { echo "Existing Caddy configuration required" >&2;exit 2; }
[[ ! -e "$SNIPPET" ]] || { echo "Existing LIVE Caddy fragment needs manual review" >&2;exit 2; }
if [[ "$STUDY_HOST" == "$RECRUIT_HOST" ]]; then
cat > "$SNIPPET" <<EOF
$STUDY_HOST {
  handle /study/* {
    reverse_proxy 127.0.0.1:8888
  }
  handle /interest/* {
    reverse_proxy 127.0.0.1:8889
  }
  handle {
    respond "Not Found" 404
  }
}
EOF
else
cat > "$SNIPPET" <<EOF
$STUDY_HOST {
  handle /study/* {
    reverse_proxy 127.0.0.1:8888
  }
  handle { respond "Not Found" 404 }
}
$RECRUIT_HOST {
  handle /interest/* {
    reverse_proxy 127.0.0.1:8889
  }
  handle { respond "Not Found" 404 }
}
EOF
fi
chmod 0644 "$SNIPPET"
BACKUP="$PRIVATE/Caddyfile.before-live.$(date -u +%Y%m%dT%H%M%SZ)"
cp -a "$CADDY" "$BACKUP"
changed=0
rollback(){
  status="$?"
  trap - EXIT
  if [[ "$status" -ne 0 ]]; then
    echo "FAILED: deactivating LIVE services and restoring Caddy; STAGING untouched" >&2
    systemctl stop "$STUDY" "$ADMIN" >/dev/null 2>&1 || true
    systemctl disable "$STUDY" "$ADMIN" >/dev/null 2>&1 || true
    if [[ "$changed" -eq 1 ]]; then
      cp -a "$BACKUP" "$CADDY"
      caddy validate --config "$CADDY" || true
      systemctl reload caddy || true
    fi
  fi
  exit "$status"
}
trap rollback EXIT
systemctl enable --now "$STUDY" "$ADMIN"
for _ in {1..25}; do
  systemctl is-active --quiet "$STUDY" && systemctl is-active --quiet "$ADMIN" &&
  ss -ltn | grep -q '127.0.0.1:8888 ' && ss -ltn | grep -q '127.0.0.1:8889 ' && break
  sleep 1
done
systemctl is-active --quiet "$STUDY"
systemctl is-active --quiet "$ADMIN"
ss -ltn | grep -q '127.0.0.1:8888 '
ss -ltn | grep -q '127.0.0.1:8889 '
[[ "$(curl --silent --max-time 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8889/control/)" == 403 ]] || {
  echo "Private dashboard direct HTTP must be blocked" >&2;exit 2;
}
if grep -Fq 'import /etc/ijcai-supervisor-live/Caddyfile.fragment' "$CADDY"; then
  echo "Caddy import already exists; validating recognized exact path."
else
  printf '\nimport /etc/ijcai-supervisor-live/Caddyfile.fragment\n' >> "$CADDY"
  changed=1
fi
caddy validate --config "$CADDY"
systemctl reload caddy
for entry in "$STUDY_HOST:/study/:200" "$RECRUIT_HOST:/interest/school:200" "$STUDY_HOST:/control/:404"; do
  host="${entry%%:*}"
  target="${entry#*:}"
  route="${target%:*}"
  expected="${target##*:}"
  found="$(curl --silent --max-time 15 -o /dev/null -w '%{http_code}' "https://$host$route")"
  [[ "$found" == "$expected" ]] || {
    echo "LIVE HTTPS route $route failed expected $expected, actual $found" >&2;exit 2;
  }
done
# Activate reminders only AFTER service/TLS, authorization and private route checks.
bash "$PREFIX/current/agent2_realdata_benchmark/ops/supervisor/install_live_reminder_timer.sh" "$GRACE"
trap - EXIT
echo "PASS: institution-signed LIVE release verified, non-demo HTTPS routes active, reminder timer installed."
echo "Check independent monitoring/backups and owner-scoped sent-mail end-to-end before inviting anyone."
