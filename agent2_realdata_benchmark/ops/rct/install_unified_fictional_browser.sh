#!/usr/bin/env bash
# Manual installation of an isolated FICTIONAL study preview only.
# No real enrollment, no Caddy, no public listener, no changes to port 8766.
set -euo pipefail
umask 077

if [[ $# -ne 0 || "$(id -un)" != "davis" ]]; then
  echo "Run as davis, with no arguments, in the reviewed preview snapshot." >&2
  exit 2
fi

BENCHMARK="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
SNAPSHOT="$(cd -- "$BENCHMARK/.." && pwd -P)"
if [[ ! "$SNAPSHOT" =~ ^/home/davis/ijcai_unified_browser_[a-zA-Z0-9_-]+$ ]]; then
  echo "Unrecognized fictional-browser snapshot location." >&2
  exit 2
fi

for required in \
  "$BENCHMARK/scripts/pilot_unified_fictional_browser.py" \
  "$BENCHMARK/scripts/pilot_unified_private_smoke.py" \
  "$BENCHMARK/src/prototype/pilot_unified_fictional_browser.py" \
  "$BENCHMARK/src/prototype/templates/pilot_unified_fictional_browser.html" \
  "$BENCHMARK/src/prototype/static/pilot_unified_fictional_browser.js" \
  "$BENCHMARK/docs/rct_candidate_v1/items.csv" \
  "$BENCHMARK/docs/rct_candidate_v1/resources.csv"; do
  if [[ ! -f "$required" || -L "$required" ]]; then
    echo "Missing or linked fictional source: $required" >&2
    exit 2
  fi
done

PY="${IJCAI_UNIFIED_PREVIEW_PY:-/home/davis/ijcai_preview_5c6bb17/.venv/bin/python}"
if [[ ! "$PY" =~ ^/[a-zA-Z0-9_./-]+$ || ! -x "$PY" ]]; then
  echo "A vetted virtualenv interpreter path is required." >&2
  exit 2
fi
cd "$BENCHMARK"
"$PY" -c 'import flask, werkzeug; from scripts.pilot_unified_fictional_browser import open_synthetic_study' \
  || { echo "Fictional unified preview cannot import dependencies." >&2; exit 2; }

UNIT="ijcai-unified-fictional-browser.service"
if systemctl cat "$UNIT" >/dev/null 2>&1; then
  echo "Service already installed; review before making changes." >&2
  exit 2
fi
if ss -ltn '( sport = :8767 )' | awk 'NR > 1 {found=1} END {exit !found}'; then
  echo "Port 8767 is already occupied; refusing parallel server." >&2
  exit 2
fi
STATE="$SNAPSHOT/state"
DB="$STATE/fictional_admission.sqlite3"
if [[ -L "$STATE" || -L "$DB" ]]; then
  echo "Refusing symlinked fictional state." >&2
  exit 2
fi
install -d -m 0700 "$STATE"
TMP="$(mktemp)"
trap 'rm -f -- "$TMP"' EXIT
cat > "$TMP" <<EOF
# Not authorized for humans. SSH tunnel only. Never expose through Caddy.
[Unit]
Description=IJCAI unified fictional browser (no human RCT)
After=network.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=davis
Group=davis
WorkingDirectory=$BENCHMARK
ExecStart=$PY -m scripts.pilot_unified_fictional_browser --port 8767 --db $DB
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

echo "Installing loopback-only synthetic browser on port 8767"
sudo install -o root -g root -m 0644 "$TMP" "/etc/systemd/system/$UNIT"
sudo systemctl daemon-reload
sudo systemctl enable --now "$UNIT"
if ! sudo systemctl is-active --quiet "$UNIT"; then
  echo "Service did not start. Inspect journalctl before retrying." >&2
  exit 2
fi
for attempt in 1 2 3 4 5 6 7 8; do
  if ss -ltn '( sport = :8767 )' | awk 'NR > 1 {found=1} END {exit !found}'; then
    break
  fi
  sleep 1
done

if ! "$PY" -m scripts.pilot_unified_private_smoke \
  --base http://127.0.0.1:8767; then
  echo "Synthetic browser acceptance failed; disabling new service." >&2
  sudo systemctl disable --now "$UNIT"
  exit 2
fi
sudo ss -lntp '( sport = :8767 )'
echo "PASS: private unified fictional browser at http://127.0.0.1:8767/"
echo "Human enrollment remains disabled. Connect with SSH -L, never public proxy."
