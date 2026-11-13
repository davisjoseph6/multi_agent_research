#!/usr/bin/env bash
# Install an authenticated TEST deployment on the existing IONOS VPS.
# Does not touch the RCT operator demo, its 8077 port, DB or systemd unit.
set -Eeuo pipefail
[[ "$EUID" -eq 0 ]] || { echo "Run with sudo"; exit 2; }

SOURCE="${SUPERVISOR_UPLOAD:-/home/davis/ijcai_supervisor_upload}"
HOST="demo.selfhealing-edu.fr"
SERVICE="ijcai-supervisor-staging"
PREFIX="/srv/${SERVICE}"
STATE="/var/lib/${SERVICE}"
ENV_DIR="/etc/${SERVICE}"
ENV_FILE="${ENV_DIR}/staging.env"
CADDY="/etc/caddy/Caddyfile"

[[ -f "${SOURCE}/.supervisor-source-revision" ]] || { echo "Missing pinned source revision"; exit 2; }
SHA="$(tr -d '\n' < "${SOURCE}/.supervisor-source-revision")"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "Invalid full source commit"; exit 2; }
[[ -f "${SOURCE}/agent2_realdata_benchmark/scripts/supervisor_vps_wsgi.py" ]] || { echo "Application source missing"; exit 2; }
[[ -f "$CADDY" ]] || { echo "Existing Caddyfile required"; exit 2; }
if find "$SOURCE" -type l -print -quit | grep -q .; then
    echo "Symlinks in uploaded archive refused"; exit 2
fi

command -v python3 >/dev/null
command -v caddy >/dev/null
command -v curl >/dev/null
command -v systemctl >/dev/null

if ! id ijcai-supervisor >/dev/null 2>&1; then
    useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin ijcai-supervisor
fi
install -d -m 0755 "${PREFIX}" "${PREFIX}/releases"
install -d -o ijcai-supervisor -g ijcai-supervisor -m 0700 "$STATE"
install -d -o root -g ijcai-supervisor -m 0750 "$ENV_DIR"
RELEASE="${PREFIX}/releases/${SHA}"
if [[ -e "$RELEASE" ]]; then
    test "$(cat "${RELEASE}/.supervisor-source-revision")" = "$SHA" || {
        echo "Source revision collision"; exit 2;
    }
else
    install -d -m 0755 "$RELEASE"
    cp -a "$SOURCE/." "$RELEASE/"
    chmod -R go-w "$RELEASE"
fi

# cp -a "$SOURCE/." "$RELEASE/" preserves the source directory's mode on
# the destination itself. The SSH upload is deliberately 0700, but the
# dedicated service user needs to traverse this public-code release folder.
# Repair this mode even on re-runs after a previous failed deployment.
# Never relax permissions on the private databases or /etc environment file.
chmod 0755 "$RELEASE"

command -v runuser >/dev/null || { echo "runuser required for service-user preflight"; exit 2; }
for executable_dir in "$PREFIX" "$PREFIX/releases" "$RELEASE" \
    "$RELEASE/agent2_realdata_benchmark" \
    "$RELEASE/agent2_realdata_benchmark/scripts"; do
    if ! runuser -u ijcai-supervisor -- test -x "$executable_dir"; then
        echo "Service user cannot enter directory: $executable_dir" >&2
        ls -ld "$executable_dir" >&2 || true
        exit 2
    fi
done
if ! runuser -u ijcai-supervisor -- \
    test -r "$RELEASE/agent2_realdata_benchmark/scripts/supervisor_vps_wsgi.py"; then
    echo "Service user cannot read the WSGI entrypoint" >&2
    exit 2
fi

python3 -m venv "${PREFIX}/venv"
"${PREFIX}/venv/bin/python" -m pip install --disable-pip-version-check \
    Flask==3.1.3 gunicorn==23.0.0

# A failed upgrade must NOT strand the current portal, remove existing
# reviewer credentials, or overwrite staging program/administrative choices.
# Save all mutable deployment surfaces before changing any of them.
[[ ! -e "${PREFIX}/current" || -L "${PREFIX}/current" ]] || {
    echo "Current release must be absent or a symlink" >&2; exit 2;
}
[[ ! -e "$ENV_FILE" || ( -f "$ENV_FILE" && ! -L "$ENV_FILE" ) ]] || {
    echo "Staging environment must be a non-symlink file" >&2; exit 2;
}
ROLLBACK_DIR="$(mktemp -d /root/ijcai-staging-redeploy.XXXXXXXX)"
chmod 0700 "$ROLLBACK_DIR"
HAD_ENV=0
HAD_UNIT=0
HAD_CADDY=0
OLD_RELEASE=""
if [[ -L "${PREFIX}/current" ]]; then
    OLD_RELEASE="$(readlink "${PREFIX}/current")"
fi
if [[ -f "$ENV_FILE" ]]; then
    HAD_ENV=1
    cp -a "$ENV_FILE" "$ROLLBACK_DIR/staging.env"
fi
if [[ -f "/etc/systemd/system/${SERVICE}.service" ]]; then
    HAD_UNIT=1
    cp -a "/etc/systemd/system/${SERVICE}.service" "$ROLLBACK_DIR/service"
fi
cp -a "$CADDY" "$ROLLBACK_DIR/Caddyfile"
HAD_CADDY=1
CHANGED=0
rollback() {
    local status="$?"
    trap - EXIT
    set +e
    if [[ "$status" -ne 0 && "$CHANGED" -eq 1 ]]; then
        echo "DEPLOYMENT FAILURE: restoring the previous staging release" >&2
        if [[ -n "$OLD_RELEASE" ]]; then
            ln -s "$OLD_RELEASE" "${PREFIX}/.rollback-current.$" &&
              mv -Tf "${PREFIX}/.rollback-current.$" "${PREFIX}/current"
        else
            rm -f "${PREFIX}/current"
        fi
        if [[ "$HAD_ENV" -eq 1 ]]; then
            cp -a "$ROLLBACK_DIR/staging.env" "$ENV_FILE"
        else
            rm -f "$ENV_FILE"
        fi
        if [[ "$HAD_UNIT" -eq 1 ]]; then
            cp -a "$ROLLBACK_DIR/service" "/etc/systemd/system/${SERVICE}.service"
        else
            rm -f "/etc/systemd/system/${SERVICE}.service"
        fi
        if [[ "$HAD_CADDY" -eq 1 ]]; then
            cp -a "$ROLLBACK_DIR/Caddyfile" "$CADDY"
            systemctl reload caddy || echo "CRITICAL: Caddy rollback reload failed" >&2
        fi
        systemctl daemon-reload
        if [[ -n "$OLD_RELEASE" && "$HAD_UNIT" -eq 1 ]]; then
            systemctl restart "$SERVICE" ||
                echo "CRITICAL: previous study service did not restart" >&2
        else
            systemctl stop "$SERVICE" || true
        fi
    fi
    rm -rf -- "$ROLLBACK_DIR"
    exit "$status"
}
trap rollback EXIT
CHANGED=1

# Preserve existing approved staging-only program lists/settings. Only the
# pinned source revision changes on redeployment. Never mutate a live config.
if [[ "$HAD_ENV" -eq 1 ]]; then
    export SUPERVISOR_EXISTING_ENV="$ENV_FILE"
    export SUPERVISOR_NEXT_SHA="$SHA"
    python3 - <<'PY'
from pathlib import Path
import os,re
p=Path(os.environ["SUPERVISOR_EXISTING_ENV"])
s=p.read_text(encoding="utf-8")
required={
    "SUPERVISOR_VPS_MODE":"staging",
    "SUPERVISOR_VPS_ROOT":"/var/lib/ijcai-supervisor-staging",
    "SUPERVISOR_VPS_HOST":"demo.selfhealing-edu.fr",
}
for key,expected in required.items():
    values=re.findall(r"(?m)^"+re.escape(key)+r"=(.*)$",s)
    if values!=[expected]:
        raise SystemExit("Expected an exact pre-existing STAGING environment value: "+key)
if len(re.findall(r"(?m)^SUPERVISOR_VPS_COMMIT=",s))!=1:
    raise SystemExit("Missing/duplicated pinned revision")
if len(re.findall(r"(?m)^SUPERVISOR_PROGRAMS=",s))!=1:
    raise SystemExit("Missing/duplicated staging academic programs")
s=re.sub(r"(?m)^SUPERVISOR_VPS_COMMIT=[0-9a-f]{40}$",
         "SUPERVISOR_VPS_COMMIT="+os.environ["SUPERVISOR_NEXT_SHA"],s,count=1)
if "SUPERVISOR_VPS_COMMIT="+os.environ["SUPERVISOR_NEXT_SHA"] not in s:
    raise SystemExit("Cannot replace old source commit")
# This replaces only the known path and preserves its private ownership/mode
# through the atomic same-directory swap.
from tempfile import NamedTemporaryFile
from os import chmod,chown,replace
mode=p.stat()
with NamedTemporaryFile(mode="w",encoding="utf-8",dir=p.parent,
                        prefix=".staging-env-",delete=False) as tmp:
    tmp.write(s)
    tmp.flush()
    os.fsync(tmp.fileno())
    name=tmp.name
chmod(name,mode.st_mode & 0o777)
chown(name,mode.st_uid,mode.st_gid)
replace(name,p)
PY
else
    cat > "$ENV_FILE" <<ENV
SUPERVISOR_VPS_MODE=staging
SUPERVISOR_VPS_ROOT=${STATE}
SUPERVISOR_VPS_HOST=${HOST}
SUPERVISOR_VPS_COMMIT=${SHA}
SUPERVISOR_PROGRAMS="Synthetic classroom demonstration"
ENV
    chown root:ijcai-supervisor "$ENV_FILE"
    chmod 0640 "$ENV_FILE"
fi

# Atomic switch, avoiding the missing-link interval of ln -sfn.
ln -s "${PREFIX}/releases/${SHA}" "${PREFIX}/.next-current.$"
mv -Tf "${PREFIX}/.next-current.$" "${PREFIX}/current"

cat > "/etc/systemd/system/${SERVICE}.service" <<UNIT
[Unit]
Description=Supervisor three-arm study (STAGING only, protected by existing Caddy basic auth)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ijcai-supervisor
Group=ijcai-supervisor
WorkingDirectory=${PREFIX}/current/agent2_realdata_benchmark
EnvironmentFile=${ENV_FILE}
UMask=0077
ExecStart=${PREFIX}/venv/bin/gunicorn --bind 127.0.0.1:8788 --workers 1 --threads 8 --timeout 60 --access-logfile /dev/null 'scripts.supervisor_vps_wsgi:make_wsgi_app()'
Restart=on-failure
RestartSec=5
StateDirectory=ijcai-supervisor-staging
StateDirectoryMode=0700
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=true
ReadWritePaths=${STATE}
RestrictSUIDSGID=true
LockPersonality=true

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable "${SERVICE}"
# enable --now need not restart an existing unit after an upgrade.
# Explicit restart also recovers a previously failed 200/CHDIR unit.
systemctl restart "${SERVICE}"
sleep 2
systemctl is-active --quiet "${SERVICE}" || {
    journalctl -u "${SERVICE}" -n 35 --no-pager; exit 2;
}

# Local health route must respond before changing the existing public proxy.
local_status="$(curl -fsS --max-time 8 -H "Host: ${HOST}" \
    -H 'X-Forwarded-Proto: https' -H 'X-Forwarded-For: 127.0.0.1' \
    http://127.0.0.1:8788/study/health)"
printf '%s' "$local_status" | grep -q '"enrollment_authorized":false' || {
    echo "Staging health gate refused"; exit 2;
}

backup="${CADDY}.supervisor.bak.$(date -u +%Y%m%dT%H%M%SZ)"
cp -a "$CADDY" "$backup"
export SUPERVISOR_CADDYFILE="$CADDY"
python3 - <<'PY'
from pathlib import Path
import os
p=Path(os.environ["SUPERVISOR_CADDYFILE"])
s=p.read_text(encoding="utf-8")
if "@supervisorStudy path /study /study/*" in s:
    print("Caddy supervisor route already exists")
else:
    # Fail rather than altering an unknown Caddy configuration. Preserve
    # existing Basic Auth, demo reverse proxy and all other services.
    if '@frontend not path /api/rct/*' not in s:
        raise SystemExit("Expected existing Basic Auth matcher not found")
    target="reverse_proxy 127.0.0.1:8077 {"
    if s.count(target)!=1:
        raise SystemExit("Expected one untouched operator-demo proxy")
    snippet=(
        "@supervisorStudy path /study /study/*\n"
        "    reverse_proxy @supervisorStudy 127.0.0.1:8788 {\n"
        "        header_up Host {host}\n"
        "        header_up X-Forwarded-Proto https\n"
        "        header_up X-Forwarded-For {remote_host}\n"
        "    }\n"
        "    "
    )
    p.write_text(s.replace(target,snippet+target),encoding="utf-8")
    print("Additional supervisor route inserted; existing demo preserved")
PY
if ! caddy validate --config "$CADDY" --adapter caddyfile; then
    cp -a "$backup" "$CADDY"
    echo "Caddy configuration invalid. Original restored."
    exit 2
fi
if ! systemctl reload caddy; then
    cp -a "$backup" "$CADDY"
    systemctl reload caddy || true
    echo "Caddy reload failed. Original restored."
    exit 2
fi
echo "STAGING service is active on 127.0.0.1:8788."
echo "Existing Basic Auth protects https://${HOST}/study/."
echo "Real enrollment: DISABLED. SMTP: DISABLED."
echo "Original operator demo port 8077 and databases were not replaced."
echo "Caddy backup: $backup"
# A successful install releases the rollback backups; failed installs use
# the trap above to restore the previous source, env, unit and Caddy config.
CHANGED=0
echo "PASS: atomic staging upgrade; existing programs and auth retained."
