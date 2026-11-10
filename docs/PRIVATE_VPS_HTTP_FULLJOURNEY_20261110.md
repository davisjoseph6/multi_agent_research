# Private VPS: disposable HTTP full-journey acceptance

**Scope:** Synthetic-only engineering test. Does not enroll, consent, identify,
recruit, or randomize real participants. Does not authorize a human study.

The newest branch builds on `research/ijcai2027-private-vps-operational-hardening-20261110`
rather than changing the original Caddy-backed operator demo.

## Terminal disconnect and SSH tunnel diagnosis

The original interactive Werkzeug process terminated or stopped listening
following a broken SSH session. `channel ... connect failed: Connection
refused` means SSH forwarding reached the VPS but the VPS port was not
accepting connections; this is distinct from an SSH login failure.

Before restarting any application, SSH into the VPS, then inspect:

```bash
sudo ss -lntp | grep ':8766' || true
systemctl status ijcai-pilot-private-preview --no-pager || true
```

If the private systemd service is already installed, use:

```bash
sudo systemctl restart ijcai-pilot-private-preview
sudo systemctl is-active ijcai-pilot-private-preview
sudo journalctl -u ijcai-pilot-private-preview -n 30 --no-pager
```

If not installed, first review the service template and the instructions in
`docs/PRIVATE_VPS_PILOT_OPERATIONS_20261110.md`. Install it only after
the new branch's source files have been transferred to the same isolated
snapshot and its dependencies verified. Do **not** concurrently run the
interactive preview and systemd on the same database or port. Never proxy
the preview publicly.

## Run a completely isolated HTTP-level acceptance

Run this in a **new checked-out snapshot** of this branch on WSL or the VPS
from `agent2_realdata_benchmark/`. It does not depend on the VPS's existing
preview listener, database or Caddy configuration.

```bash
PY="$HOME/ijcai_preview_5c6bb17/.venv/bin/python"
"$PY" -m pytest -q \
  tests/test_pilot_private_vps_smoke.py \
  tests/test_pilot_disposable_http_fulljourney.py
"$PY" -m scripts.pilot_disposable_http_fulljourney
```

Choose a different `PY` path if the virtual environment is elsewhere.
The runner uses temporary SQLite data, selects a free loopback port, and
starts a separate real HTTP server within the same OS process. It performs:

1. Private HTTP smoke check for expected security headers, A/B/C status,
   absent enrollment routes, and missing nonce/origin rejection.
2. A/B/C `next` → `rendered` → `act` cycles, with
   identical-response retry checks and server-owned fictional visit advances.
3. Each arm's 16-question pretest, 55 practice questions, 16-question
   posttest, six proposed M-VAS values and bounded Arm A-only recovery.
4. An independent read-only SQLite audit requiring three completed visits
   for each fictional arm, valid response/event accounting and DB integrity.

Expected CLI result: `PASS_SYNTHETIC_ONLY` and nine finished synthetic
visits. This is a **test expectation**, not a claim of a VPS run that has
already passed. No host deployment or systemd installation occurs from
this script.

The test uses actual loopback HTTP but **not** an external browser,
HTTPS reverse proxy, randomized human subjects, independent audits,
concurrent genuine network clients or a production WSGI service.


## Deploy a persistent private VPS preview from an immutable source snapshot

These commands are deliberate *operator actions* and have **not** been executed
by the GitHub connector. Do not paste private SSH key contents into a command,
do not open TCP/8766 on the public firewall, and keep the old operator demo
untouched.

On WSL (in the new engineering worktree, not the original repository):

```bash
cd ~/ijcai_http_acceptance_20261110
git fetch origin
git switch --detach origin/research/ijcai2027-private-vps-http-fulljourney-20261110
test -z "$(git status --porcelain)" || { echo "Dirty worktree"; exit 1; }
test -f agent2_realdata_benchmark/ops/rct/install_private_preview_service.sh
ssh -i ~/.ssh/ijcai_preview_ed25519 davis@31.70.172.140 \
  'mkdir -p ~/ijcai_preview_http_20261110'
git archive --format=tar HEAD agent2_realdata_benchmark docs | \
  ssh -i ~/.ssh/ijcai_preview_ed25519 davis@31.70.172.140 \
    'tar -xf - -C ~/ijcai_preview_http_20261110'
```

On the VPS SSH terminal (the user `davis`):

```bash
cd ~/ijcai_preview_http_20261110/agent2_realdata_benchmark
PY="$HOME/ijcai_preview_5c6bb17/.venv/bin/python"
test -x "$PY" || { echo "Previous venv not available"; exit 1; }
"$PY" -m pytest -q \
  tests/test_pilot_private_vps_smoke.py \
  tests/test_pilot_disposable_http_fulljourney.py
bash -n ops/rct/install_private_preview_service.sh
bash ops/rct/install_private_preview_service.sh
```

The installer derives the checked-out snapshot path, refuses an existing
`ijcai-pilot-private-preview.service`, refuses a busy port, uses a virtualenv
rather than system Python, creates a private synthetic state directory, installs
a root-owned restricted systemd unit, enables restart-on-failure, and checks
local HTTP response guards with a read-only smoke test. It does **not**
rewrite Caddy or publish the service.

If a service with the same name already exists, halt and inspect it manually;
do not overwrite it silently. If the installer cannot find its dependencies,
set `IJCAI_PREVIEW_PY` to the existing verified interpreter path before
rerunning. Only use this installer for synthetic fixtures in the isolated
`ijcai_preview_*` directory namespace.

To check without exposing the service:

```bash
sudo systemctl is-active ijcai-pilot-private-preview
sudo ss -lntp '( sport = :8766 )'
"$PY" -m scripts.pilot_private_vps_smoke --base http://127.0.0.1:8766
```

A successful result is local-only HTTP and a listener at
`127.0.0.1:8766`; it is never a human-study launch decision.

## Release controls still closed

This addition only validates the existing fictional preview's HTTP behavior
and audit integration. Student eligibility/consent, concealed randomization,
staff identity and session supervision, real-calendar scheduling,
approved measurement/content, independent security/accessibility evaluation,
PI/statistician review, privacy/ethics authorization and production load
testing remain separate no-go criteria.

In particular, do **not** treat `PASS_SYNTHETIC_ONLY` as permission to
expose the preview to students or to remove the human-enrollment gate.
