# IJCAI Step 95 — Real observational predictive benchmark: protocol DRAFT

**Status:** development-only, NOT a causal recovery study or externally validated generalization. Uses authentic data only after the researcher obtains it from the original steward under the applicable terms. The script never downloads, republishes or sends records to a third party. All demonstrations/tests use invented records.

## Reviewer motivation

The IJCAI-ECAI 2026 review of *Self-Healing Adaptive Quizzes via Belief-Space Modular Decision Architecture* criticized its exclusive use of synthetic learners, underspecified recovery actions, opaque algorithm explanations and questionable global healing guarantees. Real-world held-out next-response prediction directly addresses the **simulated-only state-estimation** criticism, but **cannot** answer whether the controller's actions cause improved mastery.

## Approved, reproducible source candidate

The maintainers of the ASSISTments 2009–2010 Skill Builder dataset state that the data are free to use and ask researchers to cite the original dataset URL. Prefer the **corrected deduplicated student–problem release** linked at:

https://sites.google.com/site/assistmentsdata/home/2009-2010-assistment-data/skill-builder-data-2009-2010

Record the exact provenance, download date, terms and SHA-256; consult institutional guidance on handling pseudonymized student data. Do not upload or commit raw student logs. Do not use FoundationalASSIST unless access has separately been granted under its gate and conditions (CC BY-NC and responsible-use requirements).

## Predefined initial protocol

1. Input: student identifier, single skill identifier (or compound skill token, explicitly preserved), per-student chronological order, and first-attempt correctness. Restrict to original problems when `original` is supplied. Reject duplicate student/skill/order events; use the corrected source if duplicates are present. No imputed missing skills.
2. Deterministic **student-disjoint** 60% training, 20% development, 20% **sealed test** via fixed hash salt. Exact fractions vary with finite samples. No student crosses splits. The script evaluates **training and development only**, and NEVER scores sealed-test students.
3. Compare constant-correctness baseline (training prevalence only), two-state Bayesian knowledge tracing without forgetting, and the same model with forgetting. Fit the fixed small parameter grids to **training** log loss only. Freeze model parameters before the first development evaluation; further exploratory revisions must be acknowledged. Models are run through the committed `TwoStateFilter` implementation.
4. Primary diagnostic: next-response development **log loss** (model selection on train) and Brier score (reported descriptively). Student-cluster paired bootstrap intervals are descriptive, not confirmatory. Report per-split student/event counts and invalid/filtered record counts.
5. To avoid label leakage, compute each predicted response probability from **pre-response** mastery belief, then observe correctness, then execute the standard after-response transition. No future answer may influence that prediction.
6. All student identifier values and raw student responses stay in memory; only aggregates, source SHA-256, split sizes and a small predeclared parameter grid may appear in the JSON. Use the original data only under steward/institutional permissions. The final held-out real student split is sealed for a separately registered protocol; the synthetic Step 95 held-out split remains untouched.

## Limits, sources of bias, and go/no-go

- The original release's first-attempt `correct=0` can also mean a hint was requested. This induces outcome/assistance ambiguity: it is NOT a clean random correctness measurement. A subset of logs also contain scaffolding, which is excluded where flagged.
- Skill Builder stops after mastery criteria, so question-selection and stopping introduce non-random truncation and selection bias.
- Forgetting is applied per opportunity on a **specific skill**, not proportional to calendar time. Student-specific performance may depend on difficulty, feedback, hints, and unobserved factors; this simplified BKT is only a baseline.
- Held-out predictive calibration measures **responses**, not the unobserved binary mastery or forgetting events. No trace independently validates a latent forgetting label.
- ASSISTments covers **mathematics**, not the draft Behavioral Economics curriculum. Predictive transfer between subject domains is an untested hypothesis.
- Observational records do not reveal what the student **would have learned under the alternative recovery policy**. Do not call off-policy comparisons causal, especially when treatment logging/propensities and sequential ignorability are unavailable.
- If the forgetting model does not improve next-response prediction, keep that negative result. Even if it does improve prediction, more is needed for algorithmic novelty and a valid recovery claim.

## Acceptance for this development milestone

Verified student-disjoint split, no future-label leakage, legal data access, fully reproducible SHA-256, documented parameter grid, retained negative baselines, independently audited code, and a real-world development comparison with no human-study efficacy claim. Not equivalent to completion of Step 95's IJCAI acceptance or Step 123's human trial.
