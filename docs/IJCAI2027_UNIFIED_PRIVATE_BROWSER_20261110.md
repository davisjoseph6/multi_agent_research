# IJCAI 2027 · unified fictional browser VPS runbook

**Engineering staging only. Human enrollment remains disabled.**
This software may be accessed through **private SSH port forwarding only**.
Do not configure a public DNS endpoint, public Caddy/Nginx site, ingress
rule, TLS listener, or real-student credentials for this fictional app.

## Architecture

The earlier 127.0.0.1:8766 fictional browser service is preserved.

This branch adds a separate, **private port 8767** Flask preview that
connects to `UnifiedSyntheticStudyStore`, the newer single-SQLite-file
fictional admission/learning engine. It seeds exactly nine randomly
assigned synthetic, eligibility-flagged, fictitiously consented records.
The demo displays three aliases F1/F2/F3 representing one sample from
each treatment arm, but never exposes the concealed arm, admission ID,
learner ID, bearer token or private assessment answer through the status
endpoint. The public-facing browser does not choose A/B/C.

Each displayed fixture begins Visit 1 at a fixed virtual timestamp.
Its draft learning events, crash/retry submissions, attendance starts
and attendance finishes are persisted in one SQLite file. The browser
has only status, next-action, rendered, response and static asset routes.
No enrollment, real consent, attendance override, assignment reveal,
withdrawal or staff-management route exists. The offline CLI alone
advances or finishes a virtual supervised visit.

The synthetic admission/learning transition has atomic SQLite writes
within the single-file store, with unit regression tests for rollback.
The actual action store's own SQLite transaction gives durable repeated
submissions. The UI does NOT implement an authenticated study protocol
or production authorization.

## WSL: inspect and test latest branch

```bash
cd ~/multi_agent_research
git fetch origin
git worktree add --detach ../ijcai_unified_browser_review_20261110 \
  origin/research/ijcai2027-unified-browser-fictional-20261110

cd ~/ijcai_unified_browser_review_20261110/agent2_realdata_benchmark
PY="$HOME/ijcai_http_acceptance_20261110/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q \
  tests/test_pilot_unified_fictional_browser.py \
  tests/test_pilot_unified_private_smoke.py \
  tests/test_pilot_unified_sqlite_synthetic.py \
  tests/test_pilot_unified_sqlite_rehearsal.py
```

These checks execute real virtual learning activities, test all
three blinded fixture aliases, verify HTTP request restrictions,
restart nonce invalidation and one complete three-visit fictional
browser journey. Verify the commit and a clean worktree before
shipping.

## WSL: copy to a NEW VPS directory (do not touch 8766)

```bash
cd ~/ijcai_unified_browser_review_20261110
test -z "$(git status --porcelain)" || { echo DIRTY; exit 1; }
git rev-parse --short HEAD
VPS="<your-existing-VPS-host>"
ssh -i ~/.ssh/ijcai_preview_ed25519 "davis@$VPS" \
  'mkdir -p ~/ijcai_unified_browser_20261110'
set -o pipefail
git archive --format=tar HEAD agent2_realdata_benchmark docs | \
  ssh -i ~/.ssh/ijcai_preview_ed25519 "davis@$VPS" \
    'tar -xf - -C ~/ijcai_unified_browser_20261110'
```

Do not archive a virtualenv, home directory, local study data,
any SSH key, or a pre-existing confidential application database.

## On VPS: test and install the NEW separate service

In the existing `davis@ubuntu` SSH shell:

```bash
cd ~/ijcai_unified_browser_20261110/agent2_realdata_benchmark
PY="$HOME/ijcai_preview_5c6bb17/.venv/bin/python"
test -x "$PY" || { echo "Missing verified Python virtualenv"; exit 1; }
"$PY" -m pytest -q \
  tests/test_pilot_unified_fictional_browser.py \
  tests/test_pilot_unified_private_smoke.py \
  tests/test_pilot_unified_sqlite_synthetic.py

bash -n ops/rct/install_unified_fictional_browser.sh
bash ops/rct/install_unified_fictional_browser.sh
```

The installer is fail-closed if a service with the same name exists,
if port 8767 is occupied, if source files are missing/symlinked, or if
the snapshot is outside the expected `/home/davis/ijcai_unified_browser_*`
directory namespace. It creates a restricted synthetic-state folder,
a root-owned systemd unit with service hardening and restart-on-failure,
binds localhost only and performs a read-only HTTP acceptance check.
It does not change the original preview or public firewall.

Confirm on the VPS:

```bash
sudo systemctl is-active ijcai-unified-fictional-browser
sudo ss -lntp '( sport = :8767 )'
"$PY" -m scripts.pilot_unified_private_smoke \
  --base http://127.0.0.1:8767
sudo systemctl is-active ijcai-pilot-private-preview
```

The only accepted listener for the new service is **127.0.0.1:8767**.
Do not proceed if it binds `0.0.0.0:8767` or to the public VPS IP.

## WSL: open a separate SSH tunnel

Leave the working 8766 tunnel unchanged; in a separate terminal:

```bash
VPS="<your-existing-VPS-host>"
ssh -i ~/.ssh/ijcai_preview_ed25519 \
  -o PreferredAuthentications=publickey \
  -o PasswordAuthentication=no \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -N -L 127.0.0.1:8767:127.0.0.1:8767 "davis@$VPS"
```

Open `http://127.0.0.1:8767/` in the Windows/WSL browser.

## Offline fictitious session control

The web browser **cannot** start or finalize attendance. On the VPS
operator shell after the chosen fictional fixture finishes Visit 1 or 2:

```bash
cd ~/ijcai_unified_browser_20261110/agent2_realdata_benchmark
PY="$HOME/ijcai_preview_5c6bb17/.venv/bin/python"
"$PY" -m scripts.pilot_unified_fictional_browser \
  --db "$HOME/ijcai_unified_browser_20261110/state/fictional_admission.sqlite3" \
  --advance-fixture F1
```

Repeat after Visit 2 to open Visit 3. After Visit 3 is complete:

```bash
"$PY" -m scripts.pilot_unified_fictional_browser \
  --db "$HOME/ijcai_unified_browser_20261110/state/fictional_admission.sqlite3" \
  --finish-fixture F1
```

Replace F1 with F2 or F3 as needed. Refresh the browser. These
operators manipulate virtual time and **do not authenticate actual
supervisors** or represent real student attendance.

## Remaining release controls

The fictional preview is a functional **integrated UI**, not a
production participant service. Production still requires real
institutionally reviewed student eligibility, consent and withdrawal,
an authenticated staff identity provider, MFA/RBAC/revocation, separate
per-participant credentials, privacy controller/DPO-approved retention
and deletion, hardened HTTPS ingress, data-protection review,
approved instructional content and fatigue instrument, statistical
power/protocol signoff, independently reviewed security and
accessibility, and realistic load/device/backup/restore validation.

CI passing, SSH-private access, and synthetic load tests do not supply
those missing requirements. Do not open human enrollment.
