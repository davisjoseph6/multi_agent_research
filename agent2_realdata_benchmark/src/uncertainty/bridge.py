"""Label-free bridge from frozen predictions to uncertainty signals."""

from __future__ import annotations

from dataclasses import asdict
from numbers import Integral, Real

from src.uncertainty.predictive import signal_from_probability


MODELS = frozenset({"bkt_v1", "neuralcd_v1"})


def signal_record(
    *,
    source_row: Integral,
    student_id: str,
    model: str,
    supported: bool,
    probability: Real | None,
) -> dict:
    """Construct a pre-response record without outcome information."""

    if isinstance(source_row, bool) or not isinstance(
        source_row, Integral
    ):
        raise TypeError("source_row must be an integer")

    if source_row < 0:
        raise ValueError("source_row must be nonnegative")

    if not isinstance(student_id, str) or not student_id.strip():
        raise ValueError("student_id must be a nonempty string")

    if model not in MODELS:
        raise ValueError("Unknown frozen model")

    if not isinstance(supported, bool):
        raise TypeError("supported must be boolean")

    common = {
        "source_row": int(source_row),
        "student_id": student_id,
        "model": model,
    }

    if not supported:
        if model == "bkt_v1":
            raise ValueError("BKT must cover every eligible target")

        if probability is not None:
            raise ValueError(
                "Unsupported items must not have a probability"
            )

        return {
            **common,
            "status": "unsupported_training_item",
            "p_correct": None,
            "failure_risk": None,
            "predictive_entropy_nats": None,
            "normalized_predictive_entropy": None,
        }

    if probability is None:
        raise ValueError(
            "Supported predictions require a probability"
        )

    signal = signal_from_probability(probability)

    return {
        **common,
        "status": "supported",
        **asdict(signal),
    }
