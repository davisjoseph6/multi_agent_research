# Production recruitment and researcher administration — release handoff

**Status:** implementation candidate; **NOT a live-human deployment**. The
currently running VPS remains staging (student enrollment, public interest
forms, and automated email disabled). Do not connect this work to production
until the independently signed release and mailbox/domain infrastructure are
verified. The existing /study/ protected preview and anonymized BKT monitor
remain preserved.

## Researcher roles and passwords

Four named identities are allowlisted:

- `wiam.belouard@aivancity.education` (researcher)
- `sara.elkardi@aivancity.education` (researcher)
- `davis.joseph@aivancity.education` (researcher)
- `yaacoub@aivancity.ai` (supervisor)

The `supervisor_recruitment_cli` creates cryptographically independent
temporary passwords, one per person, into mode-0600 private files in an
existing mode-0700 directory. It never prints secrets. Staff securely deliver
individual passwords out-of-band and delete the initial files after handoff.
All staff must change their temporary passwords at first login. Login uses
one-hour hashed sessions, CSRF tokens, PBKDF2 password hashes and timed lockout.
Never commit credentials or copy them into the browser test runner, terminal
chat logs, or shared email threads. Add account recovery, second-factor
authentication, and independently tested off-boarding before large-scale use.

## Isolated technical architecture

Existing services are unchanged:

- `/study/` on the separate study process (staging / 127.0.0.1:8788)
- read-only, pseudonymous BKT on 127.0.0.1:8790 via SSH tunnel
- original operator preview on 127.0.0.1:8077
- existing research and contact SQLite state under
  `/var/lib/ijcai-supervisor-staging`

New private control plane (disabled until opt-in installation):

- `/control/` dashboard and email/password sign-in, including registered
  identity/contact join, mastery curves, and precision timing metrics
- `/interest/school` and `/interest/external` bilingual forms, absent in
  staging, only present after signed LIVE configuration
- separate private `supervisor_recruitment.sqlite3`, not a public GitHub file
- distinct loopback-only preview port **127.0.0.1:8791**
- `ops/supervisor/enable_recruitment_admin_preview.sh` installs only this
  isolated staging preview and verifies anonymous PII access is blocked,
  public interest forms return HTTP 404, and the existing study is untouched

A reviewer can connect from a separately authorized SSH account:
`ssh -N -L 8791:127.0.0.1:8791 <authorized-user>@<VPS-host>`,
then open `http://127.0.0.1:8791/control/`. Do not publicize this preview.

## Required signed and externally verified production inputs

1. **Formal release evidence:** a separate private 14/14 evidence index; a
   legitimate, independently validated institutional signature and trusted
   key; exact signed Git commit and approved experimental protocol/ethics/
   privacy/content artifacts. Read the existing
   `ops/supervisor/VPS_RELEASE_RUNBOOK.md`. User confirmation is not the
   required cryptographically verifiable evidence.
2. **Bilingual candidate privacy information:** final approved PDF in EN
   and FR, each signed by the institution. Configure
   `SUPERVISOR_RECRUITMENT_NOTICE_EN`, `_FR` and corresponding
   `SUPERVISOR_RECRUITMENT_NOTICE_SIGNATURE_EN`, `_FR`. The intake app
   validates signatures against `SUPERVISOR_INSTITUTION_PUBLIC_KEY`;
   every applicant submission stores the actual signed PDF SHA-256.
3. **Non-demo DNS and HTTPS:** configure institutionally owned production
   hostname(s), valid TLS, Caddy host header restrictions, anti-CSRF proxy
   headers, secure cookies, appropriate security monitoring, and a segregated
   *production* data directory. Do **not** use `demo.selfhealing-edu.fr`
   for real human participation. The app requires
   `SUPERVISOR_RECRUITMENT_HOST` and `SUPERVISOR_VPS_HOST` pointing to
   approved canonical non-demo names.
4. **Microsoft Exchange/Outlook:** Entra ID tenant ID, application/client ID
   and private application secret (or migrate to certificate credentials).
   The sender uses Graph `/users/{mailbox}/sendMail` with an unattended
   application token; permission `Mail.Send` **must be limited by
   Exchange Online application RBAC** to the explicitly authorized outbound
   mailbox. This restriction and administrator consent must be confirmed
   by IT. Configure `SUPERVISOR_MAIL_TRANSPORT=microsoft_graph`,
   `SUPERVISOR_GRAPH_TENANT_ID`, `SUPERVISOR_GRAPH_CLIENT_ID`,
   `SUPERVISOR_GRAPH_CLIENT_SECRET` and
   `SUPERVISOR_GRAPH_SENDER_EMAIL` in private systemd environment files.
   No credentials are supplied in this repository. Graph HTTP 202 is
   *accepted for processing*, not proof of delivery.
5. **Rate limits & operations:** a private >=32-byte
   `SUPERVISOR_INTAKE_RATE_SECRET`, protected database key and encrypted
   offsite backups, rehearsed restore, researcher offboarding, access audits,
   independent penetration and accessibility QA, concurrency / load tests,
   authorized DNS ownership and data-retention configuration. Keep live
   user data OUT of staging, tests and GitHub.
6. **Supervisor-only questionnaire distribution:** PI personally sends the
   two candidate questionnaire URLs. Administrators may send *study
   invitations* to selected or all **approved applicants** after explicit
   authorization, but may not automatically send recruitment questionnaires.

## Protocol semantics and nontrivial caveats

- Intake form expressions of interest are **not study enrollment or
  informed participation consent**. Subsequent student registration must
  still pass signed information, eligibility, and consent gates.
- The original three-arm participant allocation and intervention policy are
  unchanged. Student entry is private token/cookie, not student password.
  Bad/missing tokens never reveal the interactive study content, but a static
  HTTP document can be returned to deliver the JavaScript verifier.
- In LIVE only, an **unfinished active session** expires after 7 days without
  learner progress; planned 3–5-day inter-session breaks and DONE are
  exempt. Existing answers remain intact. The old token is revoked.
- A new expression of interest from the same email is logged in
  `candidate_submissions`. **IMPORTANT NOT IMPLEMENTED: automatically
  re-enrolling the same former student**: contact and invitation email
  uniqueness still prevent an identical email receiving a new randomized
  student identity. The PI must approve repeat-participant policy and
  whether to preserve or reset the original allocation. Do not delete
  history or bypass identity checks to make this work.
- The manual 4-day inactivity encouragement and automatic 3-day opt-in
  policy use a private durable `pii.inactivity_outbox`; Graph uncertain
  results are never retried automatically. The existing scheduled visit
  reminders remain separate.
- **A production timer is not installed.** An authorized ops engineer
  must define and validate a durable scheduler run via
  `scripts.supervisor_vps_daily.py --grace-hours N --send`
  under the signed-live environment and a separately audited user.
  Toggling the dashboard preference without a verified scheduler does
  not send any emails.
- The BKT mastery curve remains **observational**. Neither student email
  nor research dashboard data changes treatment, intervention triggers,
  randomization or assessment results.
- User requested all timing intervals as decimals. New private admin API
  distinguishes **calendar time between consecutive answers**
  (including breaks and interventions) from item response latency.
- The candidate/invite ledger uses **one private delivery attempt** per
  candidate. An ambiguous timeout requires staff review in Outlook Sent
  Items before a re-send, to avoid duplicate private credentials.
- Protected admin endpoints join contact PII only in the authorized
  control-plane process. Do not mount them in the public study participant
  or pseudonymous BKT apps. The new preview may share a staging state
  directory only for *synthetic* preview data.

## Deployment decision and automated tests

Development branch:
`feature/ijcai2027-private-recruitment-admin-scaffold-20261113`.

The expected base is:
`research/ijcai2027-supervisor-consent-gdpr-20261112`.

CI: Supervisor 465-step reference oracle, Flask/SQLite test suite,
headless Chromium three-arm English/French walk-through, Python and JS
syntax validation, and the RCT rehearsal suite.

Do not merge/release if any required gate fails. Test the precise commit,
then obtain independent acceptance from the PI, privacy/infrastructure
reviewers and authorized IT. **No human invitation, identifiable dataset,
Graph email, domain flip, or LIVE-mode service is authorized by code alone.**
