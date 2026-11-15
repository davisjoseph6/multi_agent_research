# Persistent private VPS acceptance runbook

The pending LIVE installation stores its own documents, participant databases and four independently provisioned administrator credentials at /var/lib/ijcai-supervisor-live. Do not reset or migrate those records. The persistent rehearsal added here has a DIFFERENT Unix service identity and data directory, no Caddy public route, no mail dispatcher, no genuine human enrollment, and no institutional signature bypass.

## 1. Upgrade the reviewed exact Git source, pending-only

Use the guarded pending-only Git bundle upgrade, never rerun the original empty-LIVE installer. Confirm the latest expected commit via GitHub, syntax-check the upgrade wrapper, and verify that its reported exact source SHA matches the approved source. The old LIVE state and passwords must remain unchanged.

## 2. Install durable SSH-only QA on the VPS

On WSL:

    ssh -tt -i ~/.ssh/ijcai_preview_ed25519 davis@31.70.172.140

On the VPS:

    sudo bash /srv/ijcai-supervisor-live/current/agent2_realdata_benchmark/ops/supervisor/install_private_persistent_qa.sh \
      davis.joseph@aivancity.education davisjoseph767@gmail.com

Check:

    sudo systemctl status ijcai-supervisor-private-qa --no-pager
    sudo systemctl is-enabled ijcai-supervisor-private-qa
    sudo ss -lnt | grep 127.0.0.1:8897

The installer creates a new Unix user ijcai-supervisor-private-qa and owner-only 0700 state at /var/lib/ijcai-supervisor-private-qa. Its root-controlled 0640 environment resides at /etc/ijcai-supervisor-private-qa/qa.env. It refuses to overwrite an existing service, state credentials or public Caddy configuration. Its systemd cgroup restricts network use to localhost and explicitly hides the LIVE data and authorization folders.

## 3. Researcher/student browser access through your own SSH tunnel

On WSL, in a second terminal:

    ssh -N -L 8897:127.0.0.1:8897 \
      -i ~/.ssh/ijcai_preview_ed25519 davis@31.70.172.140

Friendly paths on that private tunnel:

- http://127.0.0.1:8897/questionnaire/student
- http://127.0.0.1:8897/questionnaire/external
- http://127.0.0.1:8897/researcher
- http://127.0.0.1:8897/researcher/invitations
- http://127.0.0.1:8897/participate

Those are mnemonic *paths*, not approved public DNS hostnames. Invitation tokens are displayed once and stored only as hashes; preserve any needed student link privately.

## 4. Independent staff logins and durable participant data

Four QA identities are created on initial first start; one private 0600 file per staff identity appears in /var/lib/ijcai-supervisor-private-qa/qa-admin-secrets. Read only the intended person's secret through the authorized VPS account and a protected transfer, never Git, chat, or a shared email. Each researcher changes their password at first sign-in. After restarting the service, the existing password hashes, staff access decisions, student IDs, assigned arms, all events and timing measurements persist. The initial secret files can be securely removed only after each staff identity verifies its new password.

    sudo systemctl restart ijcai-supervisor-private-qa

The FOUR separate LIVE bootstrap accounts already exist in /var/lib/ijcai-supervisor-live/initial-admin-secrets. They are distinct from QA and cannot be used until authorized LIVE activation.

Student records persist as real SQLite tables within protected QA state, and the researcher dashboard can download a per-student pseudonymous seven-file ZIP with session/quiz arm, C1-C8 BKT estimated mastery, overall mean, event-level response times, session gaps, fatigue and assessments. QA data is explicitly not a genuine RCT dataset. Use independent encrypted backups if this rehearsal must survive disk failure.

## 5. Proposed friendly production hostnames — NOT YET CONFIGURED

After the domain owner confirms real DNS control, TLS and institutional approval, one possible naming scheme is:

- https://study.selfhealing-edu.fr/study/
- https://study.selfhealing-edu.fr/interest/school
- https://study.selfhealing-edu.fr/interest/external

These exact hostnames are suggestions only, not verified DNS or active services. The private LIVE research dashboard on loopback port 8890 is intentionally SSH-only. Never publicly route /control/ without a separately reviewed identity-aware access gateway. The approved installer requires genuine non-demo DNS, HTTPS, exact-commit release signatures, all bilingual signed documents and a signed mailbox policy. Placeholder PDFs must remain pending; adding the genuine versions does not require discarding research data.

## 6. Complete the already imported Google OAuth client locally

The downloaded Google Web client JSON was imported successfully, but no Gmail OAuth grant has yet been issued. In WSL run:

    cd ~/ijcai_private_selftest/agent2_realdata_benchmark
    source ~/multi_agent_research/agent2_realdata_benchmark/.venv/bin/activate
    umask 077
    python -m scripts.supervisor_oauth_bootstrap init-vault \
      --vault-dir "$HOME/.ijcai_oauth_private/vault" \
      --vault-key-file "$HOME/.ijcai_oauth_private/mail.key"
    python -m scripts.supervisor_oauth_bootstrap start \
      --provider gmail_delegated \
      --sender davisjoseph767@gmail.com \
      --client-id "$(cat "$HOME/.ijcai_oauth_private/google-client-id.txt")" \
      --client-secret-file "$HOME/.ijcai_oauth_private/google-client.secret" \
      --session-file "$HOME/.ijcai_oauth_private/google.pending"

Open the printed owner-only consent URL in the actual Google account, then follow the protected finish and self-to-self canary procedure in GMAIL_OWNER_SHARED_SENDER_RUNBOOK.md. A harmless owner-to-self email canary does not authorize sending real research invitations. Do not send institutionally controlled messages or participant links through the actual LIVE buttons until the independently verified release and sender approvals are applied.

IMPORTANT: In the logs, the original OAuth Web JSON was stored inside the working Git repository. Move that original file to a private directory outside all Git checkouts and verify git status. The new .gitignore pattern helps prevent accidental first-time commits; it cannot remove an already committed secret or revoke one. Never upload the secret JSON, OAuth redirect URL, authorization code, or refresh token to chat.
