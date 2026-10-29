# Steps 72–123: eight-concept synthetic development extension (v3)

**NO-GO FOR HUMAN PARTICIPATION.** This bundle adds engineering functionality
while preserving the original 683-test reference baseline except for a
small, explicitly tested BKT correction in `study_v2_runtime.py`.

## What is implemented

- Eight-concept sampled latent state, history-tree UCT planner, five action
  types, explicit simulation budget/cost/transition model, reproducible seed,
  trace and model fingerprint.
- Opt-in Group A POMCP runtime with durable pending actions and no more than
  two resource actions per session. Group B remains greedy. Group C in v3
  uses a fixed, mastery-independent schedule that interleaves all concepts.
- Synthetic SQLite protocol through all 16 baseline items, 20/20/15 practice
  presentations, 3 six-response fatigue forms, 16 post-test items.
- Loopback-restricted Flask demo browser (credential in browser memory only).
  Demo resource content and questions are placeholders, not scientific items.
- Synthetic three-arm runtime rehearsal, traceable model sensitivity script,
  deterministic unit/integration tests and critical mathematical limitations.
- Pre-test-only Bayesian evidence update without artificial learning.

## What remains OPEN (do not mark as complete)

- Steps 75–78: supervisor-approved scientific comparison, estimand, dose and
  item-difficulty comparability.
- Steps 85–86, 91–95: empirical transition calibration, operational
  degradation validation, independent POMCP effectiveness benchmarking and
  theorem proof or correction.
- Steps 96–106: authored, independently expert-reviewed Behavioral Economics
  items, parallel-form calibration, learning transfer and fatigue validity.
- Steps 117–118: actual educational resource content, production identity,
  consent authorization and credential revocation.
- Steps 119–122: real-world deployment, secure identity management, reliable
  multidevice operations, DPO review, accessibility/pen testing and data
  stewardship.
- Human pilot and definitive RCT are intentionally OUTSIDE this synthetic
  software package and require institutional authorization.

## Installation and verification

From the project directory `~/multi_agent_research/agent2_realdata_benchmark`:

```bash
python -m scripts.step72_123_apply_v3
python -m py_compile src/prototype/study_v3_pomcp.py src/prototype/study_v3_runtime.py src/prototype/study_v3_demo_api.py
node --check src/prototype/static/study_v3_demo.js
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider tests/test_steps72_123_v3_extension.py
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 python -m scripts.step123_v3_pomcp_mock --participants 9 --seed 71 --simulations 80
PYTHONDONTWRITEBYTECODE=1 python -m scripts.step95_v3_sensitivity --simulations 120
```

Browser is for fictional subjects only:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m scripts.step123_v3_local_browser
```

Open `http://127.0.0.1:5062/trial-v3`, enter the locally printed PRIVATE
credential, select one of the SYNTHETIC arms and advance through sessions.
Refresh the browser, re-enter the token/ID, and verify recovery; Ctrl+C stops
the local server and removes the temp database. **Never paste the token into
chat, a Git commit, or published research logs.**

Use `git diff --check` and stage only reviewed source files. Keep the unrelated
`src/recovery/synthetic_evaluator.py`, development archives, and synthetic
outputs out of commits unless independently reviewed.

## Scientific status

All outputs from this package are synthetic engineering checks. Never report
synthetic post-test values, action frequencies, or model results as randomized
causal evidence for real students. The v3 POMCP policy is not identical to
historical four-action rule-based recovery. Neither is ready for a human RCT.
