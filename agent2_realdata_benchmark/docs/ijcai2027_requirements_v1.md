# IJCAI 2027 — Research Prototype Requirements v1

Status: Proposed requirements for team review.
Implementation approval: Not established.
Human study approval: Not established.

## 1. Primary objective

Produce a functioning, reproducible adaptive-quiz
application and a defensible AI research contribution
for IJCAI main-track resubmission.

Acceptance is not guaranteed.

## 2. Latest supervisor direction

The October 2026 team meeting established:

- Consider MCTS, POMCP and/or POMDP.
- Combine BKT and NeuralCD only if needed.
- Complete a functioning prototype application.
- Prepare testing with volunteer Master's students.
- Strengthen the next IJCAI main-track submission.

These instructions do not establish that a particular
planner, model combination or study protocol is approved.

## 3. Earlier proposed educational protocol

The previous supervisor documentation included:

- Behavioral Economics instructional material.
- Eight instructional concepts.
- Three quiz sessions.
- Main-question counts of 20, 20 and 15.
- Pre-test and distinct post-test questions.
- Bloom-level progression.
- Concept summary.
- Two-option easier question.
- Worked example.
- Socratic hint.
- Self-healing, greedy and fixed-order comparisons.

All these details require confirmation against
the latest supervisor decisions.

The previously proposed 75-participant study is
not equivalent to a small feasibility pilot.

## 4. Proposed research architecture

Separate the following components:

- Student-facing application and quiz engine.
- Item bank and item-to-skill mappings.
- Learner-state estimator.
- Difficulty or degradation event detector.
- POMDP generative model.
- Recovery planner and comparison policies.
- Assistance delivery and acknowledgement.
- Independent assessment and logging.
- Experimental evaluation and export.

Start with one justified estimator.

Introduce BKT/NeuralCD fusion only if comparative
evidence establishes its added value.

The POMDP simulator must distinguish assumed
learning effects from empirically validated effects.

## 5. Required planner evaluation

Compare the proposed planner against:

- Fixed-order or no-adaptation baseline.
- Greedy assistance selection.
- Existing one-step hypothetical selector.
- At least one clearly defined MCTS/POMCP policy.

Prespecify comparable simulation budgets.

Evaluate outcome, intervention burden, runtime,
model misspecification and abstention.

Do not claim improved real-world learning from
simulated intervention effects.

## 6. Preliminary integration direction

Prefer an explicit API boundary between frontend
and backend.

Earlier team materials proposed React, Flask
and SQLite.

Confirm those technologies and team ownership
before replacing them with another stack.

The backend must distinguish:

- Action proposed.
- Action offered.
- Action delivered.
- Action used.
- Assessment attempted.
- Assessment outcome recorded.

Do not expose answer keys before submission.

## 7. Study readiness

Before recruitment or collection of new personal
research data, establish required institutional
permissions, participant information, consent or
other appropriate legal basis, and data safeguards.

Prespecify the independent assessment outcome.

Distinguish feasibility findings from causal
learning-effectiveness evidence.

## 8. Scientific integrity

Preserve frozen Phase 6 artifacts.

Keep the held-out test gate closed until an
approved final evaluation protocol exists.

Avoid unsupported recovery theorem claims.

Retain review history, limitations and
reproducibility evidence for the resubmission.

## 9. Open team decisions

- Confirm instructional topic and item bank.
- Confirm frontend/backend responsibility.
- Confirm instructional action catalogue.
- Choose the initial belief-state model.
- Define POMDP transitions and observations.
- Approve the planner comparison protocol.
- Confirm application deployment requirements.
- Confirm pilot approval and evaluation protocol.
