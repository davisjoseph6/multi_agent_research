# IJCAI 2027: Pilot release engineering execution and evidence matrix

**Date:** 2026-11-09. **Status:** BLOCKED FOR REAL STUDENTS. **Do not deploy to IONOS or use the fictional demo for human enrollment.**

## What is now reproducible, and what is not

- WSL baseline commit `2b1b130`: 1,354 tests passed and clean working tree (user-reported).
- Browser A/B/C three-visit fictional walkthrough completed, with read-only acceptance result `PASS_SYNTHETIC_ONLY`, no audit issues, SQLite `integrity_check=ok`.
- Recorded local acceptance report hash: `c9ceca0b5925e90add479051e77a1fc4baa670b3757c5999240faaa1f53fd16d`. Report stored privately at `~/ijcai_fictional_readonly_audit.json`, not uploaded to GitHub.
- GitHub Actions 2026-11-09 earlier failed **only because the fresh cloud runner lacked research fixtures**: 5 ASSIST2009 split tests needed the local `interactions.parquet`; 1 NeuralCD reference-parity test needed `~/research_references/NeuralCD/model.py`. The remaining **1,348** tests passed.
- This branch changes the old CI job label and command to run every **self-contained** test, explicitly excluding those 6 legacy fixture-dependent tests, and prints a warning about the coverage gap. **A green CI is therefore not a 1,354-test full-suite claim.** It must be paired with local artifact-bound full-suite evidence and an independent CI plan for reproducing the six external-fixture tests.
- This branch also adds a disposable concurrent **local SQLite** first-visit rehearsal. No HTTPS load, real browser traffic or V3 240-simulation performance conclusions can be drawn from the default 41-simulation run.

## Blocking execution matrix

| Workstream | Implementable next software output | Acceptance evidence and independent decision | Current condition |
|---|---|---|---|
| Candidate integration and freeze | Compare six stacked draft PRs; versioned source/content hashes, build manifest; new candidate branch without altering deployed demo | Release reviewer confirms complete diff, reproducible CI and rollback | BLOCKED; only stacked draft PRs |
| Protocol, SAP and power | Final endpoints, ITT sets, A-vs-B/A-vs-C estimands, missingness, sequential stopping; update power calculator | PI and statistician sign versioned protocol/SAP/power justification | BLOCKED; 90 enrolled / 75 complete not necessarily powered for medium effects |
| Study governance/ethics | List institution, research controller, PI, study ID, competent review pathway, recruitment authorization | Institutional signed ethics/authorization disposition + written final GO | BLOCKED; cannot self-certify |
| Privacy and participant rights | Data inventory, minimization, retention, deletion/withdrawal, DPO review, DPIA if required, breach procedure | DPO/controller decision and validated privacy/consent text | BLOCKED |
| Content and measurement | 95 items, 32 resources and exact M-VAS wording/admin/scoring frozen with source/licence review | Reviewer-by-reviewer signed register; linguistically tested versions | BLOCKED |
| Concealed assignment and access | Independent enrolment eligibility checks, secure server-side 1:1:1 allocation, staff roles, no participant-selectable arm | PI/statistician allocation SOP; external auth/security test, no arm leakage | NOT IMPLEMENTED IN HUMAN SYSTEM |
| Student-facing authorized interface | 3 supervised visits, 3–5 **actual elapsed days**, browser-resume, server-derived time, 16/55/16 tasks, 6 validated fatigue responses | Human-trial database separate from fictional, staff/consent gates; supervised E2E QA | SYNTHETIC ONLY |
| Production hosting | Dedicated non-demo domain/host, TLS, least privilege, secrets rotation, restricted ports, patching, monitoring | Independent configuration signoff, cert renewal, recovery/oncall | NOT VERIFIED |
| Capacity and concurrency | Separate isolated SQLite contention probe (this branch); production HTTP test scenario with 30+ simultaneous learners and 240 simulations | Measured p50/p95/p99, CPU, RAM, lock/5xx rates against PI-approved thresholds | LOCAL SYNTHETIC IN PROGRESS |
| Accessibility and devices | Keyboard-only flow, focus/labels/errors, reading/zoom, screen reader, phones, Chrome/Firefox/Edge; no default fatigue response | Independent WCAG 2.2 AA review with defect closure evidence | BLOCKED |
| Security and disaster recovery | Penetration test, dependency/secret scanning, external HTTPS anti-replay/session isolation; encrypted off-site backup and restore | Signed independent security report; verified RTO/RPO and restore drills | BLOCKED |
| Release and day-of-study | Deployment/rollback checklists; staffed sessions and contingency plan | Signed PI + responsible-institution GO; witnessed dry run, no critical open defects | BLOCKED |

## Fail-closed private evidence index

`docs/pilot_release_evidence/MANIFEST_TEMPLATE.json` contains 14 **pending** gates and **no real approvals**. Do not commit copies of signed approvals, participant information or private passwords to this public repository. Create a private directory outside the Git checkout, copy the template there as `manifest.json`, and point its artifact paths at private local files. Use `sha256sum` for fingerprints, enter exact 40-hex candidate commit, required reviewer role, reviewer identifier and timezone-aware review timestamp. Never invent/replace missing signatories with your own assertion.

Inspect **without writing to the database or sending documents to GitHub**:

```bash
PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m scripts.pilot_release_evidence_preflight
# Expected: BLOCKED_MISSING_EVIDENCE, nonzero exit; this is deliberate.
"$PY" -m scripts.pilot_release_evidence_preflight --manifest /private/pilot-evidence/manifest.json
```

Even when all 14 locally indexed documents pass presence/hash checks, result is `INDEX_COMPLETE_EXTERNAL_REVIEW_STILL_REQUIRED`, with `human_enrollment_authorized=false`. **This script checks document inventory and hashes only; it cannot authenticate signatures or legally authorize recruitment.**

## Disposable concurrency rehearsal

From the isolated review worktree, **never pointing at VPS or participant DB**:

```bash
"$PY" -m pytest -q tests/test_pilot_release_evidence_gate.py tests/test_pilot_concurrency_rehearsal.py
"$PY" -m scripts.pilot_concurrency_rehearsal --participants 30 --workers 5 --simulations 41
```

The second script returns a JSON report with completed fictional first visits, arm counts, action-roundtrip p50/p95/p99, write contention and error count. It creates and deletes its own temporary SQLite database. Scale up to `--participants 90 --workers 10` only after the small run passes; this **remains local** and synthetic. To test 240 simulations, pass `--simulations 240` on purpose. External production HTTP/device performance testing with agreed thresholds is a separate mandatory gate.

## Next gated sequence

**P0:** Verify new tests and GitHub Actions self-contained result; preserve 1,354-test full WSL baseline with frozen fixture fingerprints; compare stacked PRs and document a candidate SHA.

**P1:** Complete approved protocol/SAP, eligibility, six proposed M-VAS instrument details, independent content review, consent, named institution/PI/DPO/ethics review and allocate 90/75 recruitment only as a hypothesis pending power/feasibility approval.

**P2:** Implement a **new human-eligible** system in a new database and restricted deployment only after authorization architecture and independent design review. Add concealed randomization, real server clock, staff authentication, consent/withdrawal, role separation, security, accessibility and external load/restore testing. None of these changes belongs on the currently deployed fictional VPS.

**P3:** Evidence index independently authenticated, controlled deployment/rollback rehearsal, signed institutional PI GO and approved recruitment materials. **Zero real enrollment before this.**
