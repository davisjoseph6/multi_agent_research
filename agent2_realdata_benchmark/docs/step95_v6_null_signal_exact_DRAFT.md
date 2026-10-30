# Step 95 — Exact no-forgetting response-signal audit (DRAFT)

## Audit scope

This audit calculates the probability that V6's history-based `signal_onsets`
becomes positive **even when a concept's latent mastery never changes**.
It uses the exact `ObservationChangeController.observe` state machine, with an
independent finite-state dynamic program cross-checked by exhaustive response
sequence enumeration against the real V6 class. All calculations are analytic
probabilities under a deliberately simplified stationary independent-response
null, **not simulations of students** and not human estimates.

## Null and event

Let each response for a single concept be independent Bernoulli(q), where
q=P(correct), with no learning or forgetting. V6 marks `mastery_evidence`
after two consecutive correct responses; that evidence persists. After it,
two incorrect responses generate a possible decline signal. On a subsequent
correct response, the active signal clears, and a later signal may recur.

The exact finite-state calculation tracks whether **at least one** signal
onset occurs in the first n *observations of this same concept*. It does not
calculate the probability that V6 chooses a WORKED_EXAMPLE: that also requires
an available budget and a positive recovery advantage.

For exactly four observations, a signal onset requires the unique order
`CCWW`, so the event probability is exactly `q²(1−q)²`.

For the stated observation assumptions:

- mastered with nominal slip 0.10: q=0.90, probability 0.0081 per four observations;
- never mastered with guess 0.25: q=0.25, probability 0.03515625;
- mastered with noisy slip 0.25: q=0.75, probability 0.03515625.

Thus the signal can arise without any deterioration, and its probability
under a never-mastered latent state is **higher** than under the nominal
always-mastered state for the minimal four-response window. This does *not*
mean the signal is globally anti-informative; conditionals on past responses,
state transitions and selection mechanisms are more complicated.

## Limits and action items

1. The independent-response null does not simulate learning, forgetting,
   policy-selected items, concept scheduling or the belief filter. Its rates
   **must not** be treated as false-positive rates in the actual full episode.
2. The number of observations *per concept* is not the 55 total practice slots.
3. A detector's correct evaluation requires a specified target event
   (e.g. mastered-to-unmastered transition), detection window, false alarm
   denominator, detection delay and missed detections.
4. The existing V6 100-seed mechanism ablation showed near-zero improvement
   against V6 with recovery disabled. The present analysis offers a possible
   mechanistic explanation; it is not a causal proof of that result.
5. Do not claim that V6 detects true forgetting, improves learning or has
   IJCAI-level novelty based on this audit.
6. Do not access held-out benchmark seeds until a policy and protocol are
   genuinely frozen, with independently auditable change control.

## Scientific conclusion

A two-correct/two-wrong pattern is an insufficiently discriminating signal
of latent deterioration by itself. A future method should explicitly model
learning, forgetting and observation noise, quantify uncertainty, and pass
an equal-budget no-recovery ablation before being considered as a paper's
central methodological contribution. This conclusion is mathematical and
does not constitute a publication-grade novelty or efficacy result.
