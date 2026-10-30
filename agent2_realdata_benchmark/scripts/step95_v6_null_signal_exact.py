"""Exact finite-state V6 response-signal audit under a stationary latent state.

No simulator or held-out seeds are accessed. This calculates *signal-onset*
probability, NOT recovery-action probability or educational efficacy.
The null assumes independent, identically distributed binary observations
of one concept with constant P(correct) across n observations.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json

# State: correct streak (capped at 2), prior mastery evidence,
# consecutive wrong-after-evidence (capped at 2), active signal,
# whether ANY signal onset has occurred in the n-response window.
INITIAL = (0, False, 0, False, False)


def transition(state: tuple, correct: bool) -> tuple:
    streak, evidence, wrong, active, seen = state
    if correct:
        streak = min(2, streak + 1)
        evidence = evidence or streak == 2
        return (streak, evidence, 0, False, seen)
    if evidence:
        wrong = min(2, wrong + 1)
        new_onset = wrong == 2 and not active
        return (0, evidence, wrong, active or new_onset, seen or new_onset)
    return (0, False, 0, False, seen)


def exact_signal_probability(correct_probability: Fraction, observations: int) -> Fraction:
    """Return P(at least one onset), exactly as a rational number.

    Assumptions: fixed-state concept, iid responses, constant q; no learning,
    forgetting, resource actions or belief policy. Its purpose is a *null* audit.
    """
    if isinstance(correct_probability, bool):
        raise ValueError("q must be a rational probability")
    try:
        q = Fraction(correct_probability)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError) as e:
        raise ValueError("q must be a rational probability") from e
    if not 0 <= q <= 1:
        raise ValueError("q must lie in [0,1]")
    if type(observations) is not int or not 0 <= observations <= 200:
        raise ValueError("observations must be an integer between 0 and 200")
    dist = {INITIAL: Fraction(1)}
    for _ in range(observations):
        nxt = {}
        for state, weight in dist.items():
            for correct, likelihood in ((True, q), (False, 1 - q)):
                if not likelihood:
                    continue
                s = transition(state, correct)
                nxt[s] = nxt.get(s, Fraction(0)) + weight * likelihood
        dist = nxt
    return sum((weight for s, weight in dist.items() if s[4]), Fraction(0))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", nargs="+", type=int, default=[4, 8, 12, 20])
    args = parser.parse_args()
    q_values = {
        "mastered_nominal_slip_0_10": Fraction(9, 10),
        "mastered_noisy_slip_0_25": Fraction(3, 4),
        "never_mastered_guess_0_25": Fraction(1, 4),
    }
    result = {
        "synthetic_analytical_null_only": True,
        "model": "one concept, fixed mastery state, independent identically distributed responses",
        "event": "one or more V6 signal onsets, not recovery actions",
        "learning_or_forgetting_present": False,
        "source_of_probabilities": "V6 observation mechanism and Step 95 nominal/noisy slip and guess assumptions",
        "observations_per_concept": args.observations,
        "probability_of_at_least_one_signal": {
            label: {str(n): float(exact_signal_probability(q, n)) for n in args.observations}
            for label, q in q_values.items()
        },
        "analytic_four_observation_identity": "q^2 * (1-q)^2 (the only length-4 trigger string is CCWW)",
        "interpretation": "Any signal under this no-change null is a false indication of latent deterioration. Rates cannot be extrapolated directly to policy-selected answer streams.",
        "heldout_seeds_accessed": False,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
