# IJCAI 2027 — Supervisor 11 Nov 2026 protocol implementation crosswalk

**Branch:** research/ijcai2027-supervisor-parallel-protocol-20261111  
**PR:** draft #34; **real study release:** NOT AUTHORIZED.  
**Purpose:** preserve all supervisor-prescribed steps and add tests around the
existing repository, WITHOUT merging the incompatible crossover proposal in PR #33.

## Source precedence and conflicts

1. The newest `participant_scenarios.docx` and `scenario_traces.csv`
   establish exact adaptive decision behavior: 7 scripted cases, 465 steps.
2. `data_to_save.docx` establishes append-only event/state history and
   separation of contact PII from deidentified research data.
3. `Experimentation (1).pdf` establishes the user interface, onboarding,
   recruitment, neural comparison and general workflow, except where the
   newer, explicitly revised rules contradict its older algorithmic details.
4. The email mentions `quiz_bank_144.csv`, but the actual attached file and
   newer scenario specification are `quiz_bank_192.csv`. Strictly ingest
   the supplied 192 items; never silently substitute or synthesize missing IDs.
5. The old PDF describes recovery from degradation D > .5, whereas the new
   document says D is **monitoring-only**. Implement new 5a/5b per-concept
   criteria and still compute/log D every step. Do not run both triggers.
6. The separate 2026-11-11 crossover/deterministic-intervention proposal
   changes the estimand and is NOT the supervisor's A/B/C parallel protocol.
   It stays separate and must not be deployed into this study.
7. In the old PDF, the proposed neural-network input bullet list contains
   **20** numeric features (8 masteries + 1 overall Bloom + 8 one-hot concept
   + 1 response time + 1 session + 1 current Bloom), but a separate
   architecture line says Input(21). No hidden 21st feature may be invented;
   this must be reconciled with the supervisor before frozen NN training.

## Software and requirements status

| Source requirement | Current isolated implementation | Tested? | Human pilot ready? |
|---|---|---|---|
| Preserve 8/16/192/16 actual content forms | Content copied to data/supervisor_20261111, validated | Yes | Needs item-by-item academic review |
| Screening L1 one/concept and course exclusion | Short circuit on economics=yes; cutoff ≥6/8; no group assigned for ineligible | Yes | Requires approved recruitment/consent text |
| Rotation of only eligible learners A→B→C | SQLite registration transaction | Yes | No human registration enabled |
| Exactly one group throughout all 3 sessions | SupervisorTraceEngine, participant grp immutable by API | Yes | Needs supervisor confirmation of analysis protocol |
| Day 0 pretest 16 and Q-matrix .75/.50/.20 | Exact eight-concept initializer | Yes | No reviewed pretest administration |
| Current Bloom starts L1; 2-streak promotion/demotion | Existing BKT + supervisor trace policy | Yes | Pending scientific evaluation |
| BKT learn=.10, slip=.10, guess=.25 | Reuses original study_v2.BKT | Yes | Calibrate only using legitimately collected data |
| D=mean(1-m) logged after each step | Every quiz/recovery event; no D trigger | Yes | Not a treatment trigger |
| A: 5a/5b per-concept triggers, caps 2/session 2/concept | Deterministic engine and persisted state | Yes | No behavioral-efficacy claim |
| Recovery sequential summary→DROP_2→worked→Socratic | Four-step state; scored bank recovery updates BKT only | Yes | Requires approved generated-content prompts/text |
| 2nd unsuccessful attempt nonrecoverable, Bloom=L1 | Rule 6c state/trace | Yes | Needs supervisor approval |
| B greedy weakest current-level fallback + LRU | Exact original ID priority and trace-derived LRU | Yes | No POMCP substitution |
| C fixed original _01–_03 ordering across sessions | Exact original ID fixed sequence | Yes | No reshuffle |
| 20+20+15 independent regular quiz questions | Backend counters enforce exact session sizes | Yes | Not a real participant service |
| Posttest16 after session 3 quiz, before fatigue | Backend state order | Yes | Assessment form not to teach |
| Six NASA-TLX 1–7 fatigue items after each session | Structural Q1–Q6 persisted, no item wording invented | Yes (structure) | **Needs exact approved six questions/scoring** |
| Sessions 3–5 and 6–10 days after first | Fixture schedule Day0/4/8, next-session date gate | Yes | Real schedule/admin not connected |
| Reminder 24h ahead; reschedule within 48h; remove after two misses | Memory-only fake due notifier and attendance flags | Yes (synthetic) | **No actual email/WhatsApp transport** |
| Contacts with email/token hash separately stored | Separate SQLite contact DB, .test-only fake identities | Yes | Needs authorization, encryption/key/retention audit |
| Seven remaining research tables | Config, participants, sessions, state, history, events, surveys | Yes | Institutional data controller signoff |
| Daily research+contacts database backup; delete contacts at collection end | Integrity-checked local fake SQLite backups to a 0700 folder; explicit fake-contact purge only after all learners inactive | Yes (synthetic tests) | **No production encrypted daily scheduler, offsite restore verification or approved retention** |
| Each response atomically records events + current state + history | Transactional SQLite; append-only triggers | Yes | Production backup/recovery untested |
| Never export contacts or treatment to learner UI | No join with PII in research event exports | Yes | Need independent privacy review |
| Close/reopen during recovery resumes correct state | JSON snapshot and SQLite integration | Yes | End-to-end real browser restart test pending |
| Exact seven reference cases and 465 rows | Oracle test and full SQLite 3-session rehearsals | Yes | Scripted fixtures not empirical outcomes |
| Flask/browser interface from Sara/Wiam tasks | Private localhost-only proof-of-concept with fake registrations | Yes | Device/UX/accessibility acceptance pending |
| NN after real Session1, retrain after Session2, AUC comparison NN/BKT/DKT | New strict pre-question 20-feature extraction, 20→64→32→1 optional PyTorch synthetic trainer, grouped holdout; paired AUC/Brier comparison contract | Yes (synthetic tests only) | **Real training data, 20-vs-21 schema choice, DKT predictions and scientific validation needed** |
| Claude API runtime resource generation | No supplied approved prompt/API entitlement; placeholder deliberately flagged | No | **Requires prompt, provider contract, content review** |
| 75 eligible real learners, 3 sessions each, 5-person UI check | Nothing conducted; recruitment belongs to institution/team | No | **Requires ethics/admin authorization and actual testing** |
| Live TLS, mail, monitoring, device/load/security audits | Existing unrelated RCT infrastructure left untouched | No | **14 required release evidence gates** |

## Reproducible isolated WSL commands

Use a distinct local worktree, preserving the crossover V2 worktree and
your original repository. After a fetch from the repository:

    cd ~/multi_agent_research
    git fetch origin
    git worktree add --detach ../ijcai_supervisor_validation origin/research/ijcai2027-supervisor-parallel-protocol-20261111
    cd ../ijcai_supervisor_validation/agent2_realdata_benchmark
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install pytest==9.1.1 Flask==3.1.3
    python -m pytest -q tests/test_supervisor_20261111_traces.py tests/test_supervisor_20261111_store.py tests/test_supervisor_20261111_end_to_end_store.py tests/test_supervisor_20261111_reminders.py tests/test_supervisor_20261111_fictional_http.py
    python -m scripts.supervisor_fictional_browser --port 8783

View the fictional local interface at http://127.0.0.1:8783.
Never add a public reverse proxy, expose this server to the VPS, or
submit genuine learner details: it is not authenticated human enrollment.
The launcher erases its temporary SQLite data when stopped.

For the existing full regression suite, use the repository's pinned
requirements-prototype.txt environment (it includes large PyTorch/CUDA
packages) and run:

    python -m pytest -q --ignore=tests/test_assist2009_splits.py -k "not test_reference_forward_equivalence"

The six tests excluded by this command require genuine separate ASSIST2009
and external NeuralCD reference files. Neither those external datasets
nor actual 75-person educational outcomes are present in this PR.

## Release policy

PR #34 must remain DRAFT. Do not merge it into the real RCT or
start recruitment until the supervisor approves the revised technical
plan, all scientific content and ethics/security/consent/legal conditions
are met, and the 14 mandatory release evidence gates have been signed.

**Passing synthetic tests is evidence of implementation consistency,
not approval or empirical educational effectiveness.**

## Offline NN software rehearsal, not a scientific result

After installing the pinned project PyTorch environment, the following
commands display the feature contract and execute an entirely fictional
train/validation smoke test:

    python -m scripts.supervisor_neural_rehearsal --feature-contract
    python -m scripts.supervisor_neural_rehearsal --self-test --epochs 2

The module deliberately rejects genuine learner IDs. Real NN/BKT/DKT AUC
cannot be measured until approved heldout model predictions from actual
study data exist, and the 20-vs-21 input discrepancy is resolved.

## Fictional database retention drill

A separate optional operator-only module
`src/prototype/supervisor_fictional_backup.py` makes integrity-checked
local copies of BOTH fake databases into an existing 0700 directory.
It never sends them to an external service. Purging contacts additionally
requires an explicit end-of-collection flag and zero active learners.
These helpers do NOT substitute for production encrypted, scheduled,
monitored and independently restored backups.
