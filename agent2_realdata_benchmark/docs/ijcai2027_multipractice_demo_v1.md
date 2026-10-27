# IJCAI 2027 — Multi-Practice Demonstration v1

Status: Local-only software-development fixture.

## Content

Bank version: loss_aversion_multipractice_demo_v1

One Behavioral Economics concept: loss_aversion.

Question sequence:

1. demo_main_1 — practice
2. demo_main_2 — practice
3. demo_main_3 — practice
4. demo_probe_1 — candidate independent probe

The original two-question demonstration remains available.

## Integrated functionality

The durable Flask API serves the expanded question bank.

SQLite persists accepted responses and session position.

BKT is reconstructed from committed practice responses.

Real POMCP-style shadow planning runs after practice
responses that are followed by another same-concept
practice question.

No planner actions are delivered to learners.

The independent probe does not produce a new
practice-belief update or shadow planning decision.

## Scientific limitations

All question content and Bloom labels are illustrative.

The questions have not been reviewed or validated by
the instructional supervisor.

The candidate probe is not independently validated.

There is no pretest or separate posttest form.

There is no actual assistance-offer or delivery mechanism.

The multi-practice questions test the same basic concept
and may have substantial content overlap.

POMCP transition parameters and risk thresholds are
hypothetical, not empirically calibrated.

Shadow events are stored in memory, not in the research
database.

No evidence of causal learning recovery is produced.

No real participant data may be collected.

## Next milestone

Design and implement an explicitly controlled
instructional intervention workflow.

Separate offer, acceptance, delivery and uptake.

Keep intervention actions outside independent assessment.

Agree on the educational content and experimental protocol
with the research supervisor before student recruitment.

The held-out test gate remains closed.
