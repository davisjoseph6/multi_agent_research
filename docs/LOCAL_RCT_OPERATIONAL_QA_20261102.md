# Fictional RCT staging — operational QA evidence (user-reported, 2026-11-02)

**Update:** The previously blocked Chromium full-browser test subsequently PASSED. See [CHROMIUM_REHEARSAL_PASSED_20261102.md](CHROMIUM_REHEARSAL_PASSED_20261102.md). The failure below is preserved as the original incident history.

**Status: local software rehearsal only. Not human-study approval, production
capacity, actual public TLS, independent security or accessibility verification.**

## 30-participant in-process concurrent run

Command: `python -m scripts.rct_operational_load --participants 30 --workers 8 --out /tmp/rct_load_30_20261102.json`

| Metric | Operator-provided output |
|---|---|
| Fictional journeys completed | 30/30 |
| Allocation | A=10, B=10, C=10 |
| Practice/study action total | 2,760 |
| Flask in-process client requests | 11,130 |
| Workers | 8 |
| Wall time | 56.721 s |
| Mean latency | 39.494 ms |
| Aggregate p95 request latency | 82.488 ms |
| Aggregate maximum latency | 5,553.064 ms |
| Pending actions | 0 |

Per route: `act` p95 84.444 ms/max 4649.833 ms;
`enroll` p95 21.874 ms/max 2035.377 ms;
`information` p95 933.046 ms/max 1533.091 ms;
`next` p95 66.589 ms/max 5553.064 ms;
`rendered` p95 57.917 ms/max 4454.841 ms.

**Caution:** these are in-process test-client timings. Outliers exceed
four seconds on several endpoints and have not been diagnosed; actual
Gunicorn/Caddy HTTPS p95/p99, resource utilization, contention and device
latency remain untested. No real participants.

## Backup/restore drill

Command: `python -m scripts.rct_restore_drill --out /tmp/rct_restore_20261102.json`

- Passed: yes.
- Pending action survived backup and restore.
- The original rehearsal database was unaffected by restoring a copy.
- 85 remaining actions completed on the restored fictional database.
- Pre/posttest completion: 16/16 each, zero pending actions.
- Not tested: encrypted off-site backups, actual host failure, automated backup
  retention or production recovery time objective.

## Chromium full browser check — blocked before execution

Command: `bash ops/rct/qa_browser_userlibs.sh python -m scripts.rct_browser_qa --full --out /tmp/rct_chromium_full_20261102.json`

```text
Missing shared libraries:
libasound.so.2
libnspr4.so
libnss3.so
libnssutil3.so
Attempting user-local extraction of: libasound2 libnspr4 libnss3 libnss3
E: Can't select candidate version from package libasound2 as it has no candidate
```

This is dependency resolution, not a passed Chromium test. The wrapper
previously assumed `libasound2`, which is virtual on Ubuntu 24.04;
`libasound2t64` is the concrete package name for Ubuntu 24.04.
The wrapper on the staging branch now chooses concrete candidates from
the locally configured `apt-cache policy` metadata and de-duplicates the
download list. **The fix and new unit tests still require a user machine run.**

## Correct next steps

```bash
cd ~/multi_agent_research
git switch feature/rct-https-staging-20261101
git pull --ff-only
cd agent2_realdata_benchmark

cat /etc/os-release | grep -E '^(ID|VERSION_ID|VERSION_CODENAME)='
bash -n ops/rct/qa_browser_userlibs.sh
python -m pytest -q tests/test_rct_browser_userlibs.py

bash ops/rct/qa_browser_userlibs.sh --resolve-package libasound.so.2
bash ops/rct/qa_browser_userlibs.sh --resolve-package libnspr4.so

# Existing failed browser test did not create its output file;
# use a fresh filename regardless to preserve any earlier evidence.
bash ops/rct/qa_browser_userlibs.sh \
  python -m scripts.rct_browser_qa --full \
  --out /tmp/rct_chromium_full_20261102_retry01.json
```

If package metadata remains missing, check `apt-cache policy libasound2t64
libasound2 libnspr4 libnss3`, package repositories and network access. Do
not mix packages from another OS release or use `LD_PRELOAD`/browser sandbox
disabling workarounds. With admin permission, supported `python -m playwright
install-deps chromium` is preferable to the user cache. Absent suitable
libraries, the browser-test gate remains **BLOCKED**.

## Independent human study gates are unchanged

The currently published GitHub Pages preview is an illustrative static
site. The HTTPS VPS does not yet exist. The separate fictional interactive
operator demo is code-tested, not deployed. Real human enrollment remains
blocked by ethics/privacy, measurement, instructional-content, security,
accessibility, operational and statistical-protocol sign-off.
