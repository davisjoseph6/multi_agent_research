# IJCAI 2027: Steps 72–123 implementation and release gates

**READ BEFORE USING.** This package is a **provisional, synthetic-only**
reference implementation. It does not supersede the 652-test baseline,
authorize human research, validate the original IJCAI paper's theorems, or
implement a complete, empirically calibrated eight-concept POMCP policy.

## Engineering boundaries

- All new code is additive: `study_v2.py`, `study_v2_runtime.py`, two scripts,
  and one new test module. It does not replace the old Group A/B/C demo.
- No participant authentication or public HTTP API is introduced. Synthetic
  participant identifiers must begin `SYN_`.
- Synthetic item text is **not** suitable for education or research assessment.
- Tests show internal logic, not learning, fidelity, psychometric validity,
  causal outcomes, production security or correct mathematical theorems.
- POMCP is a **one-concept synthetic proof of concept**, separate from the
  historical Group A policy. Do not claim the implemented Group A runs POMCP.
- SHA256 item-bank manifest is a version/change detector, not an endorsement.
- Recovery stages use one *episode* consisting of all four historical actions;
  max two episodes/session. This interpretation requires supervisor approval.
- `D > 0.5` when initial mastery=.2 is *initial uncertainty/low mastery*,
  **not proof of a decline**. The degradation trigger needs redesign and testing.
- Repeated scheduled practice across participants is allowed; within a learner,
  no normal practice item is repeated. This does not equate difficulty across arms.

## Mapping every step to the included code or outstanding work

| Step | Deliverable / evidence in this package | Status |
|---|---|---|
| 72 | Common `Decision` structure; Fixed/Greedy/RuleBased classes | Prototype; unify interfaces before live deployment |
| 73 | Deterministic policy code; docstrings and tests | Provisional; formal pseudocode/eligibility review pending |
| 74 | Rule-based A distinct from `OneConceptPOMCP` | Explicitly separated |
| 75 | Primary hypothesis A vs B | Decision pending |
| 76 | Secondary A vs C / B vs C | Decision pending |
| 77 | ITT estimand and covariates | Supervisor/statistician decision pending |
| 78 | Practice pool shared; selection may differ | Comparability/dose plan pending |
| 79 | `Belief.degradation`, bounded `RecoveryStatus` | Provisional; degradation/change semantics unresolved |
| 80 | `SCHEMA_VERSION`, deterministic RNG, bank SHA256 | Partial; complete environment manifest pending |
| 81 | This file, implementation boundary, and audit matrix | Preliminary design review; approval pending |
| 82 | Eight-dimensional `Belief`; synthetic latent state separate | Prototype |
| 83 | BKT slip/guess model, binary responses | Partial; timing/engagement models pending |
| 84 | Correct BKT posterior then learning transition; tests | Tested synthetic math |
| 85 | Explicit synthetic response/learning assumptions | Uncalibrated; empirical model pending |
| 86 | Threshold tests and false-trigger counterexample | Blocked on trigger definition/validation |
| 87 | All four recovery action names | Prototype |
| 88 | Two four-stage episodes/session, clear counters | Provisional semantics; review pending |
| 89 | Greedy weakest-mastery baseline with deterministic ties | Tested |
| 90 | Rule-based recovery class and finite-action tests | Tested synthetic software only |
| 91 | One-concept generative POMDP in `OneConceptPOMCP` | Incomplete: eight-concept state/reward/model pending |
| 92 | One-concept UCT history-tree planner with rollouts | Incomplete: BKT belief update in history tree, full integration pending |
| 93 | No valid general recovery guarantee inferred | **Proof pending** |
| 94 | Counterexamples for threshold and bounded recovery | Partial; more mathematical falsification needed |
| 95 | Multi-seed simulated benchmark script | Software-only; independent evaluator/calibration pending |
| 96 | Item schema includes eight concepts and Bloom tags | Blueprint allocation and expert review pending |
| 97 | 16 pretest + 16 posttest synthetic forms, distinct IDs | Parallel-form validation pending |
| 98 | Individual scores available in mock | Transfer/retention outcome specification pending |
| 99 | 64 synthetic unique practice questions for 55 presentations | Real authored bank pending |
| 100 | Item/option/answer/difficulty schema | Real questions and explanations pending |
| 101 | Review status and mechanical release gate | Independent subject-matter review pending |
| 102 | Structure/coverage tests only | Psychometric calibration and reliability pending |
| 103 | Public item excludes answers; no pre/post feedback in runtime | Full content-leak/security audit pending |
| 104 | Actions defined and logged, DROP_2 item schema | Validated multi-concept resource content pending |
| 105 | Six integer fatigue answers/session in mock | Validated questionnaire wording/scoring pending |
| 106 | Versioned bank fingerprint and reviewed-only gate | Content freeze/reviewer approval pending |
| 107 | Typed `Item` bank, `validate_bank`, server-side answer key | Local reference implementation |
| 108 | SQLite `SyntheticProtocolEngine` runs A/B/C | Synthetic only; no live interface |
| 109 | `FixedPolicy`, deterministic ID-order selection | Tested |
| 110 | `GreedyPolicy`, belief-directed selection | Tested |
| 111 | `RuleBasedSelfHealing` and bound recovery | Tested as synthetic software |
| 112 | One-concept POMCP candidate, **not** Group A integration | **Not complete** |
| 113 | Durable 16-item baseline response path | Synthetic only |
| 114 | Durable 20/20/15 practice stages | Synthetic only |
| 115 | Durable 16-item posttest without answer-feedback leakage | Synthetic only |
| 116 | Durable six-value fatigue record after each session | Synthetic-only, unvalidated measure |
| 117 | Resource acknowledgement action path, DROP_2 | Browser presentation and usability pending |
| 118 | Only `SYN_` IDs; does **not** provide real authentication | **Not complete**; actual consent/identity/revocation pending |
| 119 | SQLite re-open durable pending action and response replay | Partial; operational restart/multi-device testing pending |
| 120 | Synthetic protocol event log and request idempotency | Partial; timestamps/tamper evidence/retention pending |
| 121 | Synthetic-only JSON and SQLite audit export | **Not** an approved real-data export workflow |
| 122 | 31 focused tests, invalid actions, concurrency retry, version mismatch | Partial; accessibility/load/penetration tests pending |
| 123 | Full three-arm, three-session, pre/post/fatigue scripted dry run | Tested with synthetic-only records |

## Copy/paste command sequence

From the existing repository root `~/multi_agent_research` (activate your venv):

```bash
cd ~/multi_agent_research/agent2_realdata_benchmark
python -m py_compile src/prototype/study_v2.py src/prototype/study_v2_runtime.py
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider tests/test_steps72_123_v2.py
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 python scripts/step95_synthetic_bench_v2.py --seeds 5 --participants 9
PYTHONDONTWRITEBYTECODE=1 python scripts/step123_mock_study_v2.py --participants 9 --seed 71 --output results/step123_mock_study_v2.json
cd ..
git diff --check
git status --short
```

Expected **local** focused results: 31 tests passed. **Estimated** complete
suite if prior 652 stay unchanged: 683 passed. Verify on your own machine.

`--output` refuses to overwrite the previous result. Use a unique output path
for each run. Keep generated synthetic JSON and SQLite out of public commits.

## Exit criteria before any study release

1. A named PI and independent statistician agree on the exact Group A algorithm
   (rule-based recovery vs POMCP) and prespecified comparisons.
2. Full, reviewed, calibrated educational items and independent outcome forms.
3. A proof audit of the mathematical guarantees; replace invalid guarantees.
4. A complete eight-concept planner, if POMCP is central, with comparative
   computational evidence and bounded resource use.
5. A secured, accessible, reliable three-session browser implementation,
   authenticated participants, privacy-preserving logging and approved data flows.
6. Protocol, power, governance, consent and any required ethics/DPO review.
7. Authorized human pilot, followed by definitive RCT only after approvals.

Never describe the synthetic practice scores as human learning gains.
