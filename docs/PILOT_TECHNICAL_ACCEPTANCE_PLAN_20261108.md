# Technical acceptance plan for an authorized IJCAI three-arm pilot

**Version 0.1 — 2026-11-08; NO HUMAN PARTICIPANTS PERMITTED.**
**Environment:** existing `demo.selfhealing-edu.fr` is a fictional-only operator rehearsal. The human pilot requires separate approved data storage, code candidate, data controller and written authorization.

## A. Infrastructure and change control

- Capture anonymized evidence of Ubuntu LTS and patch level, running services, deployment commit, domain/TLS expiry and renewal, IONOS security group/firewall, public SSH restrictions, listening TCP sockets, time synchronization, low-privilege service account, Caddy basic auth, certificate/secret locations. Do not collect passwords or seed tokens.
- Public TCP only 80/443 + restricted SSH 22; Gunicorn bind only `127.0.0.1:8077`. Disable unnecessary IONOS panel ports, monitor capacity.
- Keep HTTPS Caddy configuration and `systemd` unit reviewed and versioned; lock dependencies with hashes after vulnerability review. Use SSH keys, distinct operator credentials and least privilege. Rotate disclosed/expired fictional invitations.
- Separate demo/pilot staging/human-data environments and identities; restrict production deploy to approved signed commits. A TLS certificate is not a penetration test or research approval.
- Freeze NTP/time zone (UTC storage, study-local display), host/domain and recovery-contact roster.

## B. Load and concurrency acceptance on controlled synthetic environment

A previous in-process 30-participant Flask test-client simulation is NOT actual remote HTTPS concurrency testing. Define approved concurrent active users based on physical supervised rooms (90 recruited does not mean 90 simultaneously active).

Create a *separate* synthetic staging DB with disposable invitations. Apply realistic complete pretest/practice/fatigue/posttest and duplicate retries for A/B/C. Measure from an independent client/network with actual HTTPS:
1. 1 simultaneous fictional user (baseline latency);
2. 5, 10, 20 and 30 concurrent fictional users (subject to server resource and institutional agreement);
3. spike/intermittent connectivity and worker restart; optionally larger stress test after safe abort thresholds agreed.
Record per-endpoint p50/p95/p99 and max latency, error rate, SQLite `busy/locked` frequency, retry/idempotency, CPU, resident RAM, disk, network, TLS, on-call alerts. Predeclare capacity/error/latency and abort thresholds **before** test. Stop if server overload risks collateral effects. Do not aim a stress tester at the active demo or real data without explicit authorized window.

## C. Device/browser/accessibility matrix

- Chromium, Firefox, Safari (when available); desktop Windows/Linux/macOS; real Android/iOS at common viewport sizes, including 320/375px and 200/400% zoom.
- Keyboard-only navigation, focus after dynamic updates, large text, screen reader at least NVDA/VoiceOver, language tags, contrast, errors/labels, slider accessible numeric alternative, session refresh/resume and browser back/retry.
- Target **WCAG 2.2 AA** with qualified independent audit and documented defect closure. Automated axe/Lighthouse and Playwright are only supplements, not substitutes for human assistive-tech testing.
- Check slow 3G, lost connection mid-response, duplicate form submits, invalid/expired invitation, different browser device, disconnection and recovery.

## D. Security review (independent)

Request third-party review with **OWASP ASVS 5.0.0** as basis and test plan for authorization and session boundaries; role/identity access; host/proxy spoofing; HTTP request smuggling where relevant; CSRF/origin; CORS; injection; XSS; timing, brute force and rate limiting; error disclosure; token storage in browser `sessionStorage`; invitation expiry/replay/rotation; public enrollment 403; certificate and secret lifecycle; dependency vulnerabilities; supply chain; log privacy; database encryption and file permissions; TLS renewal, backup/restore, and incident response. Record severity, owner, fix commit, independent retest, residual risk.

Current Caddy rules use **Basic Auth on frontend** and **bearer invitation on API** because both use `Authorization`; independent reviewers must understand and challenge this model, not assume Basic Auth protects the API. Caddy reverse-proxy default handles forwarded headers to prevent spoofing; avoid gratuitous trusted-proxy expansion and verify behavior. Keep no actual student records on this demo.

## E. Operational recovery

- Agree institutional RPO/RTO targets and incident contact tree; encryption key/credential custody.
- Use SQLite online backup API rather than `cp` of an active WAL-mode DB. Encrypt backup; verify copy by `PRAGMA integrity_check`, participant/action counts and sampled synthetic resume.
- Off-server and off-account retention with restricted access and deletion policy; documented successful restore onto separate disposable VPS/test workspace; backup schedule, alerts, encryption key recovery, documented rollout/rollback and patch method.
- Drill: terminated Gunicorn worker, VPS restart, DNS/TLS renewal failure, disk full, SQLite contention, loss of invitation JSON, revoked credential, expired tokens, data loss, failed restore, loss of internet during saved answer.
- Because there is **no funded/verified off-server backup configuration described**, current hosting is NOT ready for real participants.

## F. Pilot-specific protocol enforcement

A new versioned human candidate needs prior, explicit study consent; eligibility and duplicate-enrollment checks; concealed randomization 1:1:1; scheduler-authorized **three supervised visits 3–5 days apart**; pre/post M-VAS at each visit (6 observations); 16-question pre/post tests; 20+20+15 practice; exposure/time/resource logging; isolation of three arms; withdrawal and missing-value semantics; audit trail; signed content and protocol hashes; human release gate.

The deployed demo presently has one six-item rehearsal fatigue response after each session, **NOT** the proposed six single-item M-VAS timepoints. This cannot be fixed by changing the label or swapping a JSON fixture; adjust engine state machine, content validator, API and UI on a separate versioned candidate only after approval.

## G. Evidence package and owner placeholders

| Deliverable | Independent owner/signature | Evidence to archive |
|---|---|---|
| Hosting/TLS/firewall hardening | [Ops + institution] | Config hashes, public listeners, renewal and scan evidence |
| Performance/concurrency | [QA/performance engineer] | Traffic profile, raw metrics, p95/p99, errors, 95th-percentile host utilization, abort/accept conditions |
| WCAG 2.2 AA | [Independent accessibility specialist] | Manual keyboard+assistive-tech matrix, fixes and retest |
| OWASP ASVS 5.0.0 security | [Independent security reviewer] | Threat model, findings, remediation, signed residual-risk acceptance |
| Backups/restore | [Ops + DPO] | Encrypted off-server proof, integrity check, successful isolated restore, RPO/RTO |
| Content and instrument | [Subject expert + psychometrician] | 127-row reviewer register, content hashes, signed M-VAS validation |
| Study governance | [PI/institution/ethics/DPO] | Approved protocol+SAP, recruitment, consent, retention, student rights |
| Software release | [Engineer + separate approver] | Full test logs, code hash, release manifest, no real-enrollment bypass |

## Independent references

- OWASP ASVS 5.0.0: https://asvs.owasp.org/
- W3C WCAG 2.2: https://www.w3.org/TR/WCAG22/
- Caddy forwarded header defaults: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- Official guidance for pilots: https://www.bmj.com/content/355/bmj.i5239
