# IJCAI 2027 pilot: executable engineering / scientific readiness sequence

**Date:** 2026-11-10. **State:** BLOCKED for real students. No changes made to the existing IONOS fictional operator demonstration. This document is a *work plan* and test-contract, not a completed authorization or a deployment instruction for existing systems.

## Verified fictional baseline and limitations

- User-reported local WSL checkout `77e659a`: **1,388/1,388 tests passed**, clean.
- Six 30-person/240-POMCP-simulation virtual **three-visit** native-versus-single-process-FIFO runs passed. Five-worker median-run p99 improved from 1566.579 to 167.519ms; zero FIFO actions >1s in the three runs. Median action increased from 13.113 to 65.421ms; one FIFO run took 82.403s vs 40.683s native. A separate two-worker comparison improved p99 441.240→65.642ms with lower overall throughput (median 43.913s native, 59.986s FIFO). No conclusion about HTTPS or multiple processes.
- The queue is `threading.Condition` **per Python store instance and process**; multiple WSGI processes do not share its tickets.
- The "real" staging engine and operator VPS still carry a **six-item post-session fictional questionnaire**, while the proposed future pilot uses **six total single-item M-VAS timepoints**. This needs a separate, versioned candidate, not in-place migration or label editing.
- All 14 release evidence categories remain **pending**. `docs/pilot_release_evidence/MANIFEST_TEMPLATE.json` is not an approval. No authenticated human enrollment path has been approved.

## Ordered build plan, acceptance tests and decision owners

| Sequence | Deliverable | Strict engineering exit criterion | Responsible independent signoff |
|---|---|---|---|
| **0. Scientific protocol freeze** | Supervisor decision crosswalk; registered design intent; A/B/C action taxonomy, intervention resource dose, pre/post timing, consent/order, eligible population, dropout policy, 3–5-day visit intervals | Every SUP-01..SUP-14 discrepancy adjudicated; one consistent, dated protocol/SAP/content/instrument version; **no POMCP-only causal claim** for package-vs-control comparison | PI, statistician, content and measurement reviewers |
| **1. Institution/ethics/privacy determination** | Named controller and PI, competent ethics disposition, staff roles, DPO lawful basis/notice/DPIA determination, retention/deletion/incident plan; approved participant information and independent recruitment | Signed documents collected **privately**, no private source included in public Git, no personal data collected before approval | Institution, ethics authority, DPO |
| **2. Human-eligible service design review** | Separate service/domain/DB/identity mapping; deny-by-default signed release switch; server-only consent/eligibility verification, staff authentication with MFA where approved, individual assignment and concealment; no client arm selection | Negative authorization tests for all missing/expired/forged roles, invites, consent, duplicate identities and wrong arms; structured audit without PII leakage | Engineering + independent security/PI |
| **3. Study state engine** | Versioned human candidate implementing exact approved trial: 3 supervised visits, **real server time**, 16 pretest+55 practice+16 posttest, final measure instrument, missingness, visit rescheduling, accessibility | Full three-visit automated tests per arm with 3–5-day real timestamp rules; no simulated `offline_staff_authorized=True` shortcut; no changed quiz after allocation; replay-safe storage and withdrawal audit | PI, item reviewer, engineer, independent QA |
| **4. Transactional data architecture** | Clearly identify actual service **process count**, driver, database journal/locking, migration and rollback; compare single-writer controlled admission to independent row-level transactions (e.g. PostgreSQL if justified) | Multi-process and crash/kill stress preserve idempotency, order, 1:1:1 concealed allocation and immutable responses; no reliance on in-process FIFO for cross-process fairness | Independent engineer, DPO, ops |
| **5. Deployment staging** | Separate nonpublic synthetic staging with dedicated credentials; TLS/expiry, reverse proxy, host allowlist, least privilege, restricted SSH, logs/metrics, secret management, patch/dependency lock, CI artifact hashes | External browser clients connect over real HTTPS under approved load windows; operator demo and all real records untouched; rollback rehearsed | Operations + independent QA |
| **6. Safety, accessibility and performance** | OWASP ASVS threat model/independent testing, WCAG 2.2 AA keyboard/assistive tech and mobile matrix; genuine HTTP/HTTPS pacing, endpoint latency and concurrency with packet loss/retries; CPU/RAM/disk and alerts | Predetermined **owner-approved** p95/p99/error-rate/throughput and stop thresholds met; no critical security/accessibility findings; errors reproducibly classified | Independent security/accessibility/QA and ops |
| **7. Recovery and incident response** | Encrypted offsite backups with key custody, measured RPO/RTO, tested restore onto an isolated machine, disk/DB rollback, downtime session-rescheduling SOP and on-call contacts | Signed restore evidence and witnessed incident drill including duplicate response retries, missed visit, lost connection and service restart | Ops, DPO, PI |
| **8. Research execution dry run** | Staff onboarding, supervised classroom roster/time slots, consent and recruitment separation, neutral incentives, correct materials/languages, content hash and study instructions; small *approved* staged dry run | Witnessed A/B/C dry run without unapproved participants; no allocation leakage, stage skips or unlogged interventions; eligibility and consent signed off | PI, institution, supervisor, independent QA |
| **9. Immutable launch** | Exact 40-hex SHA, reproducible build/source + content hashes, signed protocol/SAP/power, release and rollback decision, approved data controller, 14-gate evidence manifest | Independent check of all signed evidence; final written institutional/PI **GO** for a specific deployment and recruitment dates | Authorized institutional signatory and PI |

## Data-collection minimization and consent notes

The original supervisor PDF proposes a registration form with name, age, program and course history and use of Google Forms/Sheets/Calendar or WhatsApp. None is automatically approved. Define the smallest eligible-person dataset, a separate lookup identity table, restricted access, withdrawal flow, retention/disposal and processor agreements. Voluntary **research consent** is not necessarily the same as the **GDPR legal basis**; the DPO must decide. Do not create or distribute live signup forms before that decision.

## Specific gaps this repo does NOT solve today

1. The current synthetic store only accepts IDs beginning `SYN_PILOT_`; it has no authorized student enrollment, identity, consent, concealment or supervisor session-authentication service.
2. The FIFO experiment does **not** coordinate multiple Python worker processes. A separate multi-process load/transaction probe is added in this branch to test that boundary, but **it is not a production HTTP load test**.
3. The 95 provisional questions, 32 resources and exact measurement instrument are neither signed nor linguistically/psychometrically approved.
4. The 90 recruited / 75 expected-completed plan is **feasibility planning only**, not an approved 80%-powered effectiveness design for moderate effects.
5. The source brief’s 6 NASA-TLX-after-session items and current 6 total pre/post M-VAS observations remain **scientifically unresolved**. See `rct_candidate_v1/SUPERVISOR_BRIEF_PROTOCOL_CROSSWALK_20261110.md`.

## Tests of the new strictly fictional multi-process probe

Run in a detached worktree with no VPS connection:

```bash
PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q tests/test_pilot_multiprocess_writer_probe.py
"$PY" -m scripts.pilot_multiprocess_writer_probe --mode native \
  > "$HOME/ijcai_multiprocess_native_synthetic.json"
"$PY" -m scripts.pilot_multiprocess_writer_probe --mode fifo \
  > "$HOME/ijcai_multiprocess_fifo_synthetic.json"
```

It creates a 0600-permission SQLite file inside a disposable temp directory; two spawned Python processes each open their **own** independent store instance, perform concurrent transaction updates through two threads, and check exact expected increments and SQLite integrity. No participant IDs or real-world credentials are used. **A passing FIFO result means only that SQLite correctly serialized the shared synthetic transactions; it does NOT imply the Python FIFO queue crossed process boundaries, and it is not human-study readiness.**

## Risk decisions not to pre-empt

- Do not automatically select 1, 2, or 5 workers; the measured p99 vs throughput trade-offs need real HTTP arrival profiles and preapproved thresholds.
- Do not re-enable WAL or merge the previously regressed off-lock planner optimization; both were rejected by local repeated performance results.
- Do not merge a chain of draft research PRs or reuse an existing fictional database in a human study; create a fresh reviewed candidate after the scientific design is frozen.
- Do not upload private documents, participant data, secrets, or genuine signed reviewer reports to the public GitHub repository.
- Do not present a test pass, staged consent UI, mock approval, or SHA-256 evidence inventory as institutional authorization.

**Status:** All technical implementation steps remain subject to independent review and acceptance. Human enrollment stays **NO-GO** until explicit signed institutional authorization.
