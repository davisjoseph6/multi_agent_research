# RCT Production Hardening — Operator Handbook (DRAFT / NO-GO)

Branch: `feature/rct-production-hardening-20261031`.
All files in `ops/rct` are **templates**. None indicates that a server, domain, TLS certificate, expert review, or deployment exists. The existing live-enrollment release gate is preserved.

## 2026-10-31 validation update — randomized block and browser QA

The first user-run 30-participant synthetic test completed **30/30** fictional journeys,
with **11,130** test-client requests, **0** pending actions, 8 worker threads and
maximum request latency approximately **5.86 seconds**. This is only a snapshot
on the user's workstation; no production-capacity assertion follows.

An initial three-participant focused test failed because the *load harness*
incorrectly required all three arms to appear among the first three
assignments. Since allocation uses randomized blocks of 6 or 9, a partially
filled block need not be balanced. The harness and its test now validate
the overall counts and require balance only in complete allocation blocks.
The controller and allocation logic were **not** changed.

The revised harness also records p95 and maximum latency by API route to
identify any unusual contention or planner delays. Previous report files
must remain untouched; use fresh output names.

### Run the latest tests from the repository benchmark folder

```bash
python -m pytest -q tests/test_rct_candidate.py tests/test_rct_operational_load.py tests/test_rct_content_review_packet.py
python -m scripts.rct_operational_load --participants 30 --workers 8 --out /tmp/rct_load_30_02.json
python -m scripts.rct_content_review_packet --out-dir /tmp/rct_review_worklists_01
python -m pytest -q
```

The review packet writes 95 item worklist entries and 32 resource worklist
entries with **empty expert assessment fields** and source hashes. It does not
modify the source content, resolve any expert assessment, or make the
fatigue instrument valid.

### Optional Chromium-engine localhost test

```bash
python -m pip install -r ops/rct/requirements-browser-qa.txt
python -m playwright install chromium
python -m scripts.rct_browser_qa --out /tmp/rct_chromium_01.json
```

This browser check exercises a fictional participant's invitation,
consent, assessment, first answer, heading keyboard focus, browser reload,
session persistence and mobile-width layout with a real Chromium engine
over local HTTP. **No public network, TLS, physical tablet/phone,
screen reader, or independent security assessor is involved.**

If Chromium installation is prevented by OS permissions or missing Linux
libraries, preserve the error; do not make unsupported deployment claims.
Continue to use the in-process test results as rehearsal evidence, not
as proof that the browser check passed.

Review `ops/rct/MEASUREMENT_DECISION_REQUIRED.md` before selecting NASA-TLX
(workload) or a validated fatigue-specific scale. The existing 1–5 response
code is not compatible with unmodified NASA-TLX administration.

---

## 2026-10-31 extension — test results, browser dependency, recovery and Raw-TLX draft

Verified by the researcher on the prior commit (not rerun yet after this extension):
- Focused test suite: **46 passed**; full suite **1271 passed**.
- Fictional 30-person/8-thread load: **30 complete**, **10 per arm**, **11130 HTTP test-client calls**, **0 pending**. Request p95 **68.067 ms**, maximum **6845.083 ms**, including a **6837.752 ms** action request. These are in-process measurements, not production performance.
- Chromium installation: succeeded, but test **failed before starting** because Linux lacked \`libnspr4.so\`. This is a host dependency, not an RCT controller test failure.
- Content review packet: generated successfully, but **95 questions and 32 resources remain unreviewed**.

### Fix Chromium Linux shared libraries

Official supported method (requires permission to install OS packages):

\`\`\`bash
python -m playwright install-deps chromium
python -m scripts.rct_browser_qa --out /tmp/rct_chromium_02.json
\`\`\`

On Ubuntu/Debian without administrative privileges, an **optional developer-QA-only** wrapper attempts to extract missing distro-packaged libraries (including \`libnspr4\`) into the user's cache. It does not install system packages or enable live enrollment:

\`\`\`bash
bash ops/rct/qa_browser_userlibs.sh python -m scripts.rct_browser_qa --out /tmp/rct_chromium_02.json
\`\`\`

The wrapper requires working \`apt-get download\` package indexes/network and can legitimately fail if the distro lacks compatible packages. If so, record \`ldd\` missing-library results, and ask the machine's administrator to install supported dependencies. Do not disable browser security controls to work around missing libraries.

### Full-browser and recovery tests (fictional only)

\`\`\`bash
bash ops/rct/qa_browser_userlibs.sh python -m scripts.rct_browser_qa --full --out /tmp/rct_chromium_full_01.json
python -m scripts.rct_restore_drill --out /tmp/rct_restore_01.json
python -m pytest -q tests/test_rct_candidate.py tests/test_rct_operational_load.py tests/test_rct_content_review_packet.py tests/test_rct_restore_drill.py tests/test_rct_questionnaire_scales.py
python -m pytest -q
\`\`\`

The restore drill backs up a fictional SQLite study after an action is offered,
restores into another file, confirms the exact pending action, completes the
journey and ensures the source backup snapshot remains independent. This is
not an offsite/encrypted backup or failover test.

### NASA Raw-TLX workload draft: separate opt-in *rehearsal* variant

The default questionnaire **remains the six unvalidated five-point fatigue fixtures**.
A new *unreviewed* \`fatigue_NASA_RAW_TLX_DRAFT.json\` and
\`settings_raw_tlx_REHEARSAL.json\` demonstrate six workload ratings on a
0–100 response scale in steps of five, including the reversed performance
anchor ("good" to "poor"). Response validation and version/hash binding
apply to either 1–5 or 0–100 variants.

\`\`\`bash
bash ops/rct/qa_browser_userlibs.sh python -m scripts.rct_browser_qa --settings docs/rct_candidate_v1/settings_raw_tlx_REHEARSAL.json --full --out /tmp/rct_raw_tlx_full_01.json
\`\`\`

This is only **an implementation candidate** and does not certify official wording,
validity, permissions, scoring or protocol suitability. Raw TLX is **workload**,
not a fatigue-specific scale. No new user instrument should enter the real
trial without formal review, frozen analysis and a separate valid release gate.

---

## Status and separation of duties

- Core three-arm transactional prototype: passes locally reported 1,263 regression tests; nine fictional participants completed in earlier HTTP rehearsal.
- This branch adds a single-host WSGI/TLS reverse-proxy template and an in-process concurrent fictional rehearsal harness. New files require local verification.
- **NOT VERIFIED:** actual TLS/HTTPS, DNS, firewall, certificate renewal, host OS updates, backup destination, disk/CPU saturation, throttling and denial-of-service protection, simultaneous real browsers, responsive tablet/mobile view, WCAG 2.2 accessibility, independent security review, final item review, and validated fatigue measure.
- **NOT APPROVED:** live enrollment and real participant contact. The application must continue to refuse live startup until all five release-evidence domains and content are genuinely reviewed and authorized.

## Deployment architecture (future, never on development workstation by assumption)

An operator/institution provides a real hostname and DNS, a controlled Linux host, TLS certificate and renewal, a restricted service account, disk encryption/backup/storage policy, and organizational security approval.

```
participant browser -- HTTPS --> Nginx :443
                                  |
                                  +-- only 127.0.0.1:8077 --> Gunicorn (one process, 8 threads)
                                                                     |
                                                              Flask RCT app
                                                                     |
                                                         restricted SQLite database
```

**Why one process?** SQLite write transactions are serialized, and the candidate uses `BEGIN IMMEDIATE`; eight threads are an initial *test configuration*, not an established capacity. Capacity and concurrency limits must be determined from realistic load tests. The reverse proxy must remove/replace untrusted forwarded headers, not pass client-provided X-Forwarded-For/Proto. Bind Gunicorn to loopback only. Do not forward authorization headers to logs or analytics.

**Operational caution:** Nginx template disables access logs to reduce personal-data exposure, but operators still need privacy-reviewed security and health monitoring. Avoid storing identifiable or bearer-token data in logs. Deployment must enforce request throttling, abuse monitoring, firewall ingress control, explicit administrator access, log retention, backups and incident response. Do not expose `serve` (Flask development server) or an administrative export endpoint to the public.

## Requirements before actual deployment

1. Decide authoritative host, domain, vendor, administrator, data processor/hosting location and approved cross-border data flows; record contract and institutional security requirements.
2. Obtain reviewed certificate; test TLS handshake, hostname validation, renewal, HTTP-to-HTTPS redirects, HSTS; test externally from *authorized* network.
3. Use restricted Linux identity; create `/etc/ijcai-rct/rct.env`, reviewed live settings, and database directory with ownership and permissions; ensure only the service identity can read study DB and config.
4. Install reproducibly locked Python dependencies in a dedicated environment. `requirements-serving.txt` is **version-ranged, not a lockfile**; produce a reviewed hash-pinned lock before deployment.
5. Install the template systemd service and Nginx site only with administrator approval, review `nginx -t` and service security settings, and ensure restricted filesystem/egress behavior.
6. Confirm a fresh database has been initialized from the correct candidate source/content/settings fingerprints. Never migrate an existing rehearsal DB to live and never use unapproved draft content in live mode.
7. Run the complete third-party release review and preflight: the **live engine intentionally blocks startup until evidence is authentic**. Do not edit a release evidence template merely to force it past the gate.
8. Set up off-host encrypted backups, scheduled restoration rehearsals, checksums, alerting, key rotation, documented retention and deletion requests, and a stop/enrollment suspension procedure.
9. Conduct realistic concurrent browser test, including network interruption, tab close/reopen, resume, duplicate submits, slow connection, mid-session server restart, simultaneous block assignment, and failed/partial backups. Treat failed steps as deployment blockers.
10. Obtain independent security/privacy review (no self-attestation); complete WCAG 2.2 AA audit and documented screen reader and keyboard tests. The UI currently uses form labels, live status and focus indicators, but these are **not accessibility certification**.

## Commands for safe fictional rehearsal

From `agent2_realdata_benchmark` with the project virtual environment:

```bash
python -m pytest -q tests/test_rct_candidate.py tests/test_rct_operational_load.py
python -m scripts.rct_operational_load --participants 30 --workers 8 --out /tmp/rct_load_30_01.json
python -m pytest -q
```

If CPU or time pressure makes 30 × 55-question workflows expensive, start with three participants; increase only after the load harness passes and capture hardware details, CPU/memory and SQLite lock errors. The numbers above exercise **Flask in-process test clients**, NOT actual TLS, Gunicorn, mobile browsers, production latency or scale.

## Real browser / accessibility verification record (to fill with genuine evidence)

| Test | Browser and version | Device / assistive tech | Result | Evidence reference |
|---|---|---|---|---|
| Full A/B/C journey | Pending | Pending | NOT TESTED | — |
| Keyboard-only tab order, inputs and focus | Pending | Pending | NOT TESTED | — |
| Screen reader questions, forms and notice updates | Pending | Pending | NOT TESTED | — |
| Zoom 200%/400%, text scaling, landscape/portrait | Pending | Pending | NOT TESTED | — |
| Narrow 320px viewport, no clipping | Pending | Pending | NOT TESTED | — |
| Contrast, keyboard target sizes, error recovery | Pending | Pending | NOT TESTED | — |
| Disconnect, refresh and resume without double answer | Pending | Pending | NOT TESTED | — |
| TLS certificate/renewal/redirect, header-proxy boundary | Pending | Pending | NOT TESTED | — |

## Actual fatigue instrument / content obligations

Existing `fatigue_REHEARSAL_ONLY.json` contains **six invented rehearsal prompts and a five-point agreement scale**, marked `REHEARSAL_ONLY_UNVALIDATED_6_ITEMS_V1`. It is NOT NASA-TLX and is not a validated fatigue instrument. NASA-TLX concerns *subjective workload* (mental, physical, temporal demands; performance, effort, frustration). If NASA-TLX is selected by the responsible study team, the instrument **must** be administered/scored according to an agreed, correctly attributed method and implementation contract. Do not silently swap instruments because the existing engine hardcodes six 1–5 responses. Such a change requires code, tests, protocol amendment, candidate re-fingerprint and measurement review.

Current candidate content: 95 total question items (16 pretest, 55 practice, 16 posttest, eight recovery DROP_2) and 32 resource texts (eight concepts × four recovery actions) remain **unreviewed**. Independently record each item's difficulty, keyed answer, concept/Bloom coverage, clarity, fairness and conflict with pretest/posttest leakage. Record each resource's correctness, pedagogical suitability, safe text, provenance, and explicit action semantics. Record reviewer, evidence/date and a genuine decision; never self-fill approvals.

Before the live pilot, decide whether the primary scientific measure is learning, fatigue, subjective workload, or a combination, and specify the full item text, response scale, scoring, licensed/attributed source and validated interpretation. The prototype's 6-item response interface is **not** automatically compatible with NASA-TLX even though both have six items.

## Completion definition

Software is *production readiness verified* only if actual host/TLS operations, independent security and accessibility checks, realistic load and failure recovery, approved final content/instrument, and a successful release-bound preflight are all documented. Until then, show **software rehearsal complete; production readiness NOT VERIFIED**.

The milestone may proceed without anyone currently being able to approve the trial; these are research and infrastructure preparation tasks, not enrollment.
