# Verified private VPS fictional-pilot operations (2026-11-10)

**State:** This is a **synthetic-only engineering release**. It cannot admit students. The Aivancity PI proposal, content approvals, consent, privacy, ethics and 14 human study release gates are pending. Do not expose the browser preview over a public domain, Caddy, or a cloud load balancer. The existing authenticated \`demo.selfhealing-edu.fr\` service is a different, older fictional demonstration; leave it untouched.

## Observed operator evidence

- WSL full suite on commit \`5c6bb17\`: **1,421 passed** (156.92 seconds).
- IONOS Ubuntu 24.04.5 VPS: **37 relevant tests passed** in 2.37 seconds; application served \`HTTP 200\` over SSH tunnel on \`127.0.0.1:8766\`, returned correct restrictive security headers.
- Bare \`POST /preview/api/status\` returned **403** without the fictional preview nonce and origin. This is expected.
- The application's \`/preview/api/\` routes are restricted to a loopback runner; user-selectable A/B/C and fixture-created fake records are NOT real allocation controls.

## New reproducible read-only HTTP acceptance suite

After updating the private VPS snapshot **only after reviewing the commits and running the local tests**, run on the VPS in the synthetic app's directory:

\`\`\`bash
PY="$HOME/ijcai_preview_5c6bb17/.venv/bin/python"
"$PY" -m pytest -q tests/test_pilot_private_vps_smoke.py
"$PY" -m scripts.pilot_private_vps_smoke --base http://127.0.0.1:8766
\`\`\`

The test first verifies a real loopback Flask server. The read-only live probe checks the HTML and assets, untrusted origin/nonce rejection, all A/B/C **status** responses, absence of enrollment/start endpoints and restrictive headers. It never submits answer content, calls \`next\`, creates students, starts visits or sends personal data. It refuses any URL other than \`http://127.0.0.1:<port>\`. The expected state is a new isolated fictional SQLite file. Do not run it against a human deployment.

## Optional restart-on-failure systemd deployment

Stop the existing manual server (Ctrl+C) before installing the system service. **Do not run two services on the same port or database.** Root review of the committed template is required before enabling.

\`\`\`bash
sudo install -o root -g root -m 0644 \
  ops/rct/ijcai-pilot-private-preview.service.template \
  /etc/systemd/system/ijcai-pilot-private-preview.service

sudo systemctl daemon-reload
sudo systemctl enable --now ijcai-pilot-private-preview
sudo systemctl is-active ijcai-pilot-private-preview
sudo ss -lntp | grep ':8766'
"$PY" -m scripts.pilot_private_vps_smoke --base http://127.0.0.1:8766
\`\`\`

Expected listener: **\`127.0.0.1:8766\` only**. Existing SSH tunnel stays:

\`\`\`bash
ssh -i ~/.ssh/ijcai_preview_ed25519 -N \
  -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8766:127.0.0.1:8766 \
  davis@31.70.172.140
\`\`\`

Notes: the unit assumes the verified copy at \`/home/davis/ijcai_preview_5c6bb17\`, operated by \`davis\`; it sets \`ProtectSystem=strict\`, \`ProtectHome=read-only\`, a single \`ReadWritePaths\` exemption for synthetic SQLite state, \`NoNewPrivileges\`, IP allowlist \`localhost\`, constrained processes/memory/CPU and 077 permissions. The service cannot operate if the directory is absent or owned differently. The unit is a **template**, not evidence of independent security approval. Before enabling, ensure the state path and port are as specified; do not use on any production-human path.

Validate basic recovery with a supervised restart of only the new unit:

\`\`\`bash
sudo systemctl restart ijcai-pilot-private-preview
sudo systemctl status ijcai-pilot-private-preview --no-pager
"$PY" -m scripts.pilot_private_vps_smoke --base http://127.0.0.1:8766
\`\`\`

The current database should survive a restart. This is not offsite restore/production disaster-recovery evidence. The service runs one Werkzeug process; **it is explicitly not production capacity**, and no remote network access is permitted.

## Software engineering still needed for real students (not silently assumed done)

1. Build a new *separately reviewed and deployed* human study service, instead of promoting \`pilot_local_browser_preview\`. Authenticate staff, ensure noncoercive consent/eligibility, use server-only concealed 1:1:1 assignment, no client-supplied arm or authorization booleans.
2. Enforce actual time and 3–5-day visits, attendance/session windows, exceptions/missed visits, content hashes, per-arm treatment fidelity, resource budget and immutable pre/post M-VAS once the measurement item is approved.
3. Select an independently assessed transactional data architecture and validate true multi-process web workers. Thread-local FIFO counters do not coordinate across processes; SQLite's behavior under synthetic load is not sufficient.
4. Create staging TLS and isolation, locked dependency/SBOM pipeline, staff MFA, privacy-aware monitoring, per-route load budgets, CI gates and automated backup restore drills on a nonproduction environment.
5. Obtain independent browser/device/assistive technology, security, accessibility, real HTTPS load and disaster recovery reports with agreed thresholds.
6. Receive the PI, statistician, Aivancity, DPO, ethics and independent reviewer evidence in a private, authenticated store. No real enrollment until an authorized release is signed and tied to the exact immutable build.

**This branch does not satisfy any human enrollment release gate merely by passing software tests.**
