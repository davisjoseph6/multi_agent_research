# IJCAI 2027 — Research V2 test and verification matrix
**Status:** 11 Nov 2026. Isolated synthetic candidate; not an approved human RCT.

This matrix refers to the draft proposed crossover branch. Never merge it into
the original three-arm parallel RCT or publish the VPS routes without a
protocol/design review and independent release authorization.

## Tests that are actually automated

| Scope | How to reproduce | What a pass demonstrates |
|---|---|---|
| Six-sequence full-journey smoke | `python3 -m scripts.research_v2_fulljourney_smoke` | A synthetic subject can complete 3 periods with 261 distinct fake item IDs across each of six permutations; no real email |
| Targeted V2 invariant tests | `python -m pytest -q tests/test_research_v2_*.py` | Consent-gated specifications, bilingual validator, two-error browser, token lifecycle, reminder queue, opt-out, 14-day expiry, recovery-before-fatigue, idempotency and six-sequence transitions |
| Research V2 fast gates | GitHub Actions `research-v2-fast-gates.yml` | Pure Python tests and mandatory **BLOCKED_NOT_APPROVED** release gate |
| Self-contained full regression | `python -m pytest -q --ignore=tests/test_assist2009_splits.py -k "not test_reference_forward_equivalence"` | Repository integration, server, database, security and recovery tests with available fixtures |
| Existing RCT rehearsal QA | GitHub Actions `rct-hardening-ci.yml` | Full self-contained regression and 0/14 published release evidence, plus no public participation surface |
| Pure V2 release rejection | `python -m scripts.research_v2_preflight` | Exit code **2**, `BLOCKED_NOT_APPROVED`, no human enrollment |
| Python syntax | `python -m compileall -q scripts src tests` | Parse/import-independent syntax check, not runtime verification |

The first test is deliberately **not** a claim that 261 peer-reviewed questions
exist. The actual bank has 87 independent normal items and 8 separately
authored DROP_2 items, and is not an approved bilingual crossover bank.

The full repository suite also contains six **external research fixture** tests
not exercised by the CI self-contained command: 5 tests requiring the frozen
ASSIST2009 data/splits and 1 requiring the external NeuralCD reference.
These require local, independently verified fixtures. Never fabricate these
datasets or mark the tests passed without running them.

## Run locally in WSL without changing original branches

The user has already created a detached worktree at
`~/ijcai_v2_validation`; do **not** run `git pull` there. Update the
worktree only after verifying no uncommitted changes:

```bash
cd ~/ijcai_v2_validation
test -z "$(git status --porcelain)" || { echo "Worktree has changes: stop"; exit 1; }
git fetch origin
git switch --detach origin/research/ijcai2027-proposed-research-v2-gates-20261111
cd agent2_realdata_benchmark

python3 -m scripts.research_v2_fulljourney_smoke
# Install pytest in a dedicated virtual environment if needed.
python3 -m pytest -q tests/test_research_v2_proposal.py \
  tests/test_research_v2_preflight.py \
  tests/test_research_v2_reminder_outbox.py \
  tests/test_research_v2_crossover_fixture.py \
  tests/test_research_v2_fulljourney_smoke.py
python3 -m pytest -q tests/test_research_v2_two_wrong_browser.py
```

For the full self-contained suite, use an existing repository test environment
with the dependencies in `requirements-prototype.txt` installed:

```bash
python -m pytest -q \
  --ignore=tests/test_assist2009_splits.py \
  -k "not test_reference_forward_equivalence"
```

When the two external fixtures are present, run `python -m pytest -q`
without excluding them. A green CI run is not a substitute for independently
verified real-device, production-concurrency, TLS, email-delivery,
accessibility, security, restore/backup, or human-protocol tests.

Check the explicit release denial separately; code 2 is expected:
```bash
python -m scripts.research_v2_preflight
test "$?" -eq 2
```

## Release blockers not solvable by passing more unit tests

- Real email delivery, provider credentials, secure recontact verification,
  operational idempotency, and data-controller/consent governance.
- Institutionally reviewed bilingual 261-item question bank, reviewed
  question-specific guidance, independently approved English/French fatigue
  instrument and pretest/posttest design.
- Approved crossover design, allocation scheme, carryover analysis and
  sample-size/power analysis. The existing parallel trial must remain frozen.
- Independent privacy, accessibility, penetration, load/recovery and real
  participant acceptance tests before operational approval.

The synthetic contact vault supports reserved `.test` recipients only.
The SQLite queue models recoverable claims; an external transport must
support its own idempotency controls to avoid duplicate emails after a crash
between external delivery and local acknowledgment.

## Additional 11 November verification

The new crash-recovery and two-error persistence revision passed a full
self-contained GitHub run with **1,618 passing tests and 1 deliberately
deselected external-reference test**. The targeted fast gates subsequently
passed **37 tests** on the BKT-trace commit.

- The fictional email outbox can reacquire an unacknowledged reservation
  after its 30-minute lease; the same queue ID acts as a future provider
  idempotency key. This is NOT an exactly-once email delivery guarantee.
- The fictional crossover record now persists the consecutive-wrong streak,
  requires the indicated intervention before continuing, and preserves
  recovery state across process restart.
- The persisted per-period BKT trace requires trusted concept metadata,
  excludes immediate DROP_2 instructional retries, and does not expose
  partial pretest/posttest scores before all 16 items are complete.
- A valid 261-item bank and institution-controlled human authentication
  remain prerequisites before a real browser can use these models.

The live web UI for the new crossover workflow and a verified email
provider are **not** supplied by the standalone synthetic stores. Never
interpret an offline green test as evidence of human-study readiness.
