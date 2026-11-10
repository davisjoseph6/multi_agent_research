# VPS staging: disconnected integrated fictional pilot only

**Engineering runbook (10 Nov 2026). Human enrollment: FORBIDDEN.**

The currently functioning private VPS preview is an independent SSH-tunnel
HTTP service at 127.0.0.1:8766. **Do not stop, replace or change that
service**. This deployment is an offline, one-shot **batch rehearsal** of
30 fictional admissions and 90 full adaptive-learning visits. It neither
opens a new web port nor serves the combined application in a browser.

No real consent or screening is obtained. Staff credentials and scheduling
are virtual fixtures. The dual SQLite stores still lack cross-database
transactional atomicity and are deleted after execution. This cannot
be called an authorized human-study application.

## 1. Local WSL: clone a new immutable review snapshot

Use the already connected SSH identity; never paste a private key:

```bash
cd ~/multi_agent_research
git fetch origin
git worktree add --detach ../ijcai_vps_batch_20261110 \
  origin/research/ijcai2027-isolated-vps-batch-20261110
cd ../ijcai_vps_batch_20261110
test -z "$(git status --porcelain)" || { echo DIRTY; exit 1; }
git rev-parse --short HEAD

PY="$HOME/ijcai_http_acceptance_20261110/agent2_realdata_benchmark/.venv/bin/python"
cd agent2_realdata_benchmark
"$PY" -m pytest -q tests/test_pilot_integrated_vps_report_check.py \
  tests/test_pilot_integrated_synthetic_journey.py
cd ..
```

On WSL, replace `VPS_HOST` with the known existing VPS address (never
place real participant details, signed ethics documents or passwords here):

```bash
VPS_HOST="<your-existing-VPS-host>"
ssh -i ~/.ssh/ijcai_preview_ed25519 "davis@$VPS_HOST" \
  'mkdir -p ~/ijcai_integrated_vps_20261110'
set -o pipefail
git archive --format=tar HEAD agent2_realdata_benchmark docs | \
  ssh -i ~/.ssh/ijcai_preview_ed25519 "davis@$VPS_HOST" \
  'tar -xf - -C ~/ijcai_integrated_vps_20261110'
```

The source is copied to a **new directory**. Do not transfer the virtual
environment, original preview databases or any local/private fixture files.
Inspect the source SHA before transferring, and do not edit the resulting
snapshot during acceptance.

## 2. VPS SSH: run in isolation

```bash
cd ~/ijcai_integrated_vps_20261110/agent2_realdata_benchmark

PY="$HOME/ijcai_preview_5c6bb17/.venv/bin/python"
test -x "$PY" || { echo "Missing verified Python environment"; exit 1; }

"$PY" -m pytest -q \
  tests/test_pilot_integrated_vps_report_check.py \
  tests/test_pilot_integrated_synthetic_journey.py

bash -n ops/rct/run_integrated_fictional_vps.sh
bash ops/rct/run_integrated_fictional_vps.sh
```

The wrapper restricts the working directory to an isolated snapshot,
requires the `davis` account and pinned source files, runs at reduced CPU
scheduling priority with a maximum execution deadline, validates aggregate
success invariants and writes a permission-restricted JSON report under
`~/ijcai_integrated_vps_20261110/reports/`.

Reports contain **only fictional aggregates**; the 30 synthetic records,
their role-capability bytes and both SQLite databases are temporary.
Do not describe those as real test subjects, power study evidence or
production data.

The 30 simulated assignments do not always yield 10/10/10 exactly,
because assignment uses cryptographically shuffled blocks of six or nine
and a 30-person sample may stop partway through a block. The validator
therefore checks 30 total assignments, all three arms, a bounded count
difference and all required 90 visits/2,610 items/180 M-VAS values.

## 3. Confirm no changes to the original private preview

On the VPS:

```bash
sudo systemctl is-active ijcai-pilot-private-preview
sudo ss -lntp '( sport = :8766 )'
```

The listener should remain **only** 127.0.0.1:8766. On WSL through the
unchanged SSH tunnel, repeat:

```bash
cd ~/ijcai_http_acceptance_20261110/agent2_realdata_benchmark
./.venv/bin/python -m scripts.pilot_private_vps_smoke \
  --base http://127.0.0.1:8766
```

Require `"result": "PASS"` and 17 successful checks. A passing report
from this new batch is **not** proof of public HTTPS, human enrollment,
real attendance, authenticated staff, validated content or measurement,
single-transaction study consistency, production scaling or security
certification. Do not configure Caddy, Nginx, DNS or firewall ingress for
the batch; there is no new HTTP service to expose.

## Release decision

**YES:** isolated offline synthetic batch execution on VPS, once the
operator has transferred the source and VPS tests pass.

**NO:** combined public or student-facing hosting, research enrollment
and claim of full human-trial software completion. That requires an
appropriately engineered and independently verified human-study
application, real signoff and associated controls.
