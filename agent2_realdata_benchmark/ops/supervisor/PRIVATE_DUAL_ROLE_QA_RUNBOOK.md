# Private dual-role acceptance (self-test; no institutional-release bypass)

This is a distinct, disposable, localhost-only QA environment intended to
test a staff user and two applicant types concurrently. It runs the actual
production Flask study and researcher implementations in **STAGING MODE**,
with separate transient SQLite databases and independent test-only passwords.
It is **not** the public or approved LIVE study, is not a recruitment site,
does not deliver any email, and cannot produce legitimate RCT participation.
Never migrate its records, student tokens, consent checkbox clicks or answers
into an approved RCT dataset. Draft consent text is visibly a review candidate.

## Prerequisites

Use an isolated checked-out release (for example the exact approved Git
candidate), a local Python virtual environment containing Flask and project
dependencies, and a free loopback port. Do **not** execute as root. Do not
run inside the prepared LIVE data directory. Use two addresses actually
controlled by the tester:

- **School applicant:** an `@aivancity.education` address.
- **External applicant:** a Gmail or other non-school address.

These addresses are allowed only for the explicitly named QA instance. QA
mode never sends to them. There is **no ChatGPT mailbox connector**.

On the local WSL machine:

    cd ~/multi_agent_research/agent2_realdata_benchmark
    source .venv/bin/activate
    python -m scripts.supervisor_private_qa \
      --port 8897 \
      --school-email 'YOUR_OWN_SCHOOL_EMAIL' \
      --external-email 'YOUR_OWN_PERSONAL_GMAIL'

On a locked-down VPS it must still bind **only 127.0.0.1:8897**. Connect
over an explicitly authorized SSH tunnel, not Caddy or a public firewall rule:

    ssh -N -L 8897:127.0.0.1:8897 -i ~/.ssh/ijcai_preview_ed25519 davis@31.70.172.140

For the initial acceptance, running on local WSL is simpler and has no risk
of changing the VPS service units. A future VPS QA service must use a separate
service account and private directory; do not use the existing LIVE state.

## Finding your researcher QA password (not institutional SSO)

Every start creates a NEW private directory and four NEW QA passwords.\nOld passwords stop working immediately when the previous server exits.\nThe QA console prints the actual temporary private directory path. While
the QA process is still running, open a **second WSL terminal** and read only
your own temporary secret. Example, replacing the directory with the exact
one printed by your own session:

    cat /tmp/ijcai-qa-self-acceptance-EXAMPLE/qa-admin-secrets/davis.joseph_at_aivancity.education.txt

The new QA runner also prints this safe `cat` command directly (never the
password). The file is local, mode 0600 and usable only until the process
stops. Use it with `davis.joseph@aivancity.education` in the private staff
login; change the temporary password at first sign-in. Do **not** try a
Microsoft Entra password, a QA student password or an older LIVE secret.
An unauthenticated `/control/api/me` response of HTTP 409 is normal.
For Wiam, Sara and the supervisor, each has an independently generated QA
secret. Give each owner only their own secret using a secure channel; never
post credentials in chat, a shared log or GitHub.

## Duplicate questionnaire behavior and identity separation

Every accepted questionnaire submission is recorded in a private submission
audit, but the candidates table is UNIQUE by case-insensitive normalized
email. A repeated click or new submission with the same email produces the
**same candidate_id** and an incremented application_count, never a second
candidate profile or another invitation. That candidate ID is an internal
staff identifier, not a verified Aivancity student number and not yet a
pseudonymous RCT participant ID. A study participant ID is created only
later, after an approved invitation and screening/registration.
Public questionnaire responses do not reveal candidate IDs; this prevents
account enumeration.

## Two concurrent browser roles

1. Open `http://127.0.0.1:8897/interest/school` and
   `http://127.0.0.1:8897/interest/external` in student/private browser
   windows. Both questionnaire forms require **no password**. Enter only
   your two explicitly allowlisted addresses and acknowledge that this is
   a rehearsal, **not** real consent. The two submissions create separate
   pending applicant records, not participants.
2. Open `http://127.0.0.1:8897/control/` in another browser context and
   sign in with the institutional researcher email (e.g. your own researcher
   account identity) and the **QA password**, not your Aivancity SSO or
   LIVE password. The console prints the mode-0700 local directory
   containing four individual 0600 QA credential files. Read your own
   file privately, never paste it in a chat; change the QA password.
   Wiam, Sara and Yaacoub have separate QA identities, and only each
   intended owner should receive their own test credentials.
3. Approve the two applicant rows in the researcher dashboard (this still
   sends no email). Open `http://127.0.0.1:8897/control/qa/` and click
   **Issue all approved QA links**. One authenticated action generates a
   distinct private link for each not-yet-issued approved test candidate
   (at most the two permitted test addresses), without sending email.
   Each created link is shown only in the authenticated research browser.
   The single-ID issuance form remains available for targeted tests.
   Previously prepared links are never regenerated; the link tokens are
   one-time confidential access credentials. Never publish any token.
   Student identities do not choose an arm.
4. In the student's browser context, open the test link. The actual study
   portal exercises bilingual information, test-only consent flow, screening,
   student registration, BKT estimation, three RCT arms, interventions and
   session milestones. In the researcher browser context refresh the
   dashboard, open the student row, and inspect the scored-response
   X-axis versus concept BKT mastery (0 to 1). Use separate cookie contexts
   rather than having the staff sign-in override the student's session.
5. Stop the QA process with Ctrl-C. The entire temporary QA database,
   identities, personally identifying test address records and test passwords
   are removed. Do not use this setup to test multi-day persistence; use
   existing hermetic session/resumption test suites for that.

## Friendly bilingual questionnaire and participation message

Both private QA and approved public intake page implementations now offer
instant English/French switching, including all headings, explanatory
paragraphs, checkbox text, success/error messages and buttons. The choice
switches only the display language and does not erase entered data.
The student forms require no username or password.

The copy encourages independent participation without generative AI tools,
explains that the number of correct quiz answers does not determine the
participant's grade, and asks learners to enjoy the experience. This is
participant-facing **draft source copy until independently reviewed and
signed**; the QA form prominently states that draft material is not valid
research consent. The genuine public form still requires independently
signed EN/FR recruitment privacy PDFs. The supervisor personally distributes
the questionnaire URL, never the application.

## What this does NOT test or authorize

- Student ID is not a verified school identity provider login; the current
  production student path is *private token plus screening/registration*.
  Capturing or validating a real university-issued ID requires explicit
  review of the ID source, data minimization, privacy notice and verification.
- No emailed private links are sent by the QA app. The live provider-neutral
  Graph/Gmail router is already implemented and covered by offline tests.
  A real sender/recipient canary needs the mailbox owner's explicit
  OAuth/Exchange permissions, the configured confidential credential vault,
  and scoped sender policy. Do not use someone else's mailbox by relying
  on your own Microsoft account login.
- A Microsoft personal account with a Gmail login alias is **not necessarily
  an Outlook mailbox**. Verify an actual Graph-accessible mail account. For
  sending from your Gmail inbox use the Gmail API with delegated
  `gmail.send` instead.
- Wiam/Sara can be configured as separate signed Graph sender routes only
  after their own permission and any required Entra/Exchange administrator
  approval. They remain researchers in the application regardless of which
  mailbox is chosen. Only the supervisor sends the questionnaire links.
- Genuine real-participant enrollment, public LIVE routes and research mail
  sending require authentic institutionally verified approvals. The 14-gate
  evidence index, 16 signed PDF categories, content signatures, signed mailbox
  permissions, final release commit, DNS/TLS and independent operational
  acceptance must all be satisfied. Fake declarations may remain PENDING but
  cannot grant those permissions.

Official provider references:

- https://learn.microsoft.com/en-us/graph/api/user-sendmail
- https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send

## One harmless real email to yourself (owner-side OAuth canary)

This is **separate** from questionnaire invitations, LIVE service startup and
institutional release signatures. It sends only one generic, non-research
test message from the authenticated mailbox **to that same mailbox**, never
on behalf of another person. The sender must first perform the documented
local OAuth flow in `LIVE_PROVIDER_AND_DOCUMENT_RUNBOOK.md`; there is no
ChatGPT account connection. Do not use your school colleague's mailbox.

For a Gmail owner, register and authorize a Google OAuth client with only
`gmail.send`; for a personal Outlook mailbox, use delegated Graph `Mail.Send`.
A Gmail alias for Microsoft sign-in is **not** a Graph Outlook mailbox.
The Google and Microsoft administrative actions have to be performed by
their actual owners and, where relevant, their institutional admins.

After the owner-only OAuth refresh grant has been safely stored and the
Fernet key exists in a separate protected local directory, run from the
exact checked-out repository (replace paths/client ID locally, not in chat):

    python -m scripts.supervisor_mail_owner_canary \
      --provider gmail_delegated \
      --sender YOUR_OWN_GMAIL \
      --client-id YOUR_REGISTERED_GOOGLE_OAUTH_CLIENT_ID \
      --vault-dir "$HOME/.ijcai_oauth_private/vault" \
      --vault-key-file "$HOME/.ijcai_oauth_private/mail.key" \
      --receipt-file "$HOME/.ijcai_oauth_private/mail-canary-first.json"

That is an OFFLINE vault/identity preflight; **no email is sent**.
To send exactly one owner-to-self test message, add
`--send --confirm-own-mailbox` to the same command using a *new,
nonexistent* receipt file. Never blindly rerun after a timeout:
the 0600 receipt intentionally blocks uncertain duplicate sends.
A success is provider acceptance only; inspect the Sent Items and actual
inbox independently. The command never sends an invitation token,
questionnaire, participant PII, recruitment material or research data.

For `graph_delegated`, supply the genuine Outlook-hosted mailbox and
Microsoft app client ID, plus `--tenant consumers` for a personal
Microsoft account. DO NOT specify a `@gmail.com` Microsoft sign-in alias
as a Graph mail sender. Neither delegated canary supports Microsoft Graph
application-only Send As; that requires separate approved tenant/Exchange
mailbox scoping and the LIVE signed sender router.

## Automatic checks

    python -m pytest -q tests/test_supervisor_private_qa.py tests/test_supervisor_mail_owner_canary.py tests/test_supervisor_questionnaire_copy.py

GitHub CI also runs the candidate's trace oracle, Chromium study journeys and
offline release tests. A green source CI result is not proof that the user's
actual VPS or external OAuth sender is configured.
