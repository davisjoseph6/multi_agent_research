"""Outcome-risk and predictive-entropy signals for binary forecasts.

These are functions of a model's predicted response probability.
They are not estimates of epistemic uncertainty or true mastery.
This module does not access labels, datasets, or model parameters.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real


@dataclass(frozen=True)
class PredictiveSignal:
    """Signals available before observing the current outcome."""

    p_correct: float
    failure_risk: float
    predictive_entropy_nats: float
    normalized_predictive_entropy: float


def signal_from_probability(p_correct: Real) -> PredictiveSignal:
    """Convert one pre-response probability into predictive signals."""

    if isinstance(p_correct, bool) or not isinstance(
        p_correct, Real
    ):
        raise TypeError("p_correct must be a real numeric value")

    p = float(p_correct)

    if not math.isfinite(p):
        raise ValueError("p_correct must be finite")

    if not 0.0 <= p <= 1.0:
        raise ValueError("p_correct must lie within [0, 1]")

    # At the exact boundaries, define 0 * log(0) by continuity.
    if p == 0.0 or p == 1.0:
        entropy = 0.0
    else:
        entropy = -(
            p * math.log(p)
            + (1.0 - p) * math.log1p(-p)
        )

    normalized = entropy / math.log(2.0)

    # Correct only harmless floating-point roundoff.
    normalized = min(1.0, max(0.0, normalized))

    return PredictiveSignal(
        p_correct=p,
        failure_risk=1.0 - p,
        predictive_entropy_nats=entropy,
        normalized_predictive_entropy=normalized,
    )
