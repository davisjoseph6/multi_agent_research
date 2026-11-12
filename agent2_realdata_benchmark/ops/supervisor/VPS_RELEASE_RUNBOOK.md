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

## Recovery: systemd status=200/CHDIR after first upload (12 Nov 2026)

The first installer version used `cp -a "$SOURCE/." "$RELEASE/"`.
Because the SSH upload directory was intentionally `0700`, GNU `cp -a`
also gave the **destination release root** mode `0700`. The dedicated
`ijcai-supervisor` service account cannot traverse it, so systemd failed
**before importing Python** with `status=200/CHDIR`. Installing Flask and
Gunicorn succeeded; this is neither an application traceback nor a sign that
the operator-demo service is broken.

**Preferred durable recovery:** Fetch the latest deployment-fix commit, use
the upload procedure in §2 to archive its *full new SHA* into a fresh
`/home/davis/ijcai_supervisor_upload_<sha>` directory, and run the new
`install_staging.sh` using sudo. The patched installer normalizes **only**
the deployed public-code release root to mode `0755`, checks directory
accessibility as `ijcai-supervisor`, and explicitly restarts the systemd
unit. It runs these checks even if a release directory already exists.
The service state under `/var/lib/ijcai-supervisor-staging` remains `0700`,
and secrets under `/etc/ijcai-supervisor-staging` remain group-restricted.
There is no need to delete the old release, disable the existing demo or
reset the SQLite databases.

For read-only diagnosis after deployment:

```bash
sudo namei -l /srv/ijcai-supervisor-staging/current/agent2_realdata_benchmark
sudo systemctl status ijcai-supervisor-staging --no-pager
sudo journalctl -u ijcai-supervisor-staging -n 35 --no-pager
sudo ss -ltnp | grep 127.0.0.1:8788
```

If the older source has **already** been copied to the VPS and you need to
repair it before updating, the following narrow recovery is safe as long as
`current` resolves under the expected release directory:

```bash
target="$(readlink -f /srv/ijcai-supervisor-staging/current)"
case "$target" in
  /srv/ijcai-supervisor-staging/releases/*) ;;
  *) echo "Unexpected release target: $target" >&2; exit 2 ;;
esac
sudo chmod 0755 "$target"
sudo -u ijcai-supervisor test -x \
  "$target/agent2_realdata_benchmark/scripts"
sudo systemctl restart ijcai-supervisor-staging
sudo systemctl is-active --quiet ijcai-supervisor-staging
```

That manual repair **does not finish public installation**: the original
installer exited **before** inserting and validating the Caddy `/study/`
reverse-proxy route. Re-run the **patched** installer to finish that step
and inspect the unauthenticated HTTPS response as required in §3. Do **not**
run `chmod -R 777`, relax `/var/lib` or `/etc` permissions, open port
8788 externally, or remove Caddy Basic Auth.

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

## 3a. Dedicated reviewer Basic Auth without sharing operator access

The initial Caddy Basic Auth may grant access to the unrelated operator
demonstration as well as `/study/`. Do **not** share the operator credentials
with the supervisor. After deploying the current code to staging, run on VPS:

```bash
sudo python3 /srv/ijcai-supervisor-staging/current/agent2_realdata_benchmark/ops/supervisor/setup_reviewer_auth.py
```

This tool requires the exact known Caddy layout, prompts invisibly for a
NEW 20+-character study reviewer password, and hashes it with Caddy bcrypt
via stdin (no plaintext command-line arguments). It separates the frontend
operator matcher from `/study` and `/study/*`, adding a dedicated reviewer
Basic Auth identity `studyreviewer` only to the study path. It validates and
reloads Caddy, then checks the following real HTTPS responses:

- Unauthenticated `/study/` — HTTP 401.
- `studyreviewer` credentials on `/study/` — HTTP 200.
- The same reviewer credentials at `/` — HTTP 401 (operator demo denied).

On failure it restores the original Caddyfile from a private backup and
reloads, leaving the study database, operator password, and 8077 unit alone.
The command refuses to modify unfamiliar Caddy configurations rather than
guessing. Review the intended access-policy change with the VPS operator.

Send the username and the newly chosen STUDY-ONLY password privately and
separately from the three already-issued fictional invitations. The groups
are assigned on eligible registration by A/B/C rotation; invite URLs do
not predetermine groups. Do not send SSH access or the unrelated researcher
dashboard password. Revoke reviewer access after the review as authorized.
Human recruitment and SMTP remain disabled.

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

## 4a. Replace a disclosed fictional invitation without deleting study progress

If a full `#invite=` URL was pasted into a chat or document, treat that
invitation as potentially disclosed even though the site also requires Caddy
authentication. The *registered* participant's invitation is also their
HttpOnly-cookie credential: deleting only the invitation text file does **not**
invalidate the link or existing cookies. Do not share the link again.

The **offline-only** `--rotate-registered-test` command replaces the
registered `.example` credential in both private tables inside one
transaction. It preserves the participant reference, arm, consent, every
response, the ongoing quiz and the scheduled future sessions. The prior
link and all browser cookies become invalid. It creates a fresh mode-0600
output file first; a failed output preflight cannot lock out the learner.
Human identities cannot use this staging command.

After upgrading the VPS to the commit containing this change, run:

```bash
ssh -tt -i "$HOME/.ssh/ijcai_preview_ed25519" davis@31.70.172.140
sudo -u ijcai-supervisor bash -c '
  set -a
  source /etc/ijcai-supervisor-staging/staging.env
  set +a
  cd /srv/ijcai-supervisor-staging/current/agent2_realdata_benchmark
  /srv/ijcai-supervisor-staging/venv/bin/python -m scripts.supervisor_vps_admin \
    --rotate-registered-test researcher@example.example \
    --output /var/lib/ijcai-supervisor-staging/invite-rotated-01.txt
'
sudo cat /var/lib/ijcai-supervisor-staging/invite-rotated-01.txt
```

Read the new link only on your trusted workstation; never paste it into
a chat or code repository. Open it in a *new private browser window*,
pass Caddy Basic Auth, and verify `WAITING_NEXT_SESSION` and the unchanged
next-session date. The old invitation must now fail; do not test or print
the old secret URL unnecessarily. Old tabs are expected to show
"invitation not found" until reauthenticated with the new link.

If the original participant withdrew or was erased, **do not use rotation**:
the correct procedure is to issue a new fictional invitation, creating a
separate participant record. Use a new filename each time; existing files
are never overwritten.

## 4b. Independent researcher monitoring: private live BKT line chart

The **researcher dashboard is not a participant page**. It uses a second,
read-only Flask service, an independent researcher password, and a per-user
encrypted SSH tunnel. It never attaches the contacts/PII database, returns
only `STUDY_Pnnn` pseudonyms, and has GET-only endpoints. Its Y axis is
estimated BKT mastery **probability**, not directly observed knowledge.
Its X axis is successive *scored* quiz/recovery responses. All eight
concepts C1..C8 are displayed as separate lines and fetched every 5 seconds.
Researchers can view the assigned arm, session, and timestamps, but must
not use these observations to change the randomized study treatment.

After deploying a source commit containing this feature on the staging VPS,
from the **remote SSH terminal**, opt in explicitly:

```bash
sudo bash /srv/ijcai-supervisor-staging/current/agent2_realdata_benchmark/ops/supervisor/enable_researcher_dashboard.sh
sudo systemctl status ijcai-supervisor-researcher --no-pager
```

The installer prompts twice for a separate researcher password, stores **only
its salted PBKDF2-SHA256 hash** in a root-owned, service-readable `0640`
environment file, starts the second service on **127.0.0.1:8790**, and
asserts that an unauthenticated request gets **401 Unauthorized**. If a
researcher credential is already configured, the installer refuses to
overwrite it. No Caddy route is created and the participant invitation
service on port 8788 is left untouched.

From the authorized researcher's **local WSL terminal**, open a tunnel:

```bash
ssh -N -L 8790:127.0.0.1:8790 \
  -i "$HOME/.ssh/ijcai_preview_ed25519" davis@31.70.172.140
```

Then browse `http://127.0.0.1:8790/admin/`, sign in with user
`researcher` and the separate password, and select a pseudonymous student.
The password does not come from Caddy, and there must **never** be an
external `/admin/` Caddy route. SSH keys, research roles, and sharing the
password with independent researchers still need institutional IAM review.

Regression: `pytest -q tests/test_supervisor_research_monitor.py`;
real-Chromium polling: `node scripts/supervisor_research_monitor_playwright.cjs`.

## 4c. Domain-scoped AI points — versioned new consent

The **verified invitation's private email domain**, not user input on the
page, determines whether AI points apply. Every exact
`@aivancity.education` address (case-insensitive) continues to see the
sixth required declaration about 150 AI points, with unchanged `v1.0`
text. All other email domains omit that declaration and see **five**
required boxes, with a matching `v1.1-nonreward-DRAFT` information sheet
and debrief. The optional independent data-sharing checkbox remains.

The two consent versions are intentionally immutable. Existing recorded
`v1.0` consent and its stored timestamp are not rewritten. The
`v1.1` nonreward legal variant has been prepared in English and French,
but the *specific revised Annex wording* must be approved and its
bracketed contact/retention fields completed before enrollment. There
is no automatic grant of 150 points to other email domains. This change
is observational with respect to the A/B/C algorithm.

Regression: `pytest -q tests/test_supervisor_reward_consent.py`.
The original supervisor guide's fixed six-box rule is **superseded for
non-school invitations only if** the corresponding amendment is approved.

## 4d. Research-only neural evaluation after authorized sessions

Source modules:
`src/prototype/supervisor_operational_neural.py` and
`scripts/supervisor_operational_neural_cli.py`. No data is sent to
external inference APIs. The approved research analyst supplies:

- A pseudonymized `supervisor_operational_study.sqlite3` database.
- A **PI-signed** feature-contract JSON (schema
  `SUPERVISOR_NN_FEATURE_CONTRACT_V1`) listing exactly the 20 concrete
  features in the original document, with the real institutional data-use
  reference, reviewer and timezone-aware approval date; its public key and
  detached signature must be independently verified.
- An isolated research Python environment with PyTorch (not the live
  participant server). Optionally an exact event-aligned heldout DKT
  probability CSV, `event_id,probability_correct`.
- A new private report destination; individual event predictions and
  participant contact details are never included in the result file.

Example after authorized approval and real Session 1 completion:

```bash
python -m scripts.supervisor_operational_neural_cli \
  --research-db /institution/private/supervisor_operational_study.sqlite3 \
  --through-session 1 \
  --feature-approval /institution/private/pi_feature_approval.json \
  --signature /institution/private/pi_feature_approval.sig \
  --public-key /institution/private/pi_official_pubkey.pem \
  --epochs 8 \
  --output /institution/private/nn_bkt_session1.json
```

Repeat `--through-session 2` for the approved update after Session 2.
The evaluator uses BEFORE-question features, student-disjoint train/holdout
splits, ROC AUC and Brier scoring for NN and BKT, optional DKT. It blocks
insufficient subjects, single-class holdouts and mismatched DKT event IDs.
No production participant policy is changed by this offline evaluation.
**No scientific accuracy or intervention-improvement result can be claimed
until enough consented real observations exist.**

The original brief lists 20 concrete inputs but says `Input(21)` in
another line. The implementation **does not invent a 21st feature**; if
the supervisor truly approves 21, the feature list, vector, neural
architecture, training and tests must be revised as a new version.
Signatures are meaningful only if the public key is trusted and the PI's
approval is independently verified.

## 4e. Authenticated-encrypted operational study backups

Optional code is available for paired research/contact SQLite backups with
AES-256-GCM encryption, private binary key files, corruption detection and
**memory-only restore verification**. It does not store either plaintext
database in the backup directory. Encryption requires the Python
`cryptography` library in the *administrative backup environment*
(`python -m pip install cryptography`). It does **not** touch the study
service's pinned dependencies, and has not been deployed to the VPS yet.

**Safer guarded wrapper (preferred for a manual maintenance window):**
After installing a source revision containing `run_safe_encrypted_backup.sh`,
use the existing service-user-readable mode-0600 32-byte backup key and a
new unique encrypted output in an existing private mode-0700 directory:

```bash
sudo bash /srv/ijcai-supervisor-staging/current/agent2_realdata_benchmark/ops/supervisor/run_safe_encrypted_backup.sh \
  /var/lib/ijcai-supervisor-backup/key.bin \
  /var/lib/ijcai-supervisor-backup/backup-unique-YYYYMMDD.enc
```

The wrapper acquires a lock, requires the known staging service to be active,
stops it, creates and verifies the encrypted paired snapshot, and uses an
EXIT trap to restore service availability even if verification fails.
It never provisions keys or copies encrypted backups offsite. Arrange a
supervised quiet period beforehand. Independently confirm secure key custody,
offsite replication and a true external-host restore drill before real data.

For a controlled backup operation, the staff operator must first arrange
a quiet period (pausing recruitment/session access), arrange institutionally
approved secure backup-key custody and offsite storage, and create a new
private destination folder. The backup CLI **refuses** if systemd reports
the staging study service running. Example (on the VPS, privileged staff
only, after arranging authorization and key custody):

```bash
# One-time key creation; DO NOT regenerate a key for existing backups.
sudo install -d -m 0700 -o ijcai-supervisor -g ijcai-supervisor \
  /var/lib/ijcai-supervisor-backup
sudo -u ijcai-supervisor bash -c '
umask 077
head -c 32 /dev/urandom > /var/lib/ijcai-supervisor-backup/key.bin
'
# Stop the study service for a coherent paired research/contact snapshot.
sudo systemctl stop ijcai-supervisor-staging
sudo -u ijcai-supervisor bash -c '
cd /srv/ijcai-supervisor-staging/current/agent2_realdata_benchmark
/srv/ijcai-supervisor-staging/venv/bin/python \
  -m scripts.supervisor_operational_backup_cli \
  --create \
  --state-dir /var/lib/ijcai-supervisor-staging \
  --key-file /var/lib/ijcai-supervisor-backup/key.bin \
  --encrypted-file /var/lib/ijcai-supervisor-backup/dated-unique.enc
'
sudo systemctl start ijcai-supervisor-staging
```

Restore drill **without writing to the live databases**:

```bash
sudo -u ijcai-supervisor bash -c '
cd /srv/ijcai-supervisor-staging/current/agent2_realdata_benchmark
/srv/ijcai-supervisor-staging/venv/bin/python \
  -m scripts.supervisor_operational_backup_cli \
  --verify \
  --key-file /var/lib/ijcai-supervisor-backup/key.bin \
  --encrypted-file /var/lib/ijcai-supervisor-backup/dated-unique.enc
'
```

The operator must ensure the participant portal is restarted even after
failures (e.g. via a reviewed `trap` handler). A complete recovery plan
also needs an externally protected key copy, offsite encrypted replica,
scheduled/monitored execution, rotation and retention policies, successful
disaster-recovery drills on another host and GDPR backup erasure handling.
A successful local encrypted backup is **not** evidence that these
institutionally controlled operations have happened. The CLI never
restores or overwrites production files automatically.

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
