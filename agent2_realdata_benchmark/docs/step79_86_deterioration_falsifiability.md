# Steps 79 and 86 — Deterioration falsifiability gate

Status: **ENGINEERING DIAGNOSTIC ONLY — NO HUMAN STUDY AUTHORIZATION**.

## Finding

The current V3 generative model defines the target mastery state after every
learning action as `old or success`. It does **not** implement forgetting, hence
latent concept mastery is monotone. It cannot simulate a decrease in an already
mastered concept, regardless of how many synthetic sessions are run.

Simultaneously, BKT mastery **beliefs** can decrease following incorrect
observations, even if the latent state remains mastered. Therefore a decrease
in estimated mastery is evidence of a belief revision, **not necessarily a
learner having deteriorated**.

An initial deficit `(1 - average mastery)` is likewise not a deterioration
signal. Eight beliefs equal to 0.2 produce deficit 0.8 with no history.

## New additive diagnostic

`step79_deterioration.py` provides:

1. Version-checked paired binary anchor observations in chronological waves.
2. A one-sided exact conditional paired-discordance (McNemar/sign) calculation.
   This signals *response* decline only if losses predominate and the supplied
   nominal alpha criterion passes.
3. A separate nonstationary eight-concept **synthetic stress-test transition**
   with a configurable forgetting probability. It is **not** substituted into
   the original V3 planner; doing that would invalidate earlier results and
   require new policy and observation-model verification.

## Inferential limitations

The paired-discordance test assumes exchangeable discordance directions under
its null hypothesis; it **does not identify true latent forgetting**. Responses
must use comparable instruments, items, administration conditions and scoring;
reusing anchors can itself introduce memory/learning effects. A nominal p-value
is not automatically an approved trigger and requires multiplicity/power design
for sequential repeated monitoring. Item-response dependence and selection
bias may invalidate the simple interpretation. It does not account for
participant dropout or assessment noise and is not calibrated to real students.

Likewise, a forced forgetting probability of 1 is a *model falsification test*,
not a proposed empirical transition rate.

## Before treating deterioration as a scientific contribution

- Freeze a falsifiable definition: latent mastery loss, performance decline on
  comparable held-out items, or change-point in calibrated learning parameters.
- Distinguish deterioration detection from ordinary low initial mastery and
  from BKT posterior volatility caused by new evidence.
- Benchmark both stationary (no forgetting) and nonstationary (forgetting or
  context shifts) held-out simulated conditions; measure false alarms,
  detection delay, intervention use, opportunity costs and uncertainty.
- Evaluate against calibrated baselines, including non-learning and
  model-misspecification controls. Keep seeds, transition settings, and
  selected configurations separate from final held-out evaluations.
- Obtain educational measurement review, study protocol agreement, appropriate
  privacy and participant approvals before any real-student study.

No novelty or educational outcome benefit is established by this audit.
The evidence-score register should **not** automatically increase because
these files exist. External signoff for Step 79/86 is still outstanding.
