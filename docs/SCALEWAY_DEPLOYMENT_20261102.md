# Scaleway deployment — restricted fictional interactive RCT demonstration

**Date:** 2026-11-02. **Status:** Provisioning instructions only; no Scaleway
resources, DNS, certificates or real participant enrollment are claimed here.

## What is being deployed

A restricted, staff/operator-only, **fictional** real Flask/POMCP three-arm
interactive demo using `operator_demo`. This is **not** the GitHub Pages
scripted public preview and **not** an authorized human RCT. Keep the genuine
`live` release gate intact; no LFS texts or unauthorized data.

Existing app service instructions:
[`FULL_INTERACTIVE_OPERATOR_DEMO_DEPLOYMENT.md`](FULL_INTERACTIVE_OPERATOR_DEMO_DEPLOYMENT.md).

## Stage 1 — create Scaleway project and register SSH public key (local laptop)

Scaleway console: https://console.scaleway.com/

Create or select a Project specifically for this demo (e.g., `ijcai-fictional-demo`).
Scaleway scopes SSH public keys to Projects. Under Project dashboard >
Credentials > SSH keys > Add, upload the **public** half of the already-created
`~/.ssh/ijcai_preview_ed25519` key. On the user's laptop:

```bash
test -s ~/.ssh/ijcai_preview_ed25519.pub
chmod 600 ~/.ssh/ijcai_preview_ed25519
ssh-keygen -lf ~/.ssh/ijcai_preview_ed25519.pub
cat ~/.ssh/ijcai_preview_ed25519.pub
```

Only paste the `.pub` line into Scaleway. Do not reveal the private file,
passphrase, Scaleway account login, API secret, study invitations, or user data.

Official guide: https://www.scaleway.com/en/docs/iam/security/create-ssh-key/

## Stage 2 — create Instance with accurate billing

Compute > CPU & GPU Instances > Create Instance > Create CPU Instance.
Recommended for restricted stage:
- Name: `ijcai-operator-demo`
- Instance type: **DEV1-M** (3 shared vCPUs, 4 GiB RAM).
- Availability zone: **fr-par-1**, or another **actual Paris zone** with stock.
- Image: **Ubuntu 24.04 LTS** (Scaleway name: Ubuntu Noble; image label
  `ubuntu_noble` for CLI).
- Root volume: **30 GB Block Storage 5K** if available and compatible.
  Confirm it is a bootable root volume. Minimum OS root volume is 10 GB.
- Networking: allocate **one flexible public IPv4**; IPv6 optional, but do
  not create DNS AAAA records unless IPv6 is configured and firewall verified.
- SSH key: select the public key uploaded to the *same Scaleway Project*.
- Select a dedicated Security Group (see next stage).
- Verify compute **plus** storage **plus** IPv4 **plus** VAT in the purchase
  summary; snapshots, optional backups and the domain have separate costs.

For approximately 730 running hours/month in Paris at observed list prices
(November 2026), before VAT: DEV1-M compute ~€14.74, 30 GB Block 5K
~€2.85, flexible IPv4 ~€2.92 = **~€20.51/month pre-VAT**.
Budget is indicative, not a binding vendor quotation; storage prices/capacity
and promotions can change.

Sources:
- https://www.scaleway.com/en/docs/instances/how-to/create-an-instance/
- https://www.scaleway.com/en/pricing/virtual-instances/
- https://www.scaleway.com/en/pricing/storage/
- https://www.scaleway.com/en/docs/instances/faq/

Scaleway may continue charging for attached volume/flexible IP after an
Instance is powered off. Delete unused billable resources deliberately.
Source: https://www.scaleway.com/en/docs/instances/reference-content/understanding-instance-pricing/

## Stage 3 — security group (before deployment)

Compute > CPU & GPU Instances > select actual Paris zone > Security groups >
Create. Attach it to the new Instance.

- Default **inbound: DROP** (stateful group).
- TCP 22: ACCEPT from your current public IPv4 **/32**, if stable; otherwise
  use a tightly managed administrator range, with console recovery.
- TCP 80: ACCEPT from internet for HTTP→HTTPS and ACME.
- TCP 443: ACCEPT from authorized reviewer networks if fixed, otherwise
  internet **only** with the demo's Caddy operator authentication and
  independent security check.
- TCP 8077: **NEVER** accessible from public network.
- Other inbound: DROP.
- Outbound: allow DNS/Ubuntu updates/ACME/repository access where required.
- Do not lock yourself out; verify SSH via Scaleway console before enabling
  any further host-level firewall.

Scaleway instructions:
https://www.scaleway.com/en/docs/instances/how-to/use-security-groups/

## Stage 4 — register domain and configure DNS

Scaleway console > Domains & Web Hosting > Domains and DNS >
Search/Register new domain.

Use a neutral research-owned name that does not claim an institution is the
operator or sponsor. Domain name availability and annual prices must be
verified in the checkout; optional examples such as `yourresearchdomain.fr`
are placeholders, not registered names.

Scaleway publishes .fr registration requirements: the domain registrant
and administrative contact must have eligible EU/EEA/Swiss residency while
the domain is active; citizenship is not itself the stated condition.
If continuity of eligibility is uncertain, consider .com instead.

Official sources:
- https://www.scaleway.com/en/docs/domains-and-dns/quickstart/
- https://www.scaleway.com/en/docs/domains-and-dns/reference-content/registration-requirements/
- https://www.scaleway.com/en/pricing/domains/

Once registered, under Domains and DNS > domain > DNS zones, create
`A` record `demo` to the **actual public IPv4** of the new Instance.

| Type | Name | Value |
|---|---|---|
| A | demo | INSTANCE_PUBLIC_IPV4 |

Avoid an AAAA record unless IPv6 is configured on the server. Verify from
the local laptop:

```bash
dig +short A demo.YOURDOMAIN.fr
```

Output must equal the Instance IPv4 before attempting TLS certificate issuance.
DNS zone instructions:
https://www.scaleway.com/en/docs/domains-and-dns/how-to/manage-dns-records/

## Stage 5 — first SSH connection (from laptop)

On instance Overview, copy Scaleway's **actual recommended SSH command**;
Scaleway's official Instance docs typically use the `root` account.

```bash
ssh -i ~/.ssh/ijcai_preview_ed25519 root@ACTUAL_INSTANCE_IPV4
```

Verify the host-key fingerprint through a trusted provider console or
out-of-band channel before first accepting it. If the image requires a
different user, follow the Instance Overview, not a guessed account.
SSH-key authentication should work without uploading the private key.

After login, on server:

```bash
cat /etc/os-release
uname -m
free -h
df -h
id
ip -brief addr
sudo apt-get update
```

Stop at this checkpoint if unexpected network, OS, credentials or billing
issues arise. Do not start public Flask serving on port 8077.

## Stage 6 — deploy full interactive app after SSH/DNS checks

Follow the existing linked runbook:
`FULL_INTERACTIVE_OPERATOR_DEMO_DEPLOYMENT.md`.

Key order: restricted OS service identity, pinned/reviewed Python environment,
`operator_demo` settings matching actual `demo.YOURDOMAIN.fr`, fresh
**synthetic-only** seeded database, loopback-only Gunicorn, Caddy with
automatic HTTPS, Basic auth for the webpage and private invitation Bearer
authorization for API endpoints.

After launch validate HTTPS certificate, no accessible `/api/rct/enroll`,
wrong-host rejection, auth boundaries, mobile/browser flow, network reload,
server restart/resume, isolation, security/permissions and monitoring.
Do not copy private invitations or SQLite database to GitHub/Pages.

## Stop/go boundaries

### Verified on researcher's local machine
- 1296 regression tests, no failures (earlier staging source revision).
- 30/30 fictional multi-arm load journeys; 11,130 in-process HTTP requests;
  zero pending, p95 82.488 ms, maximum request 5.55 seconds.
- Local SQLite pending-action recovery passed.
- Ubuntu 24.04 real headless Chromium full fictional three-session browser
  journey passed, including session resume.

### Not established yet
- Actual Scaleway deployment, host TLS, network/browser load, independent
  security/accessibility audits, real-device access, production backup
  recovery, validated instructional content and licensed LFS.
- Protocol/SAP authorizations and actual human study enrollment.

**Next progress checkpoint:** actual Instance type/zone, OS version, public
IPv4 and chosen domain, plus nonsecret SSH/DNS check output.
