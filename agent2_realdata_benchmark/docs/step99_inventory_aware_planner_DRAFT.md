# Step 99 — Consumable-inventory POMCP planning audit (development-only)

**Status:** Research-only algorithm candidate, untested on real students and not authorized as an amendment to any experimental protocol. Human RCT group A remains the original V3 POMCP.

## Implemented

A separate additive planner `src/prototype/step99_inventory_aware_pomcp.py` preserves the **hypothetical learning/observation rates and costs** of V3 but changes the internal planning state to include:

- Eight remaining practice-question counts, initialized to `(7,7,7,7,7,7,7,6)`.
- Current session (0, 1, 2) and number of practice answers within the session.
- At most two remaining recovery resources in each session.
- Exact transitions from 20 to 20 to 15 consumed practice questions, with the resource budget resetting at session boundaries.
- State-dependent legal actions: no question or resource on a concept whose practice-question inventory is depleted, in correspondence with the **current V3 root candidate filter**.

The POMCP-style UCT search consumes simulated questions on every forward transition, including rollouts. A recovery action uses a resource slot but not a practice-question slot. End-of-study is terminal after all 55 practice questions. The public selection interface consumes only mastery *beliefs* and fully observable inventory progress, not latent mastery. Internal sampled latent states are the unchanged synthetic POMCP assumption.

## Why this is a valid milestone but not a publication result

The original V3 internal simulation fixes its initial eligible practice concepts for every future simulated action, and does not count remaining individual questions. Step 99 removes that specific internal search inconsistency. Whether this materially changes decisions and improves robust downstream outcomes is *not established*. A direct head-to-head would still need matched budget/costs, independent outcomes, fixed development scenarios, multiple random seeds, stronger baselines and appropriate uncertainty quantification. The new UCT planner is not calibrated, and this correction by itself is **not novel AI**.

**Remaining fidelity gaps:** the trial selects specific question IDs; Step 99 tracks per-concept counts but not item identities/difficulty or constraints around recovery content. Real participants may skip/withdraw and sessions have fatigue measures, none of which are simulated here. In its November 2 correction, Step 99 enforces a QUESTION as the first action of each session, inside root selection, simulated tree expansion, and rollout legality. The deployed V3 warmup **chooses its question greedily using belief, item difficulty, and item ID**; Step 99 still uses POMCP to choose among warmup question concepts and has no item identity. Accordingly it is **not** an execution-equivalent RCT planner. A 55-question full protocol has far more decisions when optional recovery resources are included. The hypothetical simulator also omits explicit forgetting. No global drift or human recovery claim follows.

## Verification commands (from agent2_realdata_benchmark)

```bash
python -m pytest -q tests/test_step99_inventory_aware_pomcp.py
python -m src.prototype.step99_inventory_aware_pomcp
python -m pytest -q
git status --short
git rev-parse HEAD
```

## Strict next scientific decision

1. Verify all Step 99 tests, then separate the code-mechanics milestone from efficacy.
2. A first QUESTION is now enforced; decide whether to model exact greedy warmup item selection, item identities, and observation-related accounting in the research environment before a matched baseline study.
3. Freeze a development-only outcome design using the same inventory-consuming simulator for all competitors, not synthetic values from different simulator versions. Identify primary and secondary comparisons before evaluating them.
4. Preserve all existing negative V6 ablations, the V3 counterexample, frozen Phase6 TEST membership and human enrollment block.
5. Seek expert literature and research-supervisor review for any actual theoretical or algorithmic novelty claim.
