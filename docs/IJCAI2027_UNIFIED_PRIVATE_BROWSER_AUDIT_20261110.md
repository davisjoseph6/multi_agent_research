# Unified fictional browser: read-only completion audit

**Scope:** local/VPS **synthetic-only** software verification.
This is not human enrollment, consent validation, or a production security audit.

The deployed SSH-private browser service on port 8767 has a local,
single-file SQLite database containing nine fictional allocations,
three browser aliases (F1, F2, F3), and each learner's visit ledger.

`scripts/pilot_unified_browser_audit.py` reads the **existing** database
through a SQLite `mode=ro` consistent snapshot, with
`PRAGMA query_only=ON`. It never instantiates a mutable study store,
seeds records, advances time, submits answers, or changes the service.
The aggregate report excludes all participant IDs, mapping keys,
invitations, response contents, and arm assignments.

Its checks include database integrity, foreign keys, schema/version
restrictions, the synthetic admission event hash chain, all nine study
links, consent state, the one-per-arm browser aliases, treatment policy
consistency, visit start/finish accounting and questions/M-VAS outcomes.

## Run on the existing VPS database (after code review)

**Do not overwrite your running 8767 source snapshot.** Check out a new
read-only auditing snapshot from the branch, and run the audit against
the path of the existing fictional database.

WSL local checkout:

```bash
cd ~/multi_agent_research
git fetch origin
git worktree add --detach ../ijcai_unified_audit_review_20261110 \
  origin/research/ijcai2027-unified-browser-audit-20261110
cd ~/ijcai_unified_audit_review_20261110/agent2_realdata_benchmark
PY="$HOME/ijcai_http_acceptance_20261110/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q tests/test_pilot_unified_browser_audit.py
```

Copy a **new separate** audit checkout to VPS:

```bash
cd ~/ijcai_unified_audit_review_20261110
test -z "$(git status --porcelain)" || exit 1
VPS="<your-existing-VPS-address>"
ssh -i ~/.ssh/ijcai_preview_ed25519 "davis@$VPS" \
  'mkdir -p ~/ijcai_unified_audit_20261110'
set -o pipefail
git archive --format=tar HEAD agent2_realdata_benchmark docs | \
  ssh -i ~/.ssh/ijcai_preview_ed25519 "davis@$VPS" \
    'tar -xf - -C ~/ijcai_unified_audit_20261110'
```

On the existing VPS SSH terminal:

```bash
cd ~/ijcai_unified_audit_20261110/agent2_realdata_benchmark
PY="$HOME/ijcai_preview_5c6bb17/.venv/bin/python"
"$PY" -m pytest -q tests/test_pilot_unified_browser_audit.py
"$PY" -m scripts.pilot_unified_browser_audit \
  --db "$HOME/ijcai_unified_browser_20261110/state/fictional_admission.sqlite3"
```

**Important historical finding:** The original `4c99598` browser
used its *cumulative whole-study action count* as a per-visit timestamp
offset. On Visit 3, some learning actions could be assigned virtual
timestamps later than the hard-coded 70-minute attendance finish.
The corrected branch resets the virtual clock for each visit and
refuses any finish before the latest learning event. The read-only
audit intentionally reports `FAIL_SYNTHETIC` if the **existing**
deployment contains this historical inconsistency, even if its F1
transitions reported success. Do not rewrite, forge, or delete that
historical synthetic event chain to make it pass.

For a fresh, corrected fictional database, after F1 finishes and F2/F3
remain pending, expect F1 to show 3 completed learning visits,
3 attendance finishes, 87 ordinary questions, 6 proposed fatigue
recordings and `fully_finished=true`. F2/F3 show their actual stages.

To require all three fictional browser journeys to be finished:

```bash
"$PY" -m scripts.pilot_unified_browser_audit \
  --db "$HOME/ijcai_unified_browser_20261110/state/fictional_admission.sqlite3" \
  --require-complete
```

The final command exits with code **3** if the fictional records remain
incomplete, or **2** on audit failure. A valid but partially finished
fictional study may still return `PASS_SYNTHETIC_ONLY` with
`all_three_complete=false` when `--require-complete` is omitted.

## Validate corrected browser in an independent temporary VPS snapshot

Never point the corrected browser at the existing 8767 database or replace
its systemd unit blindly. Keep the old synthetic fixture as reproducible
historical evidence and use a new, empty database.

From the VPS, **after** transferring the new code into the isolated audit
snapshot shown above and passing its focused tests:

```bash
cd ~/ijcai_unified_audit_20261110/agent2_realdata_benchmark
PY="$HOME/ijcai_preview_5c6bb17/.venv/bin/python"
mkdir -p "$HOME/ijcai_unified_audit_20261110/fresh-state"
chmod 0700 "$HOME/ijcai_unified_audit_20261110/fresh-state"
"$PY" -m scripts.pilot_unified_fictional_browser \
  --port 8768 \
  --db "$HOME/ijcai_unified_audit_20261110/fresh-state/fictional_admission.sqlite3"
```

This command is a foreground, private, fictional server on **127.0.0.1:8768**
only, not systemd. The original 8766 and 8767 services remain intact.
In a separate WSL terminal, create another private forwarding tunnel to
port 8768 (same SSH options as for 8767, with both port numbers replaced)
and test:

```bash
"$PY" -m scripts.pilot_unified_private_smoke --base http://127.0.0.1:8768
```

Run the last command from a WSL checkout with `PY` set to the WSL
virtual environment; not from the VPS shell if you are testing the
tunnel. The local self-contained three-journey tests also verify the
new per-visit timing and read-only audit without changing any VPS state.

The 8768 process ends when its foreground terminal is stopped. Do not
expose it publicly, do not copy human data into the synthetic database,
and do not uninstall the existing services during this validation.

## Human-study readiness remains separate

Even an all-three-complete report establishes only a synthetic research
software rehearsal. It does not validate human identity, authentication,
privacy retention, a consent/legal basis, the fatigue measurement instrument,
instructional materials, power analysis, device/browser accessibility,
external HTTPS, independent penetration testing, encrypted backups,
recruitment or ethics/institutional permission. **Never use this tool
to claim that a real RCT may begin.**
