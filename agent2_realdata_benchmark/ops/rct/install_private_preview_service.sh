#!/usr/bin/env bash
# Install ONLY the synthetic IJCAI localhost preview in the current snapshot.
# Never use this tool for real students or the existing Caddy operator demo.
set -euo pipefail
umask 077

if [[ $# -ne 0 ]]; then
  echo "No arguments accepted. Run from the reviewed immutable snapshot." >&2
  exit 2
fi
if [[ "$(id -un)" != "davis" ]]; then
  echo "Run as the unprivileged davis user (not root)." >&2
  exit 2
fi

BENCHMARK="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
SNAPSHOT="$(cd -- "$BENCHMARK/.." && pwd -P)"
case "$SNAPSHOT" in
  /home/davis/ijcai_preview_*) ;;
  *)
    echo "Refusing unexpected preview snapshot location: $SNAPSHOT" >&2
    exit 2
    ;;
esac
for required in \
  "$BENCHMARK/scripts/pilot_local_browser_preview.py" \
  "$BENCHMARK/scripts/pilot_private_vps_smoke.py" \
  "$BENCHMARK/docs/rct_candidate_v1/items.csv" \
  "$BENCHMARK/docs/rct_candidate_v1/resources.csv"; do
  if [[ ! -f "$required" || -L "$required" ]]; then
    echo "Missing or symlinked preview source file: $required" >&2
    exit 2
  fi
done

# Use a venv contained in this snapshot if available. Reusing the prior
# known-working venv is optional; no global Python packages are installed.
PY="${IJCAI_PREVIEW_PY:-$SNAPSHOT/.venv/bin/python}"
if [[ ! -x "$PY" && -z "${IJCAI_PREVIEW_PY:-}" &&
      -x /home/davis/ijcai_preview_5c6bb17/.venv/bin/python ]]; then
  PY=/home/davis/ijcai_preview_5c6bb17/.venv/bin/python
fi
if [[ ! -x "$PY" ]]; then
  echo "No usable virtualenv Python: set IJCAI_PREVIEW_PY explicitly." >&2
  exit 2
fi
"$PY" -c 'import flask, werkzeug; from src.prototype.pilot_local_browser_preview import create_fictional_preview_app' \
  || { echo "Preview dependencies/source import failed." >&2; exit 2; }

STATE="$SNAPSHOT/state"
DB="$STATE/fictional_browser_preview.sqlite3"
UNIT=ijcai-pilot-private-preview.service
if [[ -L "$STATE" || -L "$DB" ]]; then
  echo "Refusing symlinked synthetic state." >&2
  exit 2
fi
if systemctl cat "$UNIT" >/dev/null 2>&1; then
  echo "Unit already installed. Inspect/review it before a manual update." >&2
  exit 2
fi
if ss -ltn '( sport = :8766 )' | awk 'NR > 1 { found=1 } END {exit !found}'; then
  echo "Port 8766 already in use: stop the former preview before installing." >&2
  exit 2
fi
install -d -m 0700 "$STATE"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
cat > "$TMP" <<EOF
# Synthetic, unapproved, SSH-tunnel-only. Never use for human enrollment.
[Unit]
Description=IJCAI fictional pilot browser preview (no human enrollment)
After=network.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=davis
Group=davis
WorkingDirectory=$BENCHMARK
ExecStart=$PY -m scripts.pilot_local_browser_preview --port 8766 --db $DB
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONUNBUFFERED=1
UMask=0077
Restart=on-failure
RestartSec=5
TimeoutStopSec=15
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$STATE
RestrictAddressFamilies=AF_INET AF_UNIX
IPAddressDeny=any
IPAddressAllow=localhost
RestrictSUIDSGID=true
LockPersonality=true
SystemCallArchitectures=native
LimitNOFILE=4096
TasksMax=64
MemoryMax=512M
CPUQuota=100%

[Install]
WantedBy=multi-user.target
EOF

echo "Installing synthetic-only service for $SNAPSHOT"
sudo install -o root -g root -m 0644 "$TMP" "/etc/systemd/system/$UNIT"
sudo systemctl daemon-reload
sudo systemctl enable --now "$UNIT"
if ! sudo systemctl is-active --quiet "$UNIT"; then
  echo "Service did not start; inspect journalctl before retrying." >&2
  exit 2
fi

# Same isolated, fail-closed loopback-only HTTP acceptance as CI.
cd "$BENCHMARK"
if ! "$PY" -m scripts.pilot_private_vps_smoke --base http://127.0.0.1:8766; then
  echo "Private preview smoke test failed; stopping the new service." >&2
  sudo systemctl disable --now "$UNIT"
  exit 2
fi
sudo ss -lntp '( sport = :8766 )'
echo "PASS: synthetic-only preview active on localhost:8766."
echo "Only connect through SSH -L 127.0.0.1:8766:127.0.0.1:8766."
