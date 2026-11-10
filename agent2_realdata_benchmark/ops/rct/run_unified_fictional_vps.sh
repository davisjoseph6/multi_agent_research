#!/usr/bin/env bash
# Manual, offline, synthetic-only, SINGLE SQLITE FILE acceptance.
# No human study, no public service, no change to existing SSH-only preview.
set -euo pipefail
umask 077

if [[ $# -ne 0 || "$(id -un)" != "davis" ]]; then
  echo "Run as davis without arguments on reviewed private VPS snapshot." >&2
  exit 2
fi

BENCHMARK="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
SNAPSHOT="$(cd -- "$BENCHMARK/.." && pwd -P)"
if [[ ! "$SNAPSHOT" =~ ^/home/davis/ijcai_unified_vps_[a-zA-Z0-9_-]+$ ]]; then
  echo "Refusing non-isolated synthetic snapshot directory." >&2
  exit 2
fi
for source in \
  "$BENCHMARK/scripts/pilot_unified_sqlite_rehearsal.py" \
  "$BENCHMARK/scripts/pilot_unified_vps_report_check.py" \
  "$BENCHMARK/src/prototype/pilot_unified_sqlite_synthetic.py" \
  "$BENCHMARK/docs/rct_candidate_v1/items.csv" \
  "$BENCHMARK/docs/rct_candidate_v1/resources.csv"; do
  if [[ ! -f "$source" || -L "$source" ]]; then
    echo "Missing or symlinked source: $source" >&2
    exit 2
  fi
done

PY="${IJCAI_VPS_PY:-/home/davis/ijcai_preview_5c6bb17/.venv/bin/python}"
if [[ ! "$PY" =~ ^/[a-zA-Z0-9_./-]+$ || ! -x "$PY" ]]; then
  echo "Verified absolute virtualenv interpreter required." >&2
  exit 2
fi
command -v timeout >/dev/null && command -v nice >/dev/null || {
  echo "Required coreutils missing." >&2
  exit 2
}

REPORTS="$SNAPSHOT/reports"
if [[ -L "$REPORTS" ]]; then
  echo "Refusing symlinked output." >&2
  exit 2
fi
install -d -m 0700 "$REPORTS"
OUTPUT="$(mktemp "$REPORTS/.synthetic-unified.XXXXXXXX")"
trap 'rm -f -- "$OUTPUT"' EXIT

cd "$BENCHMARK"
"$PY" -c 'from scripts.pilot_unified_sqlite_rehearsal import run_unified' ||
  { echo "Cannot import isolated synthetic runner." >&2; exit 2; }

if ! timeout --signal=TERM --kill-after=15s 1800s \
    nice -n 10 "$PY" -m scripts.pilot_unified_sqlite_rehearsal \
       --participants 30 --simulations 41 > "$OUTPUT"; then
  echo "Single-file synthetic rehearsal failed." >&2
  exit 2
fi

"$PY" -m scripts.pilot_unified_vps_report_check --path "$OUTPUT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$REPORTS/unified_synthetic_30x3_${STAMP}_${RANDOM}.json"
if [[ -e "$DEST" || -L "$DEST" ]]; then
  echo "Refusing to replace an acceptance report." >&2
  exit 2
fi
mv -- "$OUTPUT" "$DEST"
chmod 0600 "$DEST"
echo "PASS: synthetic-only single-SQLite 30-person / 90-visit acceptance."
echo "Aggregate report: $DEST"
cat -- "$DEST"
