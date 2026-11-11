# Read-only investigation: no recovery actions on port 8767

**Target: the existing private VPS service** `ijcai-unified-fictional-browser`
on `127.0.0.1:8767`. This is NOT the separately installed, public-domain
`ijcai-rct-operator-demo` (which runs on `127.0.0.1:8077`).

## Why empty recovery histories can be expected

- F1/F2/F3 are three displayed fictional fixtures sampled from nine synthetic
  allocations, with one shown fixture from each arm.
- Arm A uses V3 POMCP to choose either a QUESTION or an optional
  CONCEPT_SUMMARY, DROP_2, WORKED_EXAMPLE or SOCRATIC_HINT. It is not a
  rule that a wrong answer triggers an intervention.
- Arm B uses the greedy question selector and Arm C uses a balanced
  fixed practice schedule. **Neither offers recovery actions.**
- The private browser runner configures **41 simulations**, while the
  original planner has up to **40 root actions** (eight concepts, ordinary
  practice plus four resource types). It has no calibrated human recovery
  effects. Selection under these assumptions may not use resources.
- The 18/18 HTTP smoke tests check access guards and available fixtures.
  They do **not** check how many interventions POMCP has selected.

## Audit without touching the running VPS code

Checkout this branch into a clean, separate local review tree and run tests:

```bash
cd ~/multi_agent_research
git fetch origin
git worktree add --detach ../ijcai_recovery_diag_review_20261111 \
    origin/research/ijcai2027-private-recovery-diagnostic-20261111

cd ~/ijcai_recovery_diag_review_20261111/agent2_realdata_benchmark
PY="$HOME/ijcai_http_acceptance_20261110/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q tests/test_pilot_unified_recovery_diagnostic.py
```

Only after local and CI tests pass, transfer into a **new** directory
on the VPS without overwriting any installed service:

```bash
cd ~/ijcai_recovery_diag_review_20261111
test -z "$(git status --porcelain)" || exit 1
ssh -i ~/.ssh/ijcai_preview_ed25519 davis@31.70.172.140 \
  'mkdir -p ~/ijcai_recovery_diag_20261111'
set -o pipefail
git archive --format=tar HEAD agent2_realdata_benchmark/scripts/pilot_unified_recovery_diagnostic.py | \
ssh -i ~/.ssh/ijcai_preview_ed25519 davis@31.70.172.140 \
  'tar -xf - -C ~/ijcai_recovery_diag_20261111'
```

On the **VPS** SSH shell (davis@ubuntu), run with an existing vetted Python
and the already deployed 8767 source on PYTHONPATH:

```bash
cd ~/ijcai_unified_browser_20261110/agent2_realdata_benchmark
PY="$HOME/ijcai_preview_5c6bb17/.venv/bin/python"
PYTHONPATH="$PWD" "$PY" \
  "$HOME/ijcai_recovery_diag_20261111/agent2_realdata_benchmark/scripts/pilot_unified_recovery_diagnostic.py" \
  --db "$HOME/ijcai_unified_browser_20261110/state/fictional_admission.sqlite3"
```

The report counts completed incorrect practice answers, completed and
offered recoveries of each kind, and the Arm A planner's choices
without returning item responses or identities. It also reports
per-fixture progress. For a **private operator-only** mapping of F1/F2/F3
to the treatment arms, append `--show-arm`; do not show such mappings
during blinded participant interaction or publish this report.

Interpretation:

- If A has completed practice questions with incorrect answers and zero
  offered resources, the planner has not selected an intervention.
  This can be valid under the original V3 objective; it is not proof of
  a UI rendering defect.
- If A shows at least one `recovery_offered` but the browser never displayed
  it, investigate the render/submit UI, its pending action and
  completed-action history.
- If A has not progressed into practice or is waiting for a visit,
  no recovery is expected yet.
- If only B/C are examined, no recovery is expected by design.

Do not insert recovery actions, change a frozen policy, change treatment
assignments, or edit the SQLite event history just to make the demo
show an intervention. These changes would compromise the stated research
comparison.

## Security warning for the unrelated public operator demo

Never post bearer invitation tokens in command output, chat, logs, issue
comments or URLs. A public Caddy site that exempts `/api/rct/*` from Basic
Auth still enforces bearer-token access in the Flask API. A copied bearer
token can authorize fictional operations while valid. Rotate leaked
tokens with the server's `rotate_invitation` method before using the
public operator demo again, and verify Caddy configuration only on
the VPS, where the service is installed.
