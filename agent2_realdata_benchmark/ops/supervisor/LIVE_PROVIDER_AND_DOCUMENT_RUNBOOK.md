# Release-gated operational procedure — documents and outbound email

This is NOT an approved or active LIVE deployment. The existing VPS operator
(8077), staging study (8788), pseudonymous monitor (8790), administrative
preview (8791), databases, invitations, and all learner progress are untouched.

## Architecture

An entirely separate LIVE installation uses the service account
ijcai-supervisor-live, /srv/ijcai-supervisor-live/current for exact Git
source, /var/lib/ijcai-supervisor-live for private research state,
and /etc/ijcai-supervisor-live for root-controlled approvals and secrets.
The LIVE study listens only on 127.0.0.1:8888, public interest forms on
127.0.0.1:8889, and a **separate private control-plane process** on
127.0.0.1:8890. Caddy proxies ONLY /study/* and /interest/* on formally
approved non-demo DNS. Researcher /control/ is SSH-tunnel-only at 8890.
The private instance cannot serve interest forms. To reach it locally use
`ssh -N -L 8890:127.0.0.1:8890 -i ~/.ssh/ijcai_preview_ed25519 davis@31.70.172.140`
then open `http://127.0.0.1:8890/control/` using the separate LIVE account
credentials generated in the private `initial-admin-secrets` folder.
Never reuse the STAGING bootstrap passwords or open port 8890 externally.

## Private document replacement

The signed external PDF bundle contains 16 required files identified by
the keys declared in src/prototype/supervisor_release_documents.py:
participant information school/external in EN/FR; consent records
school/external EN/FR; participant privacy EN/FR; recruitment privacy
EN/FR; instructional content review EN/FR; fatigue instrument EN/FR.

Prepare a PRIVATE source directory of PDFs; missing PDFs are allowed only
at the draft stage. In a clean checkout of the exact proposed Git commit:

    cd /path/to/repo/agent2_realdata_benchmark
    umask 077
    mkdir -p -m 0700 "$HOME/ijcai_release_documents" "$HOME/ijcai_reviewed_pdfs"
    python -m scripts.supervisor_doc_bundle_cli \
      --registry "$HOME/ijcai_release_documents" \
      --commit "$(git rev-parse HEAD)" \
      --draft-source "$HOME/ijcai_reviewed_pdfs"

This NEVER approves documents or opens enrollment. Put approved PDFs in a
PRIVATE source directory with the expected key.pdf filenames. To replace
one or more PDFs after a previously approved bundle has become active,
create a completely new pending revision:

    python -m scripts.supervisor_doc_bundle_cli \
      --registry /var/lib/ijcai-supervisor-live/document_registry \
      --commit FULL_EXACT_RELEASE_COMMIT \
      --refresh-source /private/reviewed/updates

The code copies unchanged approved PDFs, computes all SHA-256 hashes,
preserves the prior immutable version, and sets the NEW manifest decision
and every record to PENDING. An authorized institution reviews every PDF,
populates real reviewer/approval timestamps, and signs the exact manifest
outside the codebase. No test signing key or placeholder can be used.

An institutional signer who possesses their genuine private key can sign:
    openssl dgst -sha256 -sign /TRUSTED/INSTITUTION/PRIVATE_KEY \
      -out /private/version/manifest.sig /private/version/manifest.json

The release verifier requires a trusted independently authenticated public
key, genuine detached signature, exact source commit, 16 approved PDF
records, SHA-256 equality and a real dated reviewer. Activation also calls
the existing independent 14-category release gate and PI content approval.
It atomically updates only the private active version pointer and appends a
non-PII audit receipt. Restart both LIVE services after approved activation;
the running processes keep their already verified document snapshot until
restart. Existing per-student consent provenance records keep the previous
bundle/document hashes. GDPR erasure removes their personal history.

The executable quiz bank, treatment policy, fixed checkbox wording and PI
signed source content still bind to the EXACT Git commit. If these runtime
resources change, a newly tested/signed commit is necessary. External PDFs
can be replaced without Python source changes.

## Institutional Graph application-only (preferred)

Go to https://entra.microsoft.com/ . The authorized school tenant admin
registers a single-tenant dedicated IJCAI2027-StudyMail app, records the
tenant and client GUIDs, and configures application mail sending.

An Exchange Online administrator MUST scope Application Mail.Send to
the specifically approved mailbox(es), using Exchange RBAC for Applications
and explicit owner authorization. An unscoped Microsoft Entra application
Mail.Send permission is additive and can defeat narrower Exchange RBAC;
the admin must review/remove unscoped tenant-wide grants. Verify authorized
AND unauthorized mailboxes with Test-ServicePrincipalAuthorization. Owner
authorization is required individually for Wiam and Sara; having a researcher
login never grants use of their mailboxes. IT maintains the genuine
owner-authorization evidence and detached institutional signature.

Create a secret only within Entra under the approved app, store the value
in a service-readable 0640 root-owned private file, and plan rotation.
The currently implemented Graph application-only client uses a client
secret; certificate-based OAuth needs its own separately tested update.
No Microsoft account password or ChatGPT connector is used.

Official: https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac

## Personal Microsoft delegated Graph

Mail.Send delegated is valid for personal Microsoft accounts with an actual
Outlook/Exchange-accessible mailbox. A Gmail address used as a Microsoft
login alias does NOT imply Microsoft hosts its mailbox. Do not configure a
gmail.com sender in the Graph delegated route. Register a client supporting
personal accounts, request Mail.Send + User.Read + offline_access, and
register http://127.0.0.1:8765/callback. The real owner authorizes locally;
PKCE state is validated and the encrypted refresh grant is written to the
private vault. Test the authenticated /me identity and an actual Outlook
mailbox with an authorized test message before activation.

Official: https://learn.microsoft.com/en-us/graph/api/user-sendmail
Official: https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow

## Gmail delegated API (alternative)

Use https://console.cloud.google.com/ . Create the project, enable Gmail
API, configure OAuth consent/audience, create a Web application OAuth client,
register exact redirect http://127.0.0.1:8765/callback and enable only
openid + email + https://www.googleapis.com/auth/gmail.send. The actual
Google mailbox owner must explicitly consent. A Google OAuth app left in
External / Testing issues refresh tokens that can expire after seven days;
complete applicable publication/verification for long-lived production.

Gmail sends RFC 2822 MIME, base64url encoded, through
POST https://gmail.googleapis.com/gmail/v1/users/me/messages/send .

Official: https://developers.google.com/workspace/gmail/api/auth/web-server
Official: https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send
Official: https://developers.google.com/identity/protocols/oauth2

## Local owner-side OAuth bootstrap (NO ChatGPT account connection)

In the actual mailbox owner's local trusted WSL or Linux Python environment,
install cryptography==50.0.2, create a PRIVATE directory of mode 0700 and
run the following without sharing any tokens in chat:

    mkdir -p -m 0700 "$HOME/.ijcai_oauth_private"
    python -m scripts.supervisor_oauth_bootstrap init-vault \
      --vault-dir "$HOME/.ijcai_oauth_private/vault" \
      --vault-key-file "$HOME/.ijcai_oauth_private/mail.key"
    python -m scripts.supervisor_oauth_bootstrap start \
      --provider gmail_delegated \
      --sender YOUR_ACTUAL_VERIFIED_GOOGLE_MAILBOX \
      --client-id REGISTERED_GOOGLE_OAUTH_CLIENT_ID \
      --client-secret-file "$HOME/.ijcai_oauth_private/google-client.secret" \
      --session-file "$HOME/.ijcai_oauth_private/google.pending"

Open the printed consent URL in the OWNER'S browser. It may redirect to a
non-listening localhost URL; privately copy the full URL from the address bar
and enter it in the LOCAL hidden prompt of the finish command:

    python -m scripts.supervisor_oauth_bootstrap finish \
      --session-file "$HOME/.ijcai_oauth_private/google.pending" \
      --vault-dir "$HOME/.ijcai_oauth_private/vault" \
      --vault-key-file "$HOME/.ijcai_oauth_private/mail.key"

For Microsoft change provider to graph_delegated and set tenant=consumers
for a personal Microsoft account; use the genuine Outlook mailbox address.
Encrypted refresh grants and the independent Fernet key must be transferred
over authenticated secure channels to the dedicated LIVE vault and
root-owned private credentials directory. Configure separate backups,
revocation and reauthorization procedures.

## Personal Gmail OAuth registration (owner-controlled, no ChatGPT connection)

This is the fallback when no institutional Entra administrator can authorize
Microsoft Graph. Sending as **your own Gmail inbox** needs no university Entra
application privileges. The researcher login identities never become OAuth
identities. Proceed solely in your personal Google account and WSL machine:

1. Open https://console.cloud.google.com/ and select or create a dedicated
   project for IJCAI study mail. Enable **Gmail API** for that project.
2. In Google Auth Platform configure the app's branding and External audience.
   Add your own Gmail as a test user while testing. Under Data Access request
   `openid`, `email` and the minimum send scope
   `https://www.googleapis.com/auth/gmail.send`. No inbox-read scopes.
3. Under Clients create a **Web application OAuth client**, register the exact
   callback `http://127.0.0.1:8765/callback`, and privately record its Client
   ID and secret (do not copy them into Git, chat, shell history or logs).
   Complete Google's required verification/publishing steps before a
   long-running production sender. External/Testing Gmail refresh tokens
   normally expire in 7 days for `gmail.send`-scoped apps.
4. On trusted local WSL, `umask 077`; create a mode-0700 credentials directory,
   install the client secret in a mode-0600 file, and run the documented
   `supervisor_oauth_bootstrap init-vault`, `start --provider gmail_delegated`
   and `finish` commands from the section above.
5. Run the existing
   `python -m scripts.supervisor_mail_owner_canary` with your **actual**
   Gmail address in `--sender`. Without `--send`, this only checks the
   encrypted refresh grant; with `--send --confirm-own-mailbox`, it sends
   **one generic test email to yourself** and leaves a permanent no-retry
   receipt. Never put invitation links into this preliminary canary.
6. Independently inspect the provider's Sent folder and destination inbox,
   grant retention/rotation procedures and the applicable data-processing
   agreement. Only then configure this route in the approved institutional
   LIVE sender policy.

Your Microsoft personal sign-in using a `@gmail.com` alias does not create
an Outlook mailbox. Microsoft Graph `Mail.Send` delegated can be used only
with an actual Graph-accessible personal mailbox, as confirmed by a successful
owner-authenticated Graph request.

## Durable custom-domain From address — optional Brevo API route

The shared address `private_quiz@selfhealing-edu.fr` is **not** granted simply
by using this string in a From header. It must be controlled and authenticated
by the domain owner. Starting January 2027, Google says personal Gmail's
third-party send-as feature will cease supporting non-Gmail third-party
addresses in the existing form (Google Workspace aliases are excepted).
For a study continuing in 2027, prefer a Google Workspace or Exchange Online
mailbox on the study domain, or a domain-native transactional API.

An optional, provider-neutral `brevo_api` sender implements
`POST https://api.brevo.com/v3/smtp/email`, in addition to
`graph_application`, `graph_delegated` and `gmail_delegated`. Its
interface is unchanged: `send(to, subject, body)`. The API credential is
read from a private file, never committed. Provider acceptance must return
HTTP 201 and a plausible nonempty message ID; other outcomes are marked
uncertain and are **never automatically retried**. A deterministic
provider-side idempotency UUID and persistent private journal protect
against duplicates; no invitation token is included in the audit record.

Owner-side steps, without ChatGPT access to any account:

1. Confirm **actual control and permission** to use
   `selfhealing-edu.fr`; verify the domain in the approved mail service.
   Configure its exact DNS records for SPF, DKIM and DMARC, and ensure the
   real `private_quiz@` mailbox/alias can receive replies and rights requests.
2. If using Brevo, create the study-controlled sender/domain in its own
   dashboard, complete sender verification and domain authentication,
   accept the appropriate research-data processor agreement, and issue a
   restricted transactional-mail API key in the account's developer section.
   Do not grant the app general contact export or campaign privileges.
3. Securely write the API key to a root-owned mode-0600/0640 file under
   `/etc/ijcai-supervisor-live/mail/`, readable only by the dedicated
   service account, but never put a live API key into the draft templates.
4. The institution independently reviews this exact sender domain and
   each authorized staff actor (e.g. Wiam, Sara and Davis). Its signed
   `mail_owner_authorizations` record must include
   `sender_domain_authenticated=true`, the owner/domain approval PDF
   digests, exact `api_key_label`, secret-file path and the explicitly
   authorized researcher emails. Unapproved draft values must remain false.
5. Set the private route's `default` to the signed `domain_native_brevo`
   route only when the genuine LIVE release has been independently approved.
   Restart the approved isolated LIVE service through the reviewed runbook,
   not by editing a public demo or resetting any SQLite database.
6. Run an explicitly authorized owner-to-self or controlled-group deliverability
   test, verify Received/Spam and reply handling, and inspect the private
   delivery journal and any delivery webhooks. Do not activate real-human
   research with a fake approval.

Reference:
https://developers.brevo.com/reference/send-transac-email
https://developers.brevo.com/docs/getting-started-with-senders-and-domains
https://support.google.com/mail/answer/22370

## Per-actor permission for shared mailboxes

Using the same centrally approved sender for Wiam, Sara and Davis does
**not** give anyone permission to impersonate those researchers. The
outbound From remains the verified central mailbox. The private login and
staff audit record identify the administrator initiating the send.
Signed `authorized_actors` arrays for each route must individually contain
the exact staff email; `by_actor` may only select a signed sender already
approved for that staff member. Administrators omitted from the signed list
cannot initiate a send, even if they have a researcher/supervisor login.
Scheduled reminder delivery uses the independently approved default
service-sender route, not a staff user's identity.

The provider-neutral architecture intentionally does not change the four
application admin identities or their permissions, questionnaire URLs,
participant identifiers, randomized arm assignments, research history or
student progress when a mailbox or provider is swapped.

## Signed sender routing & idempotency

Templates templates/mail_routes.DRAFT.json,
templates/mail_owner_authorizations.DRAFT.json and templates/live.env.DRAFT
are intentionally NONFUNCTIONAL.

Production requires an institutionally signed exact-commit authorization
manifest whose entries bind each allowed provider, mailbox, verified owner
consent and approved permission scope. The route file may select a default
provider or signed per-actor routes. It cannot invent a sender missing
from the signed policy. The administrator allowlist has never been modified.

Configure private LIVE environment paths SUPERVISOR_MAIL_CONFIG,
SUPERVISOR_MAIL_APPROVAL, SUPERVISOR_MAIL_APPROVAL_SIGNATURE,
SUPERVISOR_MAIL_VAULT_DIR, SUPERVISOR_MAIL_VAULT_KEY_FILE,
SUPERVISOR_MAIL_AUDIT_DB and SUPERVISOR_MAIL_AUDIT_KEY_FILE.
Set SUPERVISOR_MAIL_TRANSPORT=provider_router only after real authorization.
Keep ALL keys/tokens outside Git, public Caddy and logs.

All sends use the same send(to,subject,body) interface. Private mail audit
records provider ID, HMAC-recipient digest, timestamps, accepted/uncertain
state; never actual email, invitation token or content. Exact invitation
idempotency keys forbid replay after any ambiguous network failure. Existing
outboxes enforce scheduled-reminder idempotency. Graph 202 means accepted for
processing, not inbox delivery. Google 200 also requires real confirmation.

## LIVE VPS deployment — separate from staging

The operator installs ONLY after a verified new source tree has been
uploaded. On WSL, create a Git bundle for the exact release branch, then
transfer it by SSH/SCP to the VPS; do not copy a bare source archive because
the live gate requires a clean exact Git checkout.

    cd ~/multi_agent_research
    git fetch origin
    git bundle create /tmp/ijcai-live.bundle \
      origin/research/ijcai2027-supervisor-consent-gdpr-20261112
    scp -i ~/.ssh/ijcai_preview_ed25519 /tmp/ijcai-live.bundle \
      davis@31.70.172.140:/home/davis/ijcai-live.bundle

Use the exact new version of ops/supervisor/install_live_services.sh
from the verified release, transferred by the same signed-pinned process.
The root installer provides two distinct subcommands:

    sudo bash install_live_services.sh prepare /home/davis/ijcai-live.bundle FULL_SHA

PREPARE installs separate LIVE code, venv, **empty separate SQLite research,
contacts and administrator databases**, dedicated service account and four
NEW isolated LIVE administrator credentials in `initial-admin-secrets` under
0700 state, plus DISABLED systemd units. Transfer the four one-time passwords
privately; never print or copy them into chat, and destroy the originals
once secure individual handoff is complete. It does not change Caddy or
start real enrollment or mail. After final institutional records, DNS,
password/key ownership and backups are independently verified, the authorized
operator completes signed LIVE document activation, runs:

    python -m scripts.supervisor_live_readiness

and only then, after independent approvals and approved grace-hours policy:

    sudo bash install_live_services.sh activate APPROVED_GRACE_HOURS

ACTIVATE fails closed unless both actual LIVE WSGIs import successfully,
the entire signed core/PI/document/mail policy checks pass, DNS exists,
HTTPS Caddy routes are verified and the private dashboard is not public.
On failure, it stops the separate LIVE units and rolls back Caddy changes.
The reminders timer starts only after public routes pass.

## Safe upgrade of an already PREPARED (never activated) LIVE release

PREPARE creates the three systemd unit files and deliberately refuses a
second PREPARE attempt. **Never remove the units, databases, passwords or
release directory to retry installation.** For a newer reviewed source commit,
upload a complete pinned remote-tracking Git bundle together with the
`upgrade_pending_live_release.sh` script and matching
`materialize_live_bundle.sh` from that exact commit. Verify all transferred
files with SHA-256 before executing anything as root.

The dedicated upgrade accepts only an existing clean, Git-pinned, inactive
installation with disabled study/recruitment/control/reminder units, no
LIVE Caddy fragment, no LIVE environment file and no approved/current
document-bundle pointer. An already activated or partially configured
installation must follow a separate independently reviewed migration plan.
With those prerequisites checked, the operator uses:

    sudo bash upgrade_pending_live_release.sh /private/upload/ijcai-live.bundle FULL_NEW_COMMIT_SHA

It checks the exact bundle ref/SHA, creates a new source checkout and
**new PENDING 16-category document version** bound to the new commit, then
atomically changes only the `/srv/ijcai-supervisor-live/current` code
symlink. Existing LIVE research/contact/admin databases, confidential
administrator credentials, historic document versions, and staging state
remain untouched. It does not install or start public services, send mail,
approve the study or run an experimental enrollment.

The new commit MUST be tested, reviewed and signed explicitly; an existing
institutional signature for the previous source commit does not authorize
a different one. Do not reuse the old bundle or the PREPARE-only wrapper
to update a populated install. Inspect stopped units and the new source
SHA independently after upgrade.

Before the first participant, institutional operations must ALSO complete:
independent security/accessibility audit, power/protocol approval, 3-arm
randomization integrity review, load/device tests, offsite encrypted backup
and separate-machine restore, signed data-retention/DPO review, inbox canary,
negative out-of-scope sender test, and documented incident procedures.
The installer cannot independently attest to these approvals.

Current STAGING services and all existing participant data remain unchanged.
No placeholder or software developer signature authorizes real-human use.
