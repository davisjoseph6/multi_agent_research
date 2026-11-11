# Research V2 proposed specification — NOT the current IJCAI 2027 RCT

**Status 11 Nov 2026:** unapproved, synthetic-only experiment.
**Safety:** never replace the existing 127.0.0.1:8767 / 8766
or separately proxied 8077 services, nor migrate their SQLite files.
None of these changes authorizes a human study.

## 1. Scientific design fork — parallel vs crossover

The frozen existing design is a **three-arm parallel randomized trial**:
one person completes **only one** policy (A = V3/POMCP with possible
recovery, B = greedy practice without recovery, C = fixed balanced
practice without recovery). Its primary estimand compares independent
randomized groups.

The new request that **the same learner complete A, B and C** is a
three-period **crossover**. It changes the experimental design,
analysis, randomization, learning-exposure dose, measurement and
eligibility. It cannot be silently introduced into the original RCT.

The proposed state machine uses one pre-authorized period sequence
from six possibilities (ABC, ACB, BAC, BCA, CAB, CBA), one active
period at a time, and completion gates. Period/order and carryover
effects must be prespecified; learning cannot simply be "washed out"
like a short-lived medication effect. The research supervisor and
statistician must decide whether a crossover even answers the
intended question. Prefer the existing parallel design for the
current protocol until this is decided.

## 2. Question bank arithmetic and item reuse

A completed period currently has **16 pretest + 55 practice +
16 posttest = 87 independent questions**. Three non-repeating
periods require at least **261 distinct independent question IDs**,
with balanced content/concepts/difficulties and English/French
equivalence. The existing **95-row English candidate** contains
16 pretest + 55 practice + 16 posttest + 8 *separate*
DROP_2 recovery entries. There are only 87 normal question IDs,
not 261. More than 166 additional normal items would be needed
to meet the proposed counts: **174** new normal question IDs
(261-87), assuming no existing item is disqualified.
All 261 must be translated and independently reviewed in both languages.
The release validator also requires a shared canonical scored answer position
(never sent to the learner), distinct choices within each language and
coverage of all eight concepts in every independent question form.

The explicit `DROP_2` request **re-presents** the last incorrect
question with the original wrong option and correct option, whereas
the no-repeat rule says never repeat a question. The only coherent
exception is the immediate, explicitly labeled instructional
DROP_2 retry of an already presented practice item, which cannot
be counted as a new independent assessment question. The prior
incorrect option being known as wrong makes this particular two-choice
retry trivially solvable by elimination; pedagogical and observation
model approval is essential.

The release preflight `python -m scripts.research_v2_preflight`
intentionally returns exit status **2** and `BLOCKED_NOT_APPROVED`
for the current English-only, insufficient bank. **Never bypass it**
by duplicating question IDs or silently showing English text
under the French language setting.

## 3. Arm A: consecutive-error override (experimental, opt-in)

This candidate includes a separate mode enabled only with
`--question-anchored-recovery --mandatory-two-wrong-recovery`
on a new, **empty**, fictional SQLite database:

- Only consecutive incorrect normal **practice** questions in
  Arm A count; not pretest/posttest or DROP_2 attempts.
- After the second incorrect answer, a recovery action is presented
  **before any next question**, including when the 20th/15th
  practice question has just transitioned to `mvas_post`.
- The **mandatory action is a deterministic type rotation** among
  CONCEPT_SUMMARY, DROP_2, WORKED_EXAMPLE and SOCRATIC_HINT.
  This is **not a POMCP decision**. Between mandatory triggers,
  V3 still chooses ordinary practice actions using BKT; its
  discretionary resources are disabled in this mode to prevent
  uncontrolled dose differences. **Do not present this as the
  original pure-POMCP Arm A intervention policy.**
- The pure crossover progression gate rejects practice before a complete
  pretest and posttest before complete practice.
- A 20-question all-wrong visit can trigger 10 interventions.
  These count **in addition** to the 20 practice questions, unlike
  the original per-visit resource budget of **2**.
- After the completed intervention, the learner must explicitly
  choose **continue** or **save and resume later**. The fictional
  backend stores the pause/continue choice and blocks other actions
  while paused. Resumption after 14 days is rejected in this candidate.
- Text-only completion/acknowledgment does **not** establish restored
  mastery. For the two-answer retry, scored correctness is observable,
  but eliminating the known incorrect option inflates apparent success.
  Therefore the experimental V2 **does not update BKT from DROP_2**
  and excludes those instructional retries from the live BKT plot.
  It waits for a later independent practice question to provide
  mastery evidence. This differs from the legacy observation model.

The actual user study must settle a prespecified target, treatment
dose, fatigue and time-equivalence conditions, and a justified
intervention selection policy. The existing live 8767 browser is not
modified by this work.

## 4. BKT live curve vs independent performance

The isolated fictional server exposes a same-fixture, authenticated-
by-localhost-and-preview-nonce read-only `/unified/api/mastery`.
The browser draws the eight concept mastery estimates immediately
from committed completed answers; the graph is distinct from
independent **complete** 16-item pretest/posttest observed scores.
BKT is the estimator; POMCP and greedy are policies that **consume**
these estimates; fixed ignores them for ordering.

BKT state is *provisional* and its output does not prove actual
learning or causal benefit. Assessment scoring should not reveal
correct answers mid-test. The preview nonce and fixture aliases
are NOT secure production per-participant authentication.
A real live dashboard requires access control, data minimization,
and institutional validation.

## 5. Resume, reminders, private email and tokens

The pure, synthetic `PauseEpisode` rules model:

- First voluntary opt-in reminder at >=3 days of uninterrupted pause.
- Second reminder at >=3 days after the **actual first send**,
  unless completed, withdrawn, opted out or resumed. When users resume
  then pause again, the new pause is a new 3-day episode.
- At most one notice per dispatch check; late workers cannot
  simultaneously send both notices.
- Pause/resume window of <=14 days, with an explicit lock after the
  deadline. Do not silently withdraw people or skip the active arm.
- An independently issued **new 14-day bearer token for each
  period**, with only one active period and a global no-repeat
  question ledger. A 14-day token may require authorized
  renewal while a pause remains within the allowed window.
- Messages are **not actually sent**. There is no verified email
  contact vault, SMTP sender, consent/opt-out management, durable
  outbox worker, secure delivery mechanism or responsible data
  controller in this prototype. The `EMAIL_TEMPLATES` are only
  opt-in draft text in EN and FR.

A completely anonymous study cannot send individual reminders or
link a learner across three arms: the contact service must be able
to identify/re-contact the learner. The truthful wording is
**pseudonymized research data with restricted, separately held
contact information**, not "completely anonymous even to
administrators." Require transparent information notices and consent
or another legally established basis where appropriate.

## 6. Language release gates

- The source includes true EN/FR **interface welcome and disclosure
  strings**, but **not independently authored and reviewed
  French translations of the 95 English questions**, much less
  261 bilingual independent questions and validated bilingual
  recovery/fatigue materials.
- The current preview only serves English draft question content.
- The CSV preflight requires a one-to-one French translation mapping:
  duplicate approved rows cannot mask an untranslated item.
- `validate_cross_language_bank` and
  `scripts.research_v2_preflight` fail closed on incomplete French
  translations/review. Never quietly fall back to English questions
  for a French-language participant.
- Before a real bilingual release, require full item-level bilingual
  localization with equivalent options, distractor validity,
  translation review, content QA, accessibility and language-
  consistent consent/reminder copy.

## Reproduce ONLY in separate fictional local workspace

After GitHub CI passes, create a clean worktree:

```bash
cd ~/multi_agent_research
git fetch origin
git worktree add --detach ../ijcai_research_v2_review_20261111 \
  origin/research/ijcai2027-proposed-research-v2-gates-20261111
cd ~/ijcai_research_v2_review_20261111/agent2_realdata_benchmark
PY="$HOME/ijcai_http_acceptance_20261110/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q \
  tests/test_research_v2_proposal.py \
  tests/test_research_v2_preflight.py \
  tests/test_research_v2_two_wrong_browser.py

"$PY" -m scripts.research_v2_preflight
# Exit 2 and BLOCKED_NOT_APPROVED is EXPECTED (not a regression).
```

To inspect the separate synthetic browser, do NOT reuse an existing
database:

```bash
mkdir -p "$HOME/ijcai_research_v2_state"
chmod 0700 "$HOME/ijcai_research_v2_state"
"$PY" -m scripts.pilot_unified_fictional_browser \
  --question-anchored-recovery \
  --mandatory-two-wrong-recovery \
  --port 8770 \
  --db "$HOME/ijcai_research_v2_state/fictional_admission.sqlite3"
```

Only on the machine hosting it, open http://127.0.0.1:8770/.
For VPS preview, use an SSH-only loopback tunnel and a separate
verified source snapshot; never expose this app through Caddy.

**No part of this proposal authorizes enrollment, email dispatch,
production recruitment, an actual crossover RCT or claims of
scientifically established recovery benefits.**

## 7. Newly added isolated persistence and end-to-end smoke

The following additional files are **synthetic-only** and intentionally not
wired into a production public API:

- `src/prototype/research_v2_reminder_outbox.py`: distinct private SQLite
  contact store, explicit opt-in, three-day reminder reservations, second
  notice three days after **actual fictional delivery**, withdrawal,
  completion, opt-out, 14-day pause limit, and duplicate prevention.
  Only reserved `.test` recipients and `SYN_CONTACT_*` identifiers are
  accepted. It does **not** send actual emails or contain any SMTP credentials.
- `src/prototype/research_v2_crossover_fixture.py`: fictional durable three-
  period ledger, hashed 14-day period tokens, verified-fictional-identity
  token rotation, sequential pretest/practice/posttest barriers, global
  no-repeat questions, one-time immediate Arm-A DROP_2 retries, and
  idempotent request replay with payload-integrity checks.
- `scripts/research_v2_fulljourney_smoke.py`: an isolated six-sequence
  rehearsal that passes 261 **synthetic IDs** through each period sequence,
  checks two preview reminder acknowledgments and two synthetic recovery
  triggers, and deliberately sends zero actual emails.

These improvements DO NOT add 261 authored/reviewed research questions,
French translation, authenticated web enrollment, a real contact-service
sender, external ethics approval, or an actual integrated three-arm crossover
participant browser. The fictional scores do NOT constitute empirical
educational evidence.

Run after checking out the proposed V2 branch:

```bash
cd agent2_realdata_benchmark
python -m pip install pytest
python -m pytest -q \
  tests/test_research_v2_proposal.py \
  tests/test_research_v2_preflight.py \
  tests/test_research_v2_reminder_outbox.py \
  tests/test_research_v2_crossover_fixture.py \
  tests/test_research_v2_fulljourney_smoke.py
python -m scripts.research_v2_fulljourney_smoke
python -m scripts.research_v2_preflight
# Expected: BLOCKED_NOT_APPROVED and exit status 2
```

GitHub workflow `.github/workflows/research-v2-fast-gates.yml` runs
these lightweight tests and independently checks that human-study release
remains prohibited. Full self-contained regression coverage still runs in
`.github/workflows/rct-hardening-ci.yml`.
