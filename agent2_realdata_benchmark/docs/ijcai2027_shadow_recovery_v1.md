# IJCAI 2027 — Shadow Recovery Integration v1

Status: Local-only synthetic research demonstration.

## Purpose

Connect the existing BKT estimator, risk detector,
recovery controller and POMCP-style planning baseline.

## Timing

An accepted practice answer updates BKT exactly once.

The updated BKT model predicts correctness for a
hypothetical future same-skill practice opportunity.

That prediction is passed to the existing detector.

The POMCP solver receives the current mastery belief,
not the predicted correctness probability.

## Scientific boundaries

The risk threshold is illustrative and uncalibrated.

The POMDP transition parameters are hypothetical.

The existing model identifier bkt_v1 is reused as a
bridge schema label, not as evidence that a fitted
ASSISTments model is calibrated for this quiz.

Planning never modifies the actual BKT state.

The simulated permission flag is not ethics approval,
student consent or authorization to deliver assistance.

The planner result is stored internally in memory.

The current API continues to deliver no intervention.

No assistance is delivered before the independent probe.

The current quiz contains only one practice item,
so the hypothetical next-practice target is not yet
a concrete item in the item bank.

## Next requirements

- A versioned and approved item bank.
- Multiple practice items with explicit skill mappings.
- Validated and calibrated belief estimation.
- A clearly specified planning intervention target.
- Durable, privacy-protected research event logging.
- Explicit real-world permission and delivery checks.
- Reproducible comparisons with simpler policies.
- Institutional approval before any participant study.

The held-out test gate remains closed.
