# Step 95 — V6 mechanism, negative control and ablation audit

**Status:** development-only, hypothetical synthetic learners; not a frozen or approved confirmatory protocol.

The five-seed V6 results are insufficient to show that the *deterioration intervention* is useful. V6 differs from V3 in both (a) practice concept selection and (b) recovery allocation. Thus a V6-versus-V3 difference does not isolate the recovery mechanism.

## New development-only checks

- Independently replay the original V6 episode and fail closed if any primary output differs.
- Within the same V6 practice-selection architecture, compare full V6 to **recovery disabled**. This removes recovery but keeps its observation-based practice policy and observation history. Under the same exogenous events, later trajectories may diverge legitimately.
- Compare the original V6 to **risk_credit=0** and **coverage_weight=0** ablations, separately; do not adjust these weights after examining heldout data.
- Include *fixed* and *greedy* baselines under identical event keys, session lengths, and nominal costs.
- On the synthetic simulator only, count resource triggers where latent mastery is false; subdivide those according to whether a true mastered-to-unmastered forgetting transition was recorded and had not yet been reversed by learning. Being unmastered after two wrong answers **does not prove forgetting**.
- Stationary forgetting=0 is a crucial negative control: it can produce response-pattern alarms but no true latent forgetting events.
- Provide paired seed-level directional counts and descriptive bootstrap intervals. These are **not confirmatory intervals** because the design has already seen development data.

## Interpretation limits

`forgotten_and_unmastered_at_trigger` is a strict proxy for a simulated forget event since the last simulated learning event, *not* a validated deterioration label. There is no measured human calibration or evidence of clinical/educational detection quality. The no-recovery ablation estimates an **in-simulator comparative policy effect**, not a real-world causal effect. Cost parameters, simulation dynamics and temporal response model remain hypothetical.

The true latent state is only inspected by the independent episode audit **after** controller choice and for attribution; no latent truth is supplied to the policy. Existing V3/V5/V6 code remains unchanged. Only development seeds are accessible; the held-out range beginning at 200000 is blocked.

## Scientific go/no-go

Do not claim the deterioration mechanism is effective if full V6 fails to improve the prespecified objective versus its **own no-recovery ablation** and against strong baselines. Do not choose risk-credit or coverage parameters by searching for the best heldout score. Preserve negative cases, including scenarios where fixed practice wins. An IJCAI novelty comparison, stronger baselines, model sensitivity, formal mathematical results, independent review and suitable sample size/power remain necessary.

## Isolated reference development run, 100 seeds per scenario

The following output was generated with the unchanged V6 controller whose
`src/prototype/step95_v6_decline_candidate.py` SHA-256 was
`d6d3c3505f27199455488c1fa68a4d9db48e8b58974c5c6e8174b924d7fb9a90`.
The audit's independent simulator reproduced the original V6 outputs seed by
seed. All five scenarios used development seeds 100000..100099.

| Scenario | V6 nominal net | V6 with no recovery | Difference (V6 minus no recovery) | V6 recovery triggers | Triggers with recorded actual forgetting |
| --- | ---: | ---: | ---: | ---: | ---: |
| stationary_nominal | 0.4940 | 0.4925 | +0.0015 | 25 | 0 |
| slow_forgetting | 0.2222 | 0.2213 | +0.0010 | 17 | 9 |
| rapid_forgetting | 0.0236 | 0.0238 | -0.0002 | 2 | 2 |
| noisy_slow_forgetting | 0.2189 | 0.2188 | +0.0002 | 12 | 6 |
| weak_learning | 0.1333 | 0.1350 | -0.0017 | 5 | 3 |

The numbers are rounded for this table; see the exact reference JSON shipped
in this package. **Stationary alarms cannot represent actual forgetting**:
there were 25 resource triggers when forgetting probability was exactly zero.
The controller is therefore a response-pattern policy, not a validated
forgetting detector. Results do not establish an intervention advantage.

The sample size and design were explored on development data and may have
been informed by previous tests. The reported bootstrap ranges are descriptive,
not confirmatory, and the reference result must never be relabeled as an
independent held-out result.
