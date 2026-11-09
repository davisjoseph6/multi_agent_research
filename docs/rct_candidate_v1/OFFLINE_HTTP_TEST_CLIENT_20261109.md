# Three-arm HTTP test-client contract — offline fictional rehearsal only

**2026-11-09. Development draft, not a web deployment. NO HUMAN ENROLLMENT.**

This increment adds a **Flask in-process test client**, not an externally reachable application or production WSGI entrypoint:
- `src/prototype/pilot_offline_http_draft.py`
- `tests/test_pilot_offline_http_draft.py`

It uses the disconnected `SyntheticThreeArmPilotStore` from the prior fully passing 1,339-test branch `research/ijcai2027-three-arm-offline-20261109` at `27ecf3b`. This code is NOT imported by the existing candidate's live WSGI factory, Caddy reverse proxy, IONOS VPS, or deployed fictional operator demo.

## Available offline test-client operations

| HTTP test-client call | Exact JSON body | Behavior |
|---|---|---|
| GET `/_offline/health` | none | Synthetic-only and human-enrollment-not-authorized status |
| POST `/_offline/next` | `pid,at` | Get same pending action ID on retries |
| POST `/_offline/rendered` | `pid,action_id,at` | Mark offered synthetic action rendered, no repeated event |
| POST `/_offline/act` | `pid,action_id,request_id,response,at` | Submit chosen quiz option, M-VAS rating or recovery completion, with idempotency |

All participants are **fictional `SYN_PILOT_<32 hexadecimal digits>` IDs** created privately via offline test fixtures, not enrollment endpoints. Each visit is opened by offline test code calling `start_supervised_visit` with fixture authorization flags. **No HTTP route accepts staff flags or opens a visit**; real staff authentication, consent and ethics clearance remain unimplemented and blocked.

The HTTP request timestamps are supplied by test fixtures. They MUST NOT be treated as trusted clock or scheduling evidence in a future real deployment. The current client is restricted to Flask `app.test_client()` and has no `app.run` or return of a WSGI app. The local-host and Origin checks are defense-in-depth only and should not be treated as secure public authentication.

## Validated by proposed tests

Five new test cases check:
1. No human enrollment/admin/start route; fake health status; restrictive headers.
2. Host, remote address and browser-Origin rejection.
3. Exact input schema, unknown ID, malformed timestamp, cross-participant and stale/action-not-rendered errors.
4. Single proposed M-VAS response 0–100, rejection of invalid ratings, preserved pending action, stage transition.
5. **Complete three-session journeys through in-process HTTP** for synthetic A/B/C, using the existing POMCP, greedy and balanced-fixed policies. The actions retain 16 pretest, 55 practice (20+20+15), six 0–100 M-VAS readings, 16 posttest, no B/C recovery resources and at most two A recovery interventions per visit.

These additions do **not** validate a browser rendering (no HTML/UI), real network performance, client authentication, same-origin public web security, user permissions or actual research design.

## Run on an isolated WSL checkout

```bash
cd ~/multi_agent_research
git fetch origin
git worktree add --detach ../ijcai_offline_http_review \
  origin/research/ijcai2027-offline-http-test-client-20261109
cd ../ijcai_offline_http_review/agent2_realdata_benchmark
PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q tests/test_pilot_offline_http_draft.py
```

Copy only existing frozen ASSISTments data into ignored local worktree folders, as in previous reviews, before running all tests.

**Test status:** These five new cases are committed but have NOT yet been executed in user's WSL. Prior baseline: **1,339 tests passed**. Expected target if all new tests pass: **1,344 tests**; do not report success before execution.

## Next actual browser/UI milestone after this test passes

Build an isolated local-only student **fictional preview** with accessible question labels, one 0–100 fatigue input at each pre/post timepoint (no default answer), recovery resource display, refresh/resume and a supervised-visit waiting screen. Security review must ensure no answer keys in responses. This UI will require a separate local server/review arrangement and extensive browser/device tests; it must not reuse the IONOS production settings or public enrollment.

Before any human participant use, formal protocol/SAP, fatigue instrument rights/validation, institution/ethics/DPO clearance, accessibility and security reviews, content expert approval, operational capacity and real staff authentication/consent remain mandatory.
