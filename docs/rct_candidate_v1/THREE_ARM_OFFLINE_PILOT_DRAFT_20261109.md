# Three-arm persistent synthetic pilot adapter (review only)

**2026-11-09. DRAFT / SYNTHETIC-ONLY / NO HUMAN ENROLLMENT.**

This is a new isolated implementation in `src/prototype/pilot_three_arm_store_draft.py`, based on the previously passing `research/ijcai2027-pilot-bank-adapter-20261109` branch. It is NOT imported by the live `RCTCandidateEngine`, Flask, Caddy or Gunicorn and has no real participant API.

## Implementation and scientific provenance

The adapter instantiates the **existing V3 selector implementation**, rather than inventing a new policy:
- Arm A: the original eight-concept POMCP action selection with adaptive questions, first-question greedy warmup and up to two optional planner-selected recovery resources each visit (concept summary, worked example, Socratic hint, or DROP-2).
- Arm B: the original greedy question selection, **without** recovery resources.
- Arm C: the existing balanced fixed schedule, **without** adaptive mastery selection or recovery.

Pretest answers update a BKT posterior, but no instructional learning transition; practice and DROP-2 answers update the learner belief with the established BKT mechanism; posttest does not update a future learning state. The unreviewed 95-item bank and 32-resource bank are version-locked by SHA-256, alongside planner version, simulations and generative-assumption fingerprint. No action serializes an answer key to the public question payload.

Resources do **not** consume one of the 20+20+15 practice-question slots. The recovery budget resets per supervised visit and remains at most two per visit. The pilot transition model records one proposed M-VAS immediately before and after each visit's practice, and prohibits opening the next visit outside the provisional 72–120 elapsed-hour interval. Existing separate consent/authorization gates for human research remain **not implemented**.

The policy state (assigned arm, mastery estimates, distinct practiced item IDs and resource budget) is committed in the **same SQLite transaction** as the action offered or response recorded, including idempotency, audit and state progression. The system refuses to upgrade a populated bank-only database in place. Synthetic record IDs start `SYN_PILOT_`; callers supply arm and staff flags only as an *offline test fixture* (they are NOT a real randomized allocation or staff authorization process). The actual trial must require concealed randomization, independent staff authentication and institutional signed release evidence.

## Tests and status

`tests/test_pilot_three_arm_store_draft.py` tests full three-visit journeys for A/B/C, 55 unique practice questions, separate recovery-resource counts, the six pre/post M-VAS ratings, source hashes, restart, authorization/window refusals inherited from earlier tests, request replay, invalid/foreign actions and consistent backup restoration. Synthetic policy trials use 41 simulations for speed; the adapter defaults to the existing released prototype's 240 simulations. These new tests are committed but **have not been executed in the user's WSL environment**.

Run with the existing WSL Python virtual environment from `agent2_realdata_benchmark`:
```bash
python -m pytest -q tests/test_pilot_three_arm_store_draft.py
python -m pytest -q
```

The previous branch baseline contained **1,333 passing tests**. Six new tests imply 1,339 if all pass, but this remains a prediction. Any failures must be analyzed and fixed, not treated as passing without evidence.

## Not accomplished and explicit release blockers

- Not connected to the actual web/API, external HTTPS, real students, verified supervisor identity, institutional consent, invitation/bearer authentication or concealed randomization.
- **No human enrollment:** no permitted authorization bypass, no real database, no approved recruitment materials.
- Model transition assumptions are **synthetic** and not empirically calibrated. Planner implementation does not scientifically establish that the algorithm improves learning, nor that POMCP alone causes the effect.
- Arm A receives optional additional recovery resources that B/C do not; intervention is bundled and unequal resource/time exposure. Confirm estimand with PI/statistician.
- M-VAS is a **proposed** six-timepoint 0–100 measure; digital adaptation, wording, validation, languages and scoring method need sign-off.
- Expert item/resource reviews, pilot protocol/SAP approval, independent security/accessibility QA, infrastructure/concurrency/recovery testing, off-server encrypted backup and privacy/ethics signoff remain outstanding.
- Backups from this standalone synthetic SQLite rehearsal are **not encrypted or off-server** and do not meet operational human-research data controls.

Never merge or deploy this draft branch to the live IONOS fictional demo. Pilot infrastructure and the human-trial candidate must be separately frozen and independently accepted after formal approvals.
