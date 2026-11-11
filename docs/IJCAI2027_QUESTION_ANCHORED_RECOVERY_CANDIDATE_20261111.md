# IJCAI 2027 — Last incorrect question recovery candidate

**Status 11 Nov 2026: synthetic engineering candidate, NOT approved
for a real-student trial, and NOT an amendment to the frozen V3 protocol.**

## Rationale and behavior

The previous deployed unified fictional browser (port 8767) presents
concept-level recovery: POMCP selects an action and concept, DROP_2 chooses
a separately authored remediation item for that concept, and the
Socratic Hint / Concept Summary / Worked Example show the relevant
concept-wide source resource. This is *not* necessarily connected to
the most recent incorrect practice question. Do not imply otherwise.

This branch implements an **explicit opt-in variant**:
`--question-anchored-recovery` on a fresh fictional DB.

1. When an Arm A learner answers a **practice** question incorrectly,
   save the item's ID, chosen wrong option ID and current visit inside
   the private synthetic policy record. Never derive this from pretest,
   posttest, or a recovery retry. Reset on a new visit. The browser
   receives no staff/participant secret, full answer key or treatment arm.
2. Until that record exists, the V3 planner may offer only its ordinary
   practice questions. The default V3 mode is unchanged.
3. Once a mistake exists, POMCP still chooses among ordinary practice
   actions for all available concepts, but recovery actions are
   restricted to the **most recent incorrect practice item's concept**.
   This changes the planner's action space relative to V3 and hence
   **requires a scientific protocol decision** before a real RCT.
4. `DROP_2` re-presents the **original incorrect practice stem** with
   exactly two options: the previously chosen wrong answer and the
   correct answer. Option order follows the original item. The
   answer key is not marked or returned; the backend validates
   submission against only the *visible* two IDs. This uses the
   authored 55-question practice bank rather than the separate
   eight concept-level recovery DROP_2 items (which remain in the
   frozen 95-item candidate bank for legacy mode).
5. `SOCRATIC_HINT`: show the previously missed stem/choice, the authored
   concept-level guiding hint and a deterministic reflection prompt
   that does **not** reveal the correct option.
6. `CONCEPT_SUMMARY`: show the authored concept summary beside the
   mistaken question, asking the learner to apply the principle back
   to their scenario.
7. `WORKED_EXAMPLE`: present the existing authored *separate*
   analogous example and a comparison prompt, not a solved copy of
   the original assessment question.

These three text interventions are **context-linked**, not separately
authored misconception-specific tutorials. They require expert review
to evaluate real educational utility. There is **no runtime LLM**,
and no assertion that the present wording corrects misunderstandings.

The candidate retains the existing Arm A maximum of two resources
per visit, 20/20/15 distinct practice questions across three visits,
and default B/C behavior. Recovery is not an additional practice
question. Each action and selected item is persisted in the synthetic
SQLite event store and retried by action/request IDs.

## Reproduce without modifying the working VPS

From WSL:

```bash
cd ~/multi_agent_research
git fetch origin
git worktree add --detach ../ijcai_error_anchored_review_20261111 \
  origin/research/ijcai2027-question-anchored-recovery-demo-20261111

cd ~/ijcai_error_anchored_review_20261111/agent2_realdata_benchmark
PY="$HOME/ijcai_http_acceptance_20261110/agent2_realdata_benchmark/.venv/bin/python"
"$PY" -m pytest -q \
  tests/test_pilot_question_anchored_recovery_demo.py \
  tests/test_pilot_question_anchored_browser.py \
  tests/test_pilot_three_arm_store_draft.py \
  tests/test_pilot_unified_fictional_browser.py
```

**Only after CI and local tests pass**, the operator may create a
separate fictional local preview (new empty database and port 8769;
do not reuse 8767's existing database):

```bash
mkdir -p "$HOME/ijcai_error_anchored_new_demo_state"
chmod 0700 "$HOME/ijcai_error_anchored_new_demo_state"

"$PY" -m scripts.pilot_unified_fictional_browser \
  --question-anchored-recovery --port 8769 \
  --db "$HOME/ijcai_error_anchored_new_demo_state/fictional_admission.sqlite3"
```

On the same computer open http://127.0.0.1:8769/. If the new
server is manually run on a VPS, bind only 127.0.0.1 and forward 8769
via an independent SSH tunnel, never configure a public proxy.
To advance the selected fictional fixture after visit 1/2, the
operator must also supply `--question-anchored-recovery` to the
separate offline visit CLI and the **same new DB path**. Do not
silently change the installed 8767 service.

## Scientific questions requiring supervisor/expert review

- **Treatment mechanism:** Is the intended Arm A effect the
  adaptive recovery decision, a misconception-specific support
  intervention, or the combined treatment? This variant changes
  Arm A relative to the frozen protocol. Decide before enrolment.
- **Instructional validity:** Are the hint, example and concept
  summary genuinely relevant to each item/scenario and its distractor?
  The present scaffolding is deterministic and mostly concept-level.
  Reviewer approval of item-level mappings is still required.
- **Two-choice observation bias:** Correctness after reducing
  four answers to two has a higher chance level; BKT/POMCP
  observation assumptions must be recalibrated rather than treating
  that event as equivalent to an ordinary four-choice practice item.
- **Assessment leakage and carryover:** Restrict to practice errors,
  and decide whether an intervention should reveal evidence of
  a correct answer in a pretest/posttest context (this candidate
  avoids touching those assessment forms).
- **Dose, latency and effects:** Recoveries consume an individual
  resource budget; they may not occur at all if the planner chooses
  ordinary practice. Do not promise a hint after every wrong answer.
- **Measurement:** Proposed fatigue and all question resources still
  require external pedagogical, psychometric and ethics review.

**Go for an isolated synthetic demonstration only, once verified.
No real-student hosting or claims of an approved treatment.**
