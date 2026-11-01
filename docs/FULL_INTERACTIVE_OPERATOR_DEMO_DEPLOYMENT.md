# Full interactive fictional research demo over HTTPS — operator only

**Status:** code and configuration templates, not deployed. No real RCT enrollment,
participant recruitment, real consent, validated LFS or efficacy claims.
The existing GitHub Pages static preview is a **different** site.

This deployment serves the actual Flask UI and V3-POMCP controller for **only
nine pre-enrolled fictional records**, using a separate fresh SQLite database.
The public API `/api/rct/enroll` refuses requests. The `live` release evidence
gate still blocks unapproved human RCT startup. Access is limited to operators
holding a separately issued Basic-auth webpage login **and** a private fictional
invitation. API actions use invitation bearer tokens. No actual student data.

## Preconditions — before starting

- Supervisor/institution authorizes this **restricted fictional demo** and its
  hosting. Do not imply approval of participant recruitment.
- Operator controls an Ubuntu 24.04 VPS in an appropriate location, DNS name
  `demo.YOUR_DOMAIN.fr`, VPS public IPv4, SSH account, firewall and billing.
- DNS A record for `demo` resolves to the VPS. TCP 80/443 can reach Caddy.
  SSH is restricted where feasible. **Never** expose TCP 8077 publicly.
- The VPS has no production RCT database, existing research records or personal
  information. Run content only under the fictional staging settings.
- Do not paste server passwords, invitation files or raw tokens into GitHub,
  recordings or this chat.

## 1. Fetch and test this distinct staging branch

From the developer workstation:
```bash
cd ~/multi_agent_research
git switch feature/rct-https-staging-20261101
git pull --ff-only
cd agent2_realdata_benchmark
python -m pytest -q tests/test_rct_operator_demo.py tests/test_rct_candidate.py
python -m pytest -q
```
**Do not proceed** if tests fail. A GitHub commit alone does not imply tests
passed on the target machine.

## 2. Create a least-privilege VPS service

SSH as the account issued by the VPS provider. Verify host fingerprint via
a trusted channel before the first connection. On Ubuntu:
```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y git python3 python3-venv ca-certificates curl
sudo useradd --system --home-dir /srv/ijcai-rct-demo --shell /usr/sbin/nologin ijcai-demo
sudo install -d -o ijcai-demo -g ijcai-demo -m 0750 /srv/ijcai-rct-demo
sudo install -d -o ijcai-demo -g ijcai-demo -m 0700 /var/lib/ijcai-rct-demo
sudo install -d -o root -g ijcai-demo -m 0750 /etc/ijcai-rct-demo
sudo -u ijcai-demo -H git clone --branch feature/rct-https-staging-20261101 \
  https://github.com/davisjoseph6/multi_agent_research.git \
  /srv/ijcai-rct-demo/repo
sudo -u ijcai-demo -H python3 -m venv /srv/ijcai-rct-demo/venv
sudo -u ijcai-demo -H /srv/ijcai-rct-demo/venv/bin/pip install \
  -r /srv/ijcai-rct-demo/repo/agent2_realdata_benchmark/requirements-prototype.txt \
  -r /srv/ijcai-rct-demo/repo/agent2_realdata_benchmark/ops/rct/requirements-serving.txt
```
These are version-constrained dependencies, **not production locked hashes**.
For an actual human RCT deployment, review and lock them separately.

## 3. Prepare fictional-only settings and seeded records

```bash
sudo -u ijcai-demo -H cp \
  /srv/ijcai-rct-demo/repo/agent2_realdata_benchmark/docs/rct_candidate_v1/settings_operator_demo_TEMPLATE.json \
  /srv/ijcai-rct-demo/repo/agent2_realdata_benchmark/docs/rct_candidate_v1/settings_operator_demo_LOCAL.json
```
Edit the single `allowed_hosts` placeholder in the LOCAL settings to the
**actual demo domain** using an editor with the service-account permissions.
Keep `mode: operator_demo`, `release_evidence: null`, and
`behind_one_local_tls_proxy: true`. The content paths in this file are
relative to its directory. The `fatigue` file remains the explicitly
unvalidated rehearsal fixture; the Lee Fatigue Scale is NOT included.

Run the following from the benchmark working directory:
```bash
cd /srv/ijcai-rct-demo/repo/agent2_realdata_benchmark
sudo -u ijcai-demo -H /srv/ijcai-rct-demo/venv/bin/python \
  -m scripts.rct_operator_demo \
  --settings docs/rct_candidate_v1/settings_operator_demo_LOCAL.json \
  --db /var/lib/ijcai-rct-demo/fictional.sqlite3 \
  --out /var/lib/ijcai-rct-demo/fictional_invites_PRIVATE.json
```
This creates only **nine fictional records** in randomized A/B/C allocation,
pre-enrolled internally to prevent public enrollment. The private JSON contains
invitation bearer credentials. File mode is 0600; never copy to the web root.
If the seed command fails, investigate before running it again; it never
overwrites an existing DB or invitation file.

## 4. Run Gunicorn, *loopback only*

Install the template
`agent2_realdata_benchmark/ops/rct/ijcai-rct-operator-demo.service.template`
as `/etc/systemd/system/ijcai-rct-operator-demo.service`.
**Adjust its WorkingDirectory** to:
`/srv/ijcai-rct-demo/repo/agent2_realdata_benchmark`
(its template has an intentionally different repository path).

Create `/etc/ijcai-rct-demo/demo.env` (mode 0640, owner root, group
`ijcai-demo`) containing:
```text
RCT_DEMO_SETTINGS=/srv/ijcai-rct-demo/repo/agent2_realdata_benchmark/docs/rct_candidate_v1/settings_operator_demo_LOCAL.json
RCT_DEMO_DATABASE=/var/lib/ijcai-rct-demo/fictional.sqlite3
```
Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ijcai-rct-operator-demo
sudo systemctl status ijcai-rct-operator-demo --no-pager
sudo ss -ltn | grep 8077
```
It **must** be bound to `127.0.0.1:8077`, not `0.0.0.0:8077`.

## 5. HTTPS and operator login with Caddy

Install Caddy from its **official** Ubuntu/Debian repository:
https://caddyserver.com/docs/install

Copy `ops/rct/Caddyfile.operator_demo.example` to
`/etc/caddy/Caddyfile`. Replace:
- `demo.example.fr` with the actual subdomain.
- `REPLACE_WITH_CADDY_HASH_PASSWORD` with a **secure Caddy password hash**
  generated with the local interactive `caddy hash-password` command.

Use an independent strong operator password, not the SSH passphrase or an
invitation token. The Caddyfile stores the **hash**, not the plaintext password.
Restrict access to the configuration directory as appropriate. Caddy handles
automatic ACME issuance when DNS and inbound TCP 80/443 are correct.

The Caddy rule applies Basic authentication to the page/static routes, **not**
the `/api/rct/*` requests, because those requests use a different Bearer
token in the same `Authorization` HTTP header. API requests require a valid
unguessable seeded invitation, and the server rejects HTTP enrollment.
This is restricted operator staging, **not security certification**. Consider
private-VPN or IP allowlisting as a further defense if institutional policy
requires it. Confirm the trusted proxy overwrites forwarded headers.

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl enable --now caddy
sudo systemctl reload caddy
```

## 6. External go/no-go verification

From a second network, without cookies/passwords:
```bash
curl -I https://demo.YOUR_DOMAIN.fr/
```
Expected **401** for unauthenticated page requests. In a new browser,
enter the operator Basic-auth credentials and then a **single fictional
invitation** from the private JSON. Verify that all pretest, adaptive practice
with recovery resources, surveys, posttest, and final completion work.
Verify all B/C controls are question-only; do not force POMCP resource choice.

Record checks for: issued HTTPS certificate and renewal, redirects from HTTP,
response headers, cross-origin rejection, no remote enrollment, unauthorized
and expired invitation rejection, repeat submissions, tab refresh/resume,
Firefox/Chromium/mobile browsers, disconnection/reconnect, database rollback
and a tested restore on a **fictional** copy. Record p95/p99 and error rates from
real network traffic, not just Flask test-client timings.

Keep passwords and invitation codes out of browser screencasts, URLs, access
logs, issue trackers and research reports. Never share public URLs as open
recruitment. Disable and destroy the fictional records after approved demo
retention expires.

## 7. Unchanged release boundary

The actual live RCT remains **NO-GO**: authentic ethics/institutional/privacy
authorization, approved instrument permissions and version, expert-approved
95 questions/32 resources, frozen protocol and SAP, validated spacing/retention
and independent WCAG/security review are still required. No operator-demo
records are human efficacy data. No LFS items or scoring have been reproduced.
