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

After F1 has completed and F2/F3 are pending, expect F1's record to show
3 finished learning visits, 3 finished attendance visits, 87 questions,
6 proposed fatigue recordings and `fully_finished=true`.
F2/F3 should report their actual persisted stages, which the audit
will not assume.

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

## Human-study readiness remains separate

Even an all-three-complete report establishes only a synthetic research
software rehearsal. It does not validate human identity, authentication,
privacy retention, a consent/legal basis, the fatigue measurement instrument,
instructional materials, power analysis, device/browser accessibility,
external HTTPS, independent penetration testing, encrypted backups,
recruitment or ethics/institutional permission. **Never use this tool
to claim that a real RCT may begin.**
