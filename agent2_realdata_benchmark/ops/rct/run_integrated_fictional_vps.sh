#!/usr/bin/env bash
# Operator-initiated OFFLINE synthetic-only VPS acceptance.
# Does not serve HTTP, contact students, modify Caddy, or use the 8766 service.
set -euo pipefail
umask 077

if [[ $# -ne 0 || "$(id -un)" != "davis" ]]; then
  echo "Run as davis with no arguments, from an isolated VPS snapshot." >&2
  exit 2
fi

BENCHMARK="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
SNAPSHOT="$(cd -- "$BENCHMARK/.." && pwd -P)"
if [[ ! "$SNAPSHOT" =~ ^/home/davis/ijcai_integrated_vps_[a-zA-Z0-9_-]+$ ]]; then
  echo "Refusing a non-isolated snapshot: $SNAPSHOT" >&2
  exit 2
fi

for required in \
  "$BENCHMARK/scripts/pilot_integrated_synthetic_journey.py" \
  "$BENCHMARK/src/prototype/pilot_admission_controls_draft.py" \
  "$BENCHMARK/src/prototype/pilot_three_arm_store_draft.py" \
  "$BENCHMARK/docs/rct_candidate_v1/items.csv" \
  "$BENCHMARK/docs/rct_candidate_v1/resources.csv"; do
  if [[ ! -f "$required" || -L "$required" ]]; then
    echo "Missing or linked synthetic fixture: $required" >&2
    exit 2
  fi
done

PY="${IJCAI_VPS_PY:-/home/davis/ijcai_preview_5c6bb17/.venv/bin/python}"
if [[ ! "$PY" =~ ^/[a-zA-Z0-9_./-]+$ || ! -x "$PY" ]]; then
  echo "Verified absolute virtualenv interpreter required." >&2
  exit 2
fi
if ! command -v timeout >/dev/null || ! command -v nice >/dev/null; then
  echo "Ubuntu coreutils timeout and nice are required." >&2
  exit 2
fi

REPORTS="$SNAPSHOT/reports"
if [[ -L "$REPORTS" ]]; then
  echo "Refusing symlink report directory." >&2
  exit 2
fi
install -d -m 0700 "$REPORTS"
OUTPUT="$(mktemp "$REPORTS/.fictional-run.XXXXXXXX")"
trap 'rm -f -- "$OUTPUT"' EXIT

cd "$BENCHMARK"
"$PY" -c 'from scripts.pilot_integrated_synthetic_journey import run_integrated' \
  || { echo "Synthetic runner import failed." >&2; exit 2; }

# A one-shot, low-priority disposable acceptance. 30 participants, 41 POMCP
# simulations. It is not a background service or a human study. Do not
# replace this CLI with a listening HTTP application.
if ! timeout --signal=TERM --kill-after=15s 1800s \
    nice -n 10 "$PY" -m scripts.pilot_integrated_synthetic_journey \
      --participants 30 --simulations 41 > "$OUTPUT"; then
  echo "Isolated fictional rehearsal failed; see local diagnostics." >&2
  exit 2
fi

"$PY" - "$OUTPUT" <<'PY'
import json
from pathlib import Path
import sys

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = {
    "kind": "DISPOSABLE_SYNTHETIC_ADMISSION_LEARNING_CROSSCHECK",
    "result": "PASS_SYNTHETIC_ONLY",
    "fictional_participants": 30,
    "fictional_completed_visits": 90,
    "fictional_questions": 2610,
    "fictional_mvas_records": 180,
    "admission_audit": "PASS_SYNTHETIC_ONLY",
    "learning_audit": "PASS_SYNTHETIC_ONLY",
    "no_client_supplied_arm": True,
    "no_network_requests": True,
    "temporary_stores_deleted": True,
    "human_enrollment_authorized": False,
    "staff_authentication_real": False,
    "consent_or_measurement_validated": False,
    "cross_database_atomicity": False,
    "independent_security_or_ethics_approval": False,
}
for key, value in expected.items():
    if data.get(key) != value:
        raise SystemExit("VPS synthetic acceptance invariant failed: " + key)
arms = data.get("allocated_by_arm", {})
if (set(arms) != {"A", "B", "C"}
        or any(type(n) is not int or n < 1 for n in arms.values())
        or sum(arms.values()) != 30
        or max(arms.values()) - min(arms.values()) > 3):
    # 30 may end partway through a randomly sized block of 6 or 9.
    # The resulting counts need not be exactly 10/10/10.
    raise SystemExit("VPS synthetic allocation exceeded block-balance bound")
if not isinstance(data.get("fictional_replay_checks"), int) or data["fictional_replay_checks"] < 30:
    raise SystemExit("VPS synthetic replay coverage is incomplete")
PY

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
# Never overwrite a prior acceptance report.
DEST="$REPORTS/fictional_30x3_41_${STAMP}_${RANDOM}.json"
if [[ -e "$DEST" || -L "$DEST" ]]; then
  echo "Refusing to replace an acceptance report." >&2
  exit 2
fi
mv -- "$OUTPUT" "$DEST"
chmod 0600 "$DEST"
echo "PASS: disposable 30-person / 90-visit synthetic VPS acceptance."
echo "Private aggregate report: $DEST"
cat -- "$DEST"
