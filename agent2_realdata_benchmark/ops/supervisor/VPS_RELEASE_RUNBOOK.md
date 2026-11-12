# Supervisor parallel-study /study/ — separate IONOS deployment

**Status:** Engineering staging candidate, **not yet a released study.** This
installs a real persistent, HTTPS-routed study application with invitation,
consent, screening, authenticated cookie, server-side grading, all A/B/C
policies, three sessions, survey, debrief and withdrawal; TEST enrollment is
restricted to `@example.example` contacts. No live emails, humans or student
recruitment are authorized. The source content is still marked DRAFT.

The VPS already runs Caddy at `demo.selfhealing-edu.fr` and the unrelated
operator demonstration (Gunicorn on `127.0.0.1:8077`). Do not overwrite its
service, SQLite database, Caddy basic-auth configuration or credentials.
The supervisor staging application listens **only** on
`127.0.0.1:8788`, state is under `/var/lib/ijcai-supervisor-staging`,
and Caddy proxies `/study/` under its existing Basic Auth.

## 1. Release acceptance on GitHub and WSL

The supervisor workflow checks the exact 465 reference trace rows, core
regressions and real Chromium browser journeys for the original fictional
browser and the new operational API. The self-contained RCT workflow omits
the genuine ASSIST2009 splits and external NeuralCD reference fixture;
do not describe that exclusion as a full all-data benchmark.

Run locally in an isolated WSL worktree:

```bash
cd ~/ijcai_gdpr_recovery_demo
git fetch origin
git status --short
git switch --detach origin/research/ijcai2027-supervisor-consent-gdpr-20261112
cd agent2_realdata_benchmark
source ~/ijcai_v2_validation/agent2_realdata_benchmark/.venv/bin/activate
python -m pytest -q tests/test_supervisor_vps_staging.py tests/test_supervisor_vps_scheduler.py
python -m pytest -q --ignore=tests/test_assist2009_splits.py -k 'not test_reference_forward_equivalence'
node --check src/prototype/static/supervisor_vps.js
bash -n ops/supervisor/install_staging.sh
```

## 2. Upload this exact commit from WSL; no private credentials in Git

On your Windows 11 / WSL workstation, using your existing key-only VPS
SSH configuration:

```bash
cd ~/ijcai_gdpr_recovery_demo
SHA="$(git rev-parse HEAD)"
UPLOAD="/home/davis/ijcai_supervisor_upload_${SHA:0:12}"
SSH="davis@31.70.172.140"
KEY="$HOME/.ssh/ijcai_preview_ed25519"

ssh -i "$KEY" "$SSH" "mkdir -p '$UPLOAD' && chmod 700 '$UPLOAD'"
git archive --format=tar "$SHA" | ssh -i "$KEY" "$SSH" "tar -xf - -C '$UPLOAD'"
printf '%s\n' "$SHA" | ssh -i "$KEY" "$SSH" "cat > '$UPLOAD/.supervisor-source-revision'"
ssh -t -i "$KEY" "$SSH" "sudo env SUPERVISOR_UPLOAD='$UPLOAD' bash '$UPLOAD/agent2_realdata_benchmark/ops/supervisor/install_staging.sh'"
```

This requires `sudo` on the VPS and an existing Caddyfile matching the
previously checked operator-demo layout. If the installer does not recognize
that layout, it **fails without rewriting the unknown proxy**. The installer
validates the Caddy configuration and restores its dated backup on failure.
It never alters the demo on port 8077.

## 3. Verify (without exposing any real participant)

```bash
ssh -i "$KEY" "$SSH" 'sudo systemctl status ijcai-supervisor-staging --no-pager'
ssh -i "$KEY" "$SSH" 'sudo ss -ltnp | grep 127.0.0.1:8788'
curl -i https://demo.selfhealing-edu.fr/study/
```

With no Basic Auth credentials, the public request **should return 401**.
After entering your *existing* operator credentials in your browser, the
`https://demo.selfhealing-edu.fr/study/` page should load. Do not remove
the existing Basic Auth layer for staging.

## 4. Generate one restricted staging invitation, offline

Run this **on the VPS**, as the dedicated service user:

```bash
sudo -u ijcai-supervisor bash -c '
  set -a
  source /etc/ijcai-supervisor-staging/staging.env
  set +a
  cd /srv/ijcai-supervisor-staging/current/agent2_realdata_benchmark
  /srv/ijcai-supervisor-staging/venv/bin/python -m scripts.supervisor_vps_admin \
     --issue researcher@example.example \
     --output /var/lib/ijcai-supervisor-staging/invite-local.txt
'
```

The secret invitation URL is saved to a new file with `0600` permissions,
not Git, terminal history or the service logs. Read it only on your
trusted machine:

```bash
sudo cat /var/lib/ijcai-supervisor-staging/invite-local.txt
```

Do not paste a live secret invitation link into a support request or public
issue. The test address is intentionally non-deliverable. A TEST participant
may now complete the actual VPS-served consent, screening and first session
under that invite; the database survives application and VPS restarts.

## 5. Operations, security and known blockers

- Caddy terminates HTTPS and preserves existing Basic Auth, which includes
  `/study/*`. The local Gunicorn server must not bind `0.0.0.0`.
- Staff invitation issuing, private contact handling, points exports,
  scheduling and attendance management are OFFLINE operations, not public
  administration routes.
- The new store has separate research and contact SQLite files, hashed
  invitation/session secrets, persistent evidence of rendered questions,
  single-use response IDs, server-side randomized/rotating arm allocation,
  and removal of all linked rows for approved erase requests.
- An hourly scheduler implementation maintains a private reminder outbox,
  retries failed SMTP and handles a second missed visit; it is **not
  enabled by the staging installer** because the PI has not finalized the
  session/grace-hours protocol. Once approved, configure an isolated timer
  using `scripts.supervisor_vps_daily`.
- Real SMTP requires an institutionally authorized sender and correctly
  configured STARTTLS credentials. TEST mode rejects `--send`.
- The separate signed evidence index provides a **structural** 14/14 check
  and an OpenSSL signature against an out-of-band verified institutional
  public key. Neither an editable JSON index nor a self-created key is
  ethics approval. LIVE startup is explicitly blocked while the currently
  shipped teaching content says DRAFT; no real students should be entered.
- Still required: approved bilingual materials, final six fatigue items
  and scoring, 20-vs-21 NN feature resolution, validated research outcomes,
  identity verification for email-based erasure, independent accessibility
  and penetration tests, production-grade encrypted/offsite backups with
  restore proof, operational load assessment, verified institutional
  signatures, and a PI/institutional GO decision. The original release
  evidence status was 0/14.
- A healthy service or passing fictional CI **does not** mean those
  independent human and institutional requirements have been completed.

## 6. How to stop only the new service

```bash
sudo systemctl stop ijcai-supervisor-staging
```

This leaves the original operator demonstration untouched. Never replace
its database with supervisor data or place study credentials in GitHub.
