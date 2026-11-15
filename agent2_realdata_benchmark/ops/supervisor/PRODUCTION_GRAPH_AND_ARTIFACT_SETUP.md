# Production readiness: draft placeholders and Microsoft Graph sender

**This is an operator runbook, NOT approval or a production release.**
The currently deployed study, researcher monitor, and recruitment dashboard
remain **STAGING** at the exact verified Git commit. Do not enable real-human
enrollment, public intake, or outbound mail until the independent review is
recorded and the cryptographic release checks pass.

## A. Generate safely replaceable draft review material

From a checkout of the exact candidate revision:

```bash
cd /path/to/multi_agent_research/agent2_realdata_benchmark
SHA="$(git rev-parse HEAD)"
umask 077
mkdir -p "$HOME/private-ijcai-reviews"
chmod 0700 "$HOME/private-ijcai-reviews"
python3 -m scripts.supervisor_production_draft_inventory \
  --scaffold "$HOME/private-ijcai-reviews/candidate-${SHA:0:12}" --commit "$SHA"
python3 -m scripts.supervisor_production_draft_inventory \
  --check "$HOME/private-ijcai-reviews/candidate-${SHA:0:12}"
```

The check must report zero approved gates and no verified release. The
scaffold creates **private review placeholders**, not genuine signatures or
legal notices. It does not create fake PDF evidence and deliberately leaves
mail and enrollment disabled. The parent directory must exist and not be a
symlink. Store the drafts outside the public Git checkout and off the VPS's
live data path.

When actual documents arrive:

1. Replace each `evidence/*.DRAFT.md` with a real reviewed PDF
   (a draft markdown file is never evidence); update the matching path,
   SHA-256, required role, actual reviewer, timezone-aware review time,
   and approval status in `evidence_index.json`. The 14 required category
   names are in `src/prototype/pilot_release_evidence_gate.py`.
2. Replace *in-repository* draft instructional text and consent Annex HTML
   with the actual reviewed versions, keeping versioning and research
   reproducibility. Obtain a **new exact Git commit** if content changes.
   Re-run `scripts.supervisor_content_approval_template` against that final
   commit; the interim pending inventory is not signed evidence.
3. The real institution/PI, using a trusted out-of-band verified signing key,
   must sign the evidence index and distinct content-review manifest.
   The signer must authenticate the independent reviews, not merely sign a
   populated JSON document. The public key cannot be self-declared by the
   application operator.
4. Put the institutionally approved English and French candidate privacy
   notices into separate final PDFs. Obtain signatures over the exact PDFs.
   The recruitment WSGI checks both signatures with OpenSSL; replacing a PDF
   afterward invalidates the signature.
5. Confirm institutional DNS/TLS, distinct LIVE state under
   `/var/lib/ijcai-supervisor-live`, mailbox scope, backups/restore,
   independent load/security/accessibility checks, all required secrets, and
   the exact signed source commit. Only then should a separate LIVE service
   be configured and the automated release gates executed.

**Important:** Swapping a file in a live release without updating hashes,
signature(s) and the exact approval commit is NOT supported. This protects
scientific reproducibility and the participants' signed information.

## B. Connect davis.joseph@aivancity.education through Microsoft Graph

The current `GraphMailSender` is an unattended **client-credentials**
implementation using an Entra tenant ID, application ID, client secret and
sending mailbox. It does **not** log in with the mailbox's personal
password, use SMTP AUTH, require a ChatGPT plugin, or use a delegated
`/me/sendMail` token.

1. In **https://entra.microsoft.com/**, sign in with
   `davis.joseph@aivancity.education`. Confirm the school **work/school
   tenant** is selected. Your own Outlook inbox access does not by itself
   grant app-registration/tenant/Exchange admin rights.
2. Under **Entra ID → App registrations → New registration**, create a
   dedicated app (e.g., `IJCAI2027-StudyMail`), single organizational
   directory only. Record **Directory (tenant) ID** and
   **Application (client) ID**. Do not register a public callback URL:
   this particular code uses no interactive OAuth redirect.
3. Have authorized Microsoft 365/Exchange IT assign only the necessary
   **application Mail.Send** privilege, restricted to
   `davis.joseph@aivancity.education` via Exchange Online
   **RBAC for Applications**. Granting unscoped Graph Application
   `Mail.Send` in Entra can give access to every mailbox and is NOT
   narrowed simply by adding a narrower independent Exchange RBAC grant.
   IT must review *both* Entra-wide and Exchange-scoped grants and remove
   unintended broad rights; do not self-grant tenant-wide access.
4. IT should create a resource/management scope for exactly the approved
   mailbox, register the Entra service principal in Exchange Online,
   assign `Application Mail.Send` to the scoped principal, then use
   `Test-ServicePrincipalAuthorization -Identity <service-principal-id>
   -Resource davis.joseph@aivancity.education`. They must also test a
   different mailbox OUT of scope and independently audit Entra-wide grants.
   Microsoft notes that cache propagation can take 30 minutes–2 hours.
5. Under **App registrations → your app → Certificates & secrets**, choose
   a client secret for the currently implemented transport, record its
   **Value once** inside the institutionally managed secret vault, and
   plan rotation/expiry alerts. Microsoft recommends a **certificate or
   federated credential for production**; switching the application to
   certificate authentication requires a separate code change and testing.
6. In the final root-owned LIVE environment (NOT in a Git commit or chat),
   the approved operator configures:
   `SUPERVISOR_MAIL_TRANSPORT=microsoft_graph`,
   `SUPERVISOR_GRAPH_TENANT_ID`,
   `SUPERVISOR_GRAPH_CLIENT_ID`,
   `SUPERVISOR_GRAPH_CLIENT_SECRET`,
   `SUPERVISOR_GRAPH_SENDER_EMAIL=davis.joseph@aivancity.education`.
   These secrets must be readable only by the dedicated LIVE service account.
7. Test with **one explicitly authorized nonparticipant test mailbox**,
   after the signed-live gate is satisfied. Verify Graph response code 202
   and the recipient's actual inbox/Sent Items. A 202 response means
   *accepted for processing*, NOT delivered. Exercise uncertain-outcome
   and duplicate prevention without resending learner tokens automatically.

If Entra app registration, Exchange RBAC or application mail permissions
are unavailable to your account, ask school IT to configure them. If IT
only permits **delegated Mail.Send** requiring your interactive Outlook
sign-in, the current app-only sender cannot use that token: a separate,
reviewed delegated OAuth/token-cache implementation is necessary.

Microsoft documentation:
- https://learn.microsoft.com/en-us/graph/auth-register-app-v2
- https://learn.microsoft.com/en-us/graph/api/user-sendmail
- https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac
- https://learn.microsoft.com/en-us/entra/identity-platform/how-to-add-credentials

## C. Current verification boundaries

- Private recruitment dashboard: port 8791, SSH-tunnel only, fictional staging.
- Participant portal: port 8788 through protected /study/, fictional staging.
- Researcher BKT monitor: port 8790, SSH-tunnel only.
- Original operator demo: port 8077; leave untouched.
- Four administrator identities have been provisioned in the staging ledger;
  temporary secrets must be delivered to each holder privately and removed.
- An app-only mail **source implementation** exists; Entra registration,
  granted sender scope, approved non-demo domain, signed release artifacts,
  separate LIVE deployment, backups and an independently tested restore are
  not proven by this repository or the user's last VPS logs.
- `install_live_reminder_timer.sh` exists but is deliberately unable to
  activate without a separately approved LIVE checkout and environment.

**No draft document, custom JSON, copied public key, or success of staging
CI constitutes a license to enroll actual participants.**
