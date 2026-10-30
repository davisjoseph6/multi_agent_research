"""Independent finite-path oracle for the two-state learn/forget HMM.

Not a new cognitive model or a data-fitted estimator. Enumerates every latent
state trajectory explicitly with rational weights, then conditions on observed
answers. Can validate short sequences, but exponential runtime prohibits long
horizons. No held-out seeds or human data are used.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import log
from typing import Sequence


def rat(x: float | Fraction) -> Fraction:
    """Exact decimal representation for externally supplied float parameters."""
    if isinstance(x, bool):
        raise ValueError("Boolean probability is invalid")
    p = Fraction(str(x))
    if p < 0 or p > 1:
        raise ValueError("Probability outside [0, 1]")
    return p


@dataclass(frozen=True)
class OracleStep:
    index: int
    prior_mastery: float
    posterior_mastery: float
    recent_forgetting_posterior: float
    predictive_next_mastery: float
    observation_likelihood: float
    cumulative_log_likelihood: float


def enumerate_paths(
    responses: Sequence[bool | None],
    learning: Sequence[float],
    *,
    initial_mastery: float,
    slip: float,
    guess: float,
    forget: float,
) -> tuple[OracleStep, ...]:
    """Enumerate every state path; calculate exact rational conditional masses.

    State t produces response t, followed by a transition to state t+1.
    The last-forgetting event at time t is S_(t-1)=1 and S_t=0.
    """
    if len(responses) != len(learning):
        raise ValueError("Each response must have an action learning rate")
    if len(responses) > 9:
        raise ValueError("Path oracle restricted to at most nine steps")
    p0, sl, gs, f = map(rat, (initial_mastery, slip, guess, forget))
    # The keys are COMPLETE latent trajectories: not the filter recursion.
    paths: dict[tuple[int, ...], Fraction] = {
        (0,): 1 - p0,
        (1,): p0,
    }
    output: list[OracleStep] = []
    for t, (y, l) in enumerate(zip(responses, learning)):
        if y is not None and type(y) is not bool:
            raise ValueError("Responses must be boolean or None")
        learn = rat(l)
        before = sum(paths.values(), Fraction())
        prior = sum((w for h, w in paths.items() if h[-1]), Fraction()) / before
        def likelihood(last_state: int) -> Fraction:
            if y is None:
                return Fraction(1)
            q = (1 - sl) if last_state else gs
            return q if y else 1 - q
        observed = {h: w * likelihood(h[-1]) for h, w in paths.items()}
        evidence = sum(observed.values(), Fraction())
        if evidence == 0:
            raise ValueError("Observation impossible under enumerated model")
        posterior = sum((w for h, w in observed.items() if h[-1]), Fraction()) / evidence
        recent = sum(
            (w for h, w in observed.items() if len(h) >= 2 and h[-2:] == (1, 0)),
            Fraction(),
        ) / evidence
        # Propagate EVERY observed path through BOTH successor states.
        new_paths: dict[tuple[int, ...], Fraction] = {}
        for history, mass in observed.items():
            p_next_mastered = (1 - f) if history[-1] else learn
            new_paths[history + (1,)] = mass * p_next_mastered
            new_paths[history + (0,)] = mass * (1 - p_next_mastered)
        predicted = sum((w for h, w in new_paths.items() if h[-1]), Fraction()) / evidence
        output.append(OracleStep(
            t, float(prior), float(posterior), float(recent), float(predicted),
            float(evidence / before), log(float(evidence)),
        ))
        paths = new_paths
    return tuple(output)
