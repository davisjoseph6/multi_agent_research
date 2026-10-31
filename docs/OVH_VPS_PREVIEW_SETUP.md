# Deploy the static research preview on an OVHcloud VPS (no human RCT)

This procedure is for the standalone `docs/index.html` **scripted, synthetic public preview**.
It does not publish the actual Flask RCT app, enroll anyone, run POMCP, or demonstrate
production-ready human-subject research. Purchase/setup requires account owner action.

## 0. Local repository and evidence

Use the `feature/rct-https-staging-20261101` branch; execute:
```bash
git fetch origin feature/rct-https-staging-20261101
git branch --set-upstream-to=origin/feature/rct-https-staging-20261101
git pull --ff-only
cd agent2_realdata_benchmark
python -m scripts.rct_public_preview_check
python -m pytest -q
```

## 1. Buy only what is needed

Choose one VPS in an **actual French OVHcloud datacenter**, with Ubuntu 24.04 LTS,
public IPv4, and SSH-key authentication. VPS-1 is an initial rehearsal host,
not an accepted concurrent-participant capacity. Choose/verify a separate .fr domain
that is available for registration. Register it in your own name with truthful
contact details. Avoid suggesting institutional sponsorship in the hostname.
Copy only the public SSH key to the hosting dashboard; never a private key.
Check current billing commitment, VAT, renewal price and region before paying.

Local SSH key setup, **on your laptop** (do not replace an existing key):
```bash
if [ -e ~/.ssh/ijcai_preview_ed25519 ]; then
    echo "SSH key already exists; reuse or inspect it (do not overwrite)."
else
    ssh-keygen -t ed25519 -a 100 -f ~/.ssh/ijcai_preview_ed25519 -C ijcai-static-preview
fi
cat ~/.ssh/ijcai_preview_ed25519.pub
```
The `.pub` line is what goes into the hosting dashboard. Do not share the
private key. Your VPS control panel provides the actual public IPv4 address
and the login user (possibly `ubuntu` or `root` depending on the image).

## 2. Configure a preview subdomain

In the domain's authoritative DNS zone, create a record:

| Record | Name | Type | Value |
|---|---|---|---|
| subdomain | `preview` | `A` | **Your VPS public IPv4, from its dashboard** |

Do not create an AAAA record unless an IPv6 address is actually assigned
and the server/firewall can answer IPv6 HTTPS. Remove conflicting records.
Wait for DNS propagation and verify:
```bash
dig +short A preview.YOURDOMAIN.fr
```
The returned value must match your VPS IPv4 before attempting certificate issuance.

## 3. SSH login and server preparation

**From laptop**, replace these placeholders with the actual user/IP:
```bash
ssh -i ~/.ssh/ijcai_preview_ed25519 LOGIN_USER@ACTUAL_VPS_IPV4
```
Verify the host key via the provider dashboard/out-of-band before accepting
it. On the VPS:
```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl
```
Install Caddy from its documented stable Ubuntu/Debian repository:
https://caddyserver.com/docs/install . This automatically installs a systemd
service. Use the official commands rather than unverified installation scripts.

Check that your cloud/provider firewall and host firewall allow public
**TCP 80 and 443**, and restricted SSH access on the configured SSH port.
Never enable a new firewall configuration unless a tested SSH/console recovery
path exists. Keep database and development ports closed.

## 4. Copy only one public HTML file

**From laptop**, repository root, after source-check:
```bash
cd ~/multi_agent_research/agent2_realdata_benchmark
python -m scripts.rct_public_preview_check
cd ..
scp -i ~/.ssh/ijcai_preview_ed25519 docs/index.html LOGIN_USER@ACTUAL_VPS_IPV4:/tmp/ijcai-preview-index.html
```
**On the VPS**:
```bash
sudo install -d -o root -g root -m 0755 /srv/ijcai-preview
sudo install -o root -g root -m 0644 /tmp/ijcai-preview-index.html /srv/ijcai-preview/index.html
rm -f /tmp/ijcai-preview-index.html
```
Do not copy the repository, `~/.ssh`, any invitation JSON or SQLite database
into the web root. It should contain only `index.html`.

## 5. Install the static-preview Caddyfile

Copy `agent2_realdata_benchmark/ops/rct/Caddyfile.static_preview.example`
to the VPS via `scp`, **then** replace `preview.example.fr` with the
registered `preview.YOURDOMAIN.fr`. You may use `sudoedit /etc/caddy/Caddyfile`
and paste the reviewed configuration after backing up the default.

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl enable --now caddy
sudo systemctl reload caddy
sudo systemctl status caddy --no-pager
```

Caddy automatically obtains a publicly trusted certificate and redirects HTTP
to HTTPS when a public domain resolves to the server and TCP 80/443 are reachable.
Do not disable certificate verification to make checks pass.

## 6. Verify from another network, record evidence

```bash
curl -fsSI https://preview.YOURDOMAIN.fr/
curl -fsSI http://preview.YOURDOMAIN.fr/
```
The HTTPS response should have an appropriate `200` status; HTTP should
redirect to HTTPS. Verify the exact DNS/certificate hostname and expiry with
`openssl s_client` or the browser certificate viewer. Test the static
four-stage walkthrough, keyboard focus, mobile layout, and test from a second
physical device/network. Confirm there is no POST enrollment, no user response
persistence and no study backend reachable.

Record: domain, host location, provider account owner, DNS screenshot (no
credentials), certificate info, exact commit SHA, service status, security
headers, keyboard/mobile test log, rollback procedure and independent review
status. Keep security credentials and participant files out of the report.

## 7. What is deliberately NOT deployed

- No `rct_candidate_cli serve` exposed on public IPv4.
- No `make_wsgi_app()` in rehearsal mode; the live release gate remains intact.
- No real invitations, study database, results export or participants.
- No inference from static preview, VPS TLS or browser testing that human
  ethics/privacy/measurement/content/security gates have passed.
- For real interactive RCT hosting, use `ops/rct/README_PRODUCTION_HARDENING.md`
  after all release evidence and independent review have been obtained.
