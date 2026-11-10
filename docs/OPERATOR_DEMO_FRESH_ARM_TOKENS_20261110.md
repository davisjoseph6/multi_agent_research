# Fresh fictional Arm A/B/C invitation tokens for demo.selfhealing-edu.fr

This workflow is **only** for the HTTPS `operator_demo` Flask/Gunicorn
application and its existing pre-seeded `fictional.sqlite3`. It is **not**
the separate SSH-only unified browser on ports 8766/8767, which uses
F1/F2/F3 aliases rather than invitation bearer tokens.

No real-student enrollment, real consent or human-study release is enabled.
Do not generate tokens for another research deployment or reset an existing
database. Never publish bearer tokens, share them in ChatGPT/GitHub, put
them into shell commands or URLs, or record them during screen sharing.

## 1. Check the domain's actual service on the VPS

```bash
getent ahostsv4 demo.selfhealing-edu.fr
sudo systemctl is-active ijcai-rct-operator-demo
sudo systemctl show ijcai-rct-operator-demo -p User -p WorkingDirectory
sudo ss -lntp '( sport = :8077 )'
sudo grep -E '^RCT_DEMO_(SETTINGS|DATABASE)=' /etc/ijcai-rct-demo/demo.env
```

Stop unless the actual domain is routed to this VPS and that exact
service is active, running as `ijcai-demo`, with private
`127.0.0.1:8077` Gunicorn; its live environment must identify the
existing `operator_demo` settings and fictional database. A static
preview, 8766/8767 app or another VPS requires a different procedure.

## 2. WSL: review and test the new offline utility

```bash
cd ~/multi_agent_research
git fetch origin
git worktree add --detach ../ijcai_arm_token_review_20261110 \
  origin/research/ijcai2027-operator-demo-arm-token-refresh-20261110
cd ../ijcai_arm_token_review_20261110/agent2_realdata_benchmark
PY="$HOME/ijcai_http_acceptance_20261110/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q \
  tests/test_rct_operator_demo_new_arm_tokens.py \
  tests/test_rct_operator_demo.py
```

Tests exercise the same database twice, preserve old invitations, ensure
new A/B/C tokens start at pretest, confirm 0600 output, and demonstrate
that an interrupted allocation transaction creates no partial cohort.

## 3. Transfer only the reviewed Python utility

From WSL, in the above checkout:

```bash
scp -i ~/.ssh/ijcai_preview_ed25519 \
  scripts/rct_operator_demo_new_arm_tokens.py \
  davis@31.70.172.140:/tmp/rct_operator_demo_new_arm_tokens.py
```

On the **correct** VPS, only after read-only service/path verification:

```bash
sudo install -o ijcai-demo -g ijcai-demo -m 0600 \
  /tmp/rct_operator_demo_new_arm_tokens.py \
  /var/lib/ijcai-rct-demo/new_demo_arm_token_utility.py
sudo rm -f /tmp/rct_operator_demo_new_arm_tokens.py
```

The utility is placed outside the served application and web root.
No service restart, Caddy reload, database replacement or enrollment
HTTP route is required.

## 4. Register new fictional invitations in the CURRENT live demo database

```bash
sudo -u ijcai-demo -H bash -c '
  set -euo pipefail
  set -a
  source /etc/ijcai-rct-demo/demo.env
  set +a
  export PYTHONPATH=/srv/ijcai-rct-demo/repo/agent2_realdata_benchmark
  exec /srv/ijcai-rct-demo/venv/bin/python \
    /var/lib/ijcai-rct-demo/new_demo_arm_token_utility.py \
    --settings "$RCT_DEMO_SETTINGS" \
    --db "$RCT_DEMO_DATABASE" \
    --expected-host demo.selfhealing-edu.fr \
    --lifetime-hours 72 \
    --out /var/lib/ijcai-rct-demo/demo_arm_tokens_PRIVATE_20261110.json
'
```

Choose a *new filename* if the file already exists; the script
intentionally refuses overwrites. The output lists the private filename
and nonsecret enrollment counts, **not invitation strings**. The
same live SQLite file receives nine brand-new, pre-enrolled fictional
records. The new private JSON supplies exactly one usable token each for A,
B and C. Six extra randomized fictional records are immediately
deactivated in the same transaction; no extra usable credentials are
retained. Existing tokens remain untouched.

The batch uses one SQLite transaction with a private fsynced pending
output; if the transaction fails, the batch rolls back. If publishing
the file fails after commit, preserve the secret `.pending_...` file
and investigate; do not create another batch blindly.

## 5. Privately retrieve one token at a time

Do this **only when your terminal isn't screen-shared or recorded**.
Never paste the token into ChatGPT or an issue. Use the same service
user to open the owner-only file:

```bash
sudo -u ijcai-demo -H /srv/ijcai-rct-demo/venv/bin/python - \
  /var/lib/ijcai-rct-demo/demo_arm_tokens_PRIVATE_20261110.json <<'PY'
import json
import sys
from pathlib import Path
info = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for arm in "ABC":
    print("Arm", arm, ":", info["tokens_by_arm"][arm]["invitation"])
PY
```

Enter each invitation **in the HTTPS operator-demo webpage**, separately.
The service handles API authorization with a Bearer token, but do not
put it in a URL or add it to a shell command's arguments.

After the demonstration, revoke or expire the temporary credentials
under a reviewed operator procedure and keep the JSON private.
These records are *fictional demo state*, never human experiment evidence.

## Hard stop conditions

Do not execute this script if `ijcai-rct-operator-demo` is missing,
the domain points to a different VPS, the service's environment uses
another database or mode, or the database contains any non-SYN_ IDs.
Do not assume port 8767's unified browser uses invitation credentials.
When a check fails, inspect the actual deployment rather than
creating random strings that the site will reject.
