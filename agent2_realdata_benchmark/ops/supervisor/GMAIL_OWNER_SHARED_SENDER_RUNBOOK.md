# Owner-controlled Gmail sender — exact next actions

The software's provider-neutral dispatch, reminder worker, private mail audit
and per-researcher sending authorization already exist. This operator
procedure is specific to the **owner's personal Gmail sender**
`davisjoseph767@gmail.com`. It avoids requiring Microsoft Entra app
registration or institutional Microsoft 365 Send As permissions.

The supervisor still distributes only the initial public questionnaire
links personally. The app sends *private study invitation tokens* only
to approved candidates, and only once the actual signed LIVE release is
authorized. Staff logins are separate from email OAuth.

## 1. Configure your actual Gmail mailbox (external account-side steps)

Do these actions only as the actual mailbox owner. ChatGPT does not need
any Gmail, Google, Microsoft or VPS secrets.

1. Open https://console.cloud.google.com/ and create/select a project
   dedicated to this study's outgoing mail. Enable **Gmail API**.
2. Navigate to **Google Auth Platform → Branding**, set the legitimate
   application description and support/developer contact. Under **Audience**
   choose **External**, with only your own Google address in the test-user
   list while preparing the connector.
3. In **Data Access**, request the minimum
   `https://www.googleapis.com/auth/gmail.send`, alongside OpenID email
   identity scopes. Never request Gmail read, modify, delete or full-mail
   scopes for sending study invitations.
4. Under **Clients → Create Client → Web application**, register exactly
   `http://127.0.0.1:8765/callback` as an authorized redirect URI.
   Keep the OAuth Client ID and Client Secret in your own private password
   manager. The secret must **not** be committed or shared in chat.
5. Google classifies `gmail.send` as a **sensitive** scope and may require
   OAuth verification for a published app. External/Testing refresh tokens
   issued with this scope normally expire in **seven days**. A successful
   owner-only test does not establish a durable production sender.

Official documentation:

- https://developers.google.com/workspace/gmail/api/auth/scopes
- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.google.com/identity/protocols/oauth2

## 2. Authorize the sender in your own WSL machine

Use the exact checked-out candidate source and existing Python environment:

    cd ~/ijcai_private_selftest/agent2_realdata_benchmark
    source ~/multi_agent_research/agent2_realdata_benchmark/.venv/bin/activate
    umask 077
    mkdir -p -m 0700 "$HOME/.ijcai_oauth_private"
    python -m scripts.supervisor_oauth_bootstrap init-vault \
      --vault-dir "$HOME/.ijcai_oauth_private/vault" \
      --vault-key-file "$HOME/.ijcai_oauth_private/mail.key"

Privately place the **actual Google OAuth Web client secret value** in the
mode-0600 file `$HOME/.ijcai_oauth_private/google-client.secret`.
Never paste it into a shell command line, Git repository, screenshot or
ChatGPT conversation. Create the file using a locally trusted editor and
verify `stat -c '%a' "$HOME/.ijcai_oauth_private/google-client.secret"`
returns 600.

    python -m scripts.supervisor_oauth_bootstrap start \
      --provider gmail_delegated \
      --sender davisjoseph767@gmail.com \
      --client-id YOUR_GOOGLE_WEB_OAUTH_CLIENT_ID \
      --client-secret-file "$HOME/.ijcai_oauth_private/google-client.secret" \
      --session-file "$HOME/.ijcai_oauth_private/google.pending"

Open the printed Google consent URL in **your own browser**, consent only
for the exact Gmail account, and run the finish command:

    python -m scripts.supervisor_oauth_bootstrap finish \
      --session-file "$HOME/.ijcai_oauth_private/google.pending" \
      --vault-dir "$HOME/.ijcai_oauth_private/vault" \
      --vault-key-file "$HOME/.ijcai_oauth_private/mail.key"

Enter the full redirected localhost URL into the *hidden local prompt*.
The short-lived authorization code is secret; don't share or paste it here.

## 3. Do a single generic delivery test to yourself

This is **not a study invitation** and must not include a private token:

    python -m scripts.supervisor_mail_owner_canary \
      --provider gmail_delegated \
      --sender davisjoseph767@gmail.com \
      --client-id YOUR_GOOGLE_WEB_OAUTH_CLIENT_ID \
      --client-secret-file "$HOME/.ijcai_oauth_private/google-client.secret" \
      --vault-dir "$HOME/.ijcai_oauth_private/vault" \
      --vault-key-file "$HOME/.ijcai_oauth_private/mail.key" \
      --receipt-file "$HOME/.ijcai_oauth_private/owner-canary-first.json"

Without `--send`, this only performs a protected OAuth identity/vault
preflight; no mail is sent. To send one harmless email to your own inbox,
rerun that exact command **once** with
`--send --confirm-own-mailbox`. The private receipt file prevents an
automatic retry, even after an ambiguous provider response. Independently
inspect your Gmail Sent and Inbox/Spam folders. Never delete the receipt
to force a duplicate attempt without investigating delivery.

## 4. Prepare one central sender for all four staff accounts

Two separately editable **NONFUNCTIONAL templates** are provided:

- `templates/mail_routes.GMAIL_OWNER_DRAFT.json` — an owner-Gmail sender
  and intended researcher/supervisor route selection.
- `templates/mail_owner_authorizations.GMAIL_OWNER_DRAFT.json` — a PENDING
  exact-commit policy recording intended staff actors and the files for
  genuine mailbox-owner and institutional permission evidence.

The intended authorized actor list is Davis, Wiam, Sara and Yaacoub. When
a staff member clicks **Send all approved**, the existing private
researcher dashboard calls the production dispatch service; the signed
router chooses your central Gmail sender and records which administrator
initiated delivery. **It does not impersonate Wiam or Sara as the mail
From address.** All sends carry recipient-specific private tokens; no
tokens are visible in server logs or provider audit receipts.

The templates are deliberately incomplete, with invalid OAuth Client ID
and pending authorization. The institution must independently validate
the exact release SHA, signed consent/privacy documents, mailbox owner's
approved staff rights, authenticated public URL, data processing and
delivery acceptance before using LIVE invitation mail. The user's
requested staff authorization is recorded as **intent**, not falsely
represented as an institutional signature. Never set the decision to
approved or manufacture evidence to satisfy the release gate.

## 5. Keep private QA tests independent

The localhost `supervisor_private_qa` form and researcher dashboard
have separate temporary databases and four temporary administrator
passwords. On every process restart their credentials change. The QA
`/control/qa/` page can issue **all** approved test links in one click,
without emailing anyone. The real signed LIVE `/control/` page already
provides **Send all approved** for genuine mailing, and remains disabled
until all release checks pass. Neither workflow migrates any QA response
into an approved RCT cohort.
