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
   sends no email). Open `http://127.0.0.1:8897/control/qa/`, enter each
   approved candidate ID and issue each one **once**. The server shows a
   private QA invitation link in the authenticated researcher browser.
   Never publish the fragment token. Student identities do not choose an arm.
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

## Automatic checks

    python -m pytest -q tests/test_supervisor_private_qa.py

GitHub CI also runs the candidate's trace oracle, Chromium study journeys and
offline release tests. A green source CI result is not proof that the user's
actual VPS or external OAuth sender is configured.
