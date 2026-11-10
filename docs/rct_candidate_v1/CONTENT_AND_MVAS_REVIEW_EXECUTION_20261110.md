# Independent instructional-content and fatigue-measure review execution

**2026-11-10. Pending independent approval. Do NOT present draft quizzes or the rehearsal fatigue form as reviewed human-study instruments.**

## Current content set

The bank at `agent2_realdata_benchmark/docs/rct_candidate_v1/` holds **95 provisional questions**: 16 baseline pretest, 55 practice, 16 final posttest and 8 DROP_2 recovery variants. It also holds **32 provisional recovery resource entries**. This is a **127-row reviewer register** at `docs/rct_candidate_v1/CONTENT_REVIEW_REGISTER_20261108.csv`.

As supplied in the source repository, all 127 register rows have the current review decision **pending**, and the individual signoff/reviewer fields are blank. The existing 6-item `fatigue_REHEARSAL_ONLY.json` is a separate, unvalidated 1–5 response rehearsal instrument and is **not** the supervisor-proposed 0–100 *single-item before and after learning* M-VAS.

## What the subject-matter reviewers must do

Every one of the **95 quiz** rows requires an authorized independent review for learning-objective coverage, eight behavioral-economics concepts, Bloom level/difficulty, unambiguous prompt, correct answer/rationale, distractors, accessibility, source permissions, cultural bias and (if used) language versions. Re-review each changed hash.

Every one of the **32 recovery resources** requires an independent review for scope, correctness, licensing, pedagogy, source attribution, accessibility, consistent package treatment and whether "offered", "opened", "rendered" and "completed" are measured distinctly. For Arm A, confirm the allowable per-session recovery count and the definition of a recovery *action* or sequence. Arm B/C must not receive A-only resources.

**Do not add invented reviewer names, decisions, dates or permissions**. Keep real reviewer evidence in the private institution-approved store. No local tool can authenticate reviewer signatures.

## Required separate fatigue instrument decision

The supervisor has *proposed* one item, rated **0–100 immediately before and immediately after learning**, at each of three visits. Before a real student sees it, the PI and psychometrics reviewer must approve:
- exact wording and endpoint labels, original source and rights;
- whether physical 10-cm VAS versus digital integer 0–100 response are comparable;
- user-selected non-default response, keyboard/number input and screen-reader alternatives;
- approved translations and consistent timing relative to pretest, learning and final posttest;
- handling of skipped, incomplete, withdrawn or rescheduled observations;
- sign of fatigue change (`post - pre`), descriptive reporting and limits on inference.

No such independent scientific/psychometric approval is currently evidenced. In particular, **six total ratings from one pre/post single item are not equivalent to six different NASA-TLX-style questions after each session**.

## Automated mechanical preflight (NOT an approval)

The new local-only `python -m scripts.pilot_content_review_audit` compares the reviewer-register IDs, concepts and form/action against the **actual** items/resources CSV, counts pending/incomplete fields, hashes the assets and detects the rehearsal-only fatigue questionnaire. This check should report **BLOCKED** and use exit code **2** until the work is complete; even full administrative metadata does not verify content accuracy, rights or signatures.

```bash
PY="$HOME/multi_agent_research/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m scripts.pilot_content_review_audit \
  > "$HOME/ijcai_content_readiness_20261110.json"
test "$?" -eq 2 && echo "Expected: independent review still blocked"
```

The report contains source-file SHA256 fingerprints but no participant information. Reviewer approvals should be privately bound to the final immutable content version, **not** entered as invented green flags in the public repository or used to override the final institutional release gate.
