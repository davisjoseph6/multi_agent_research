# Pilot question bank adapter — offline synthetic verification only

**2026-11-09. DRAFT, NOT APPROVED OR DEPLOYABLE. NO HUMAN ENROLLMENT.**

Branch: research/ijcai2027-pilot-bank-adapter-20261109, based on reviewed 67cba9e.

## What has been implemented

- An isolated item-bank reader `src/prototype/pilot_item_bank_draft.py` loads the existing **95 draft behavioral-economics questions** in `docs/rct_candidate_v1/items.csv`, validates exact form counts (16 pretest, 55 practice, 16 posttest, 8 recovery-DROP2) and uses the existing Item.public() method to exclude answer keys from returned question payloads.
- The **offline** `SyntheticPilotStore` gains an **optional** `items_path`. Count-only synthetic tests and the deployed `RCTCandidateEngine` remain unchanged.
- When bound, each synthetic QUESTION action contains its frozen item ID, concept, prompt and options; submitted option IDs are validated, correct/incorrect scoring is recorded transactionally with the action and request, and 16-item pretest/posttest totals can be reported once complete.
- A database using the item bank binds its schema version to the question CSV SHA-256. Reopening with a changed bank or with count-only mode refuses instead of silently changing the source.
- Existing 3-visit timeline, six proposed pre/post M-VAS responses, duplicate-request replay, pending actions across restarts and SQLite backup/restore continue in the offline model.
- New tests in `tests/test_pilot_bank_adapter_draft.py` check answer-key non-disclosure, all 87 individual MCQ responses, unique item IDs, scoring, visit-state recovery, score backup, bank hash mismatch, and invalid-choice rollback.

## Scientifically critical constraints

**NOT three-arm policy integration.** This adapter deliberately uses a **single fixed balanced practice order for ALL synthetic records**, derived from the existing V3 balanced schedule. It does **not** yet choose POMCP Arm A or greedy Arm B actions, invoke a recovery planner, deliver any of the 32 recovery resources, or randomize students into three distinct educational policies. This is only an item/answer-scoring and storage integration milestone.

It also does NOT implement real supervisor identity verification, signed release evidence, participant eligibility or consent, a validated M-VAS, student browser, accessible forms, or sufficient operational production controls. Institutional ethics, DPO, content review, instrument approval, independent QA, hardware and backup readiness remain blocking.

For a real pilot, separate next changes must integrate and scientifically verify **A=POMCP with up to two recovery resources/visit**, **B=greedy**, **C=balanced fixed**, including proper belief updates and no practice-budget consumption for optional recovery actions. Review time-on-task and bundled-intervention interpretation with statistician and PI.

Question text and correct answers are DRAFT; 95 questions and 32 resources have not received required expert review. Never assume code tests constitute subject-matter approval.

## How to verify locally on WSL

From a separate checkout in agent2_realdata_benchmark, after setting `PY` to your project Python binary:

```bash
"$PY" -m pytest -q tests/test_pilot_bank_adapter_draft.py tests/test_pilot_session_store_draft.py tests/test_pilot_measurements_draft.py tests/test_pilot_session_flow_draft.py
"$PY" -m pytest -q
```

Tests were committed but have **not** yet been executed in the user's WSL environment. The prior **1,328 tests** pass on baseline commit `67cba9e`. New bank tests may uncover bugs needing fixes.

**Never deploy this branch to demo.selfhealing-edu.fr or collect any actual participant information with it.**
