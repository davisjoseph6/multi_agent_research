# Step 95 — V6 observation-change candidate (development only)

**Status:** provisional algorithm design, **not** a demonstrated novel IJCAI result.

## Motivation

The original V5 and V3 policies selected exactly the same 825 decisions across
15 development runs (five seeds in each of three forgetting/noise scenarios).
A zero-belief-gain guard is consequently inactive under these settings.

## Candidate intervention

Keep an observation-only history for each concept. After two consecutive
correct answers, mark `mastery_evidence`. If two later consecutive incorrect
answers occur, raise a *possible deterioration* signal. This is not proof of
latent forgetting; lucky guesses and noisy observations can generate it.

When a signal is active and a resource is available, choose a WORKED_EXAMPLE if
its nominal incremental expected gain, minus its incremental cost, plus a
**prespecified hypothetical** risk credit of 0.012 is positive. Otherwise
choose a practice question by estimated gain and an observation-coverage
regularizer of 0.003/(1+number_of_observations_for_concept).

All weights are synthetic development assumptions and must be sensitivity
analyzed. The controller does not access latent true mastery or future results.
Recovery resource budgets remain capped at two per session; total 55 actions.

## Comparison protocol

Reuse the same exogenous event generator, fixed session lengths, cost functions,
stationary model misspecification and development seeds as the existing Step 95
benchmark. Include original fixed, greedy, heuristic, V3 and V5 policies;
report raw mastery, nominal net mastery, and intervention costs separately.

Hold out seed range starting at 200000. This script **has no held-out switch**.
It is not the primary confirmatory analysis.

## Failure conditions

This idea is rejected as the lead method if it fails to produce a reproducible
advantage under prespecified conditions, if performance is overly dependent on
risk-credit weighting, or if no independent novelty argument is found.

Additional requirements: action traces, false-alarm and detection-delay audits,
strong prior-art baseline comparisons, computational time, variation of planning
budgets, paired confidence intervals, and fully documented seed handling.

## Evidence boundary

Passing tests establishes code behavior only. Neither latent deterioration,
causal educational benefit, novelty nor a real-human recovery effect has been
proven. External expert review and protocol approvals remain outstanding.
