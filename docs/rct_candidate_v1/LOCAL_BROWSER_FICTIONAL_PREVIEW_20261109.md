# Local-only fictional browser preview — never enroll real students

**2026-11-09 • CODE PREVIEW ONLY • UNAPPROVED • NO HUMAN PARTICIPANTS**

Previous in-process HTTP client passed 1,344 tests on user-verified commit 5adae47. This optional loopback-only browser demonstration runs on the disconnected synthetic three-arm engine. The IONOS/VPS production operator demo and /var/lib/ijcai-rct-demo/fictional.sqlite3 remain unchanged.

## Added

- src/prototype/pilot_local_browser_preview.py: Flask app guarded by loopback/Host, same-origin POST and per-process nonce, a server-controlled VIRTUAL clock, status/next/render/act endpoints. No human enrollment/visit-start/admin/score/export paths.
- scripts/pilot_local_browser_preview.py: explicit manual entrypoint, binds 127.0.0.1 only (never 0.0.0.0), no debugger, refuses root, uses a separate fictional-only SQLite file. Starts visits 2/3 from a SEPARATE OFFLINE TERMINAL COMMAND.
- templates/pilot_fictional_preview.html; static/pilot_fictional_preview.js; static/pilot_fictional_preview.css: semantic HTML, keyboard-native controls, responsive layout, fictional warnings, draft MCQs/recovery resources rendered via textContent, strict 0–100 M-VAS input WITHOUT a preselected rating. No third-party JavaScript, remote assets or inline scripts.
- tests/test_pilot_local_browser_preview.py: five new Flask test-client cases for no enrollment, nonce/origin/host guards, local assets, synthetic visit transition, invalid M-VAS and restart persistence.

## Run on local WSL only

After creating a new isolated worktree for this branch, from its agent2_realdata_benchmark directory:

    PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"
    "$PY" -m scripts.pilot_local_browser_preview

In a browser on the SAME machine open:

    http://localhost:8765/

If Windows cannot reach WSL localhost forwarding, configure WSL local forwarding or use a Linux browser inside WSL. Do NOT expose to any public IP, tunnel or reverse proxy.

The process seeds precisely three records, one each Arm A/B/C, all named SYN_PILOT_*, in a NEW named SQLite file:

    ~/.cache/ijcai2027_fictional_browser_preview/fictional_browser_preview.sqlite3

They are fake profiles with unapproved practice content, no real identity/consent/enrollment/participant data. Planner simulations=41 (responsive fictional preview, NOT the 240-simulation release candidate).

## Move to the next fictional supervised visit

After finishing Visit 1 for Arm A, open a SECOND WSL terminal in the same review checkout:

    PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"
    "$PY" -m scripts.pilot_local_browser_preview --advance-arm A

This does not run a server or accept any real staff credentials. It advances the fictional clock four days ONLY after that arm's preceding visit completed. Repeat to start Visit 3. Use B or C for the other fictional arms. Refresh the page. Pending actions persist across browser reloads and restarts; Ctrl+C stops the server.

## Limitations / blockers

No public authentication, real student allocation, consent, signed release, ethics/DPO approval, expert content review (95 questions / 32 resources), approved M-VAS wording/digital psychometrics, production TLS/concurrency, device testing, screen reader audit, independent security testing or offsite encrypted backup is implemented by this component. All timestamp and four-day spacing evidence is VIRTUAL, not actual supervision. User choosing A/B/C is not randomized treatment assignment. Arm A includes additional recovery resources (bundled intervention confound).

Do NOT merge or deploy to the existing IONOS VPS. The full authorized human RCT implementation, protocol/SAP, study statistics, ethics, privacy, security, accessibility, and staff procedures are separate approval gates.

## Automated verification

    "$PY" -m pytest -q tests/test_pilot_local_browser_preview.py
    "$PY" -m pytest -q

These five new tests have been committed but NOT YET EXECUTED on user's WSL. Prior verified baseline 1,344; anticipated 1,349 if all pass.

Flask test-client checks are not real browser/device/accessibility checks. Follow with manual Chrome/Firefox/Edge, keyboard-only, mobile viewport and screen reader testing before calling even the fictional browser UI broadly reliable.
