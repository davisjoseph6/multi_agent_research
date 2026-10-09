# IJCAI 2027 — Adaptive Quiz Prototype Charter v1

Status: Initial implementation proposal.
Source: Research-team meeting reported October 9, 2026.
Detailed design approval: Not yet established.

## Supervisor's direction

1. Consider MCTS, POMCP and POMDP planning.
2. Combine BKT and NeuralCD only if justified.
3. Complete a functioning adaptive quiz application.
4. Prepare evaluation with volunteer Master's students.
5. Strengthen the evidence for IJCAI main-track resubmission.

## Proposed minimum viable system

The application shall provide:

- A functioning student quiz interface.
- An explicitly defined instructional topic and item bank.
- Question-to-skill mappings.
- Pre-response predictions and sequential belief updates.
- Detection of potential learning difficulties.
- POMDP-based recovery decision modelling.
- MCTS/POMCP planning evaluated against simple baselines.
- Permission and resource-availability checks.
- Defined instructional assistance resources.
- Recorded assistance offers, delivery and use.
- Independent unhinted recovery probes.
- Session completion and research-result export.
- Reproducible tests and synthetic evaluations.

## Scientific scope

Use one knowledge estimator initially.

Evaluate additional estimators only if they provide
a defensible, measurable contribution.

The planning simulator's assumed intervention effects
are not empirical causal estimates.

Compare planning quality, computation, assistance
burden and recovery outcomes under controlled assumptions.

Do not claim a mathematical recovery guarantee until
the executed policy satisfies its proof obligations.

## Human pilot

Do not recruit students or collect identifiable research
records before the necessary institutional reviews,
permissions and participant protections are established.

Pilot findings must be distinguished from confirmatory
educational-effectiveness evidence.

## Preservation requirements

Do not modify frozen BKT or NeuralCD baseline artifacts.

Do not replace frozen event-detection policies.

Do not reinterpret historical help requests as
randomized interventions.

Do not access held-out test outcomes prematurely.

The Phase 6 held-out test gate remains closed.

## Decisions still required

- Confirm the instructional subject and item bank.
- Approve the full assistance-action catalogue.
- Define the POMDP transition and observation models.
- Choose the initial planner and comparison baselines.
- Establish the application deployment environment.
- Establish the institutional human-study approval path.
- Register the pilot outcomes and analysis.
