"""Exact finite-state drift certificates.

Certificates concern the supplied mathematical model,
not real learners or the deployed POMCP controller.
"""

from dataclasses import dataclass
from fractions import Fraction


def rational(value):
    if type(value) not in (int, Fraction):
        raise ValueError(
            "Use int or Fraction, never float or bool"
        )
    return Fraction(value)


@dataclass(frozen=True)
class FiniteDriftModel:
    potentials: tuple[Fraction, ...]
    transitions: tuple[tuple[Fraction, ...], ...]

    def __post_init__(self):
        if (
            not isinstance(self.potentials, tuple)
            or not self.potentials
        ):
            raise ValueError("Potentials must be a nonempty tuple")

        v = tuple(rational(x) for x in self.potentials)

        if any(x < 0 for x in v) or not any(x == 0 for x in v):
            raise ValueError(
                "Need nonnegative potentials and a zero target"
            )

        if (
            not isinstance(self.transitions, tuple)
            or len(self.transitions) != len(v)
        ):
            raise ValueError("Transition matrix dimensions mismatch")

        rows = []

        for i, row in enumerate(self.transitions):
            if not isinstance(row, tuple) or len(row) != len(v):
                raise ValueError("Transition row dimensions mismatch")

            p = tuple(rational(x) for x in row)

            if any(x < 0 for x in p) or sum(p) != 1:
                raise ValueError(
                    "Transition rows must be probability distributions"
                )

            if v[i] == 0 and any(
                p[j] > 0 and v[j] > 0
                for j in range(len(v))
            ):
                raise ValueError(
                    "Target set must be absorbing"
                )

            rows.append(p)

        object.__setattr__(self, "potentials", v)
        object.__setattr__(self, "transitions", tuple(rows))

    def uniform_drift_margin(self):
        margins = [
            value - sum(
                probability * successor
                for probability, successor in zip(
                    self.transitions[i],
                    self.potentials,
                )
            )
            for i, value in enumerate(self.potentials)
            if value > 0
        ]

        if not margins or min(margins) <= 0:
            raise ValueError(
                "No strictly positive uniform drift margin"
            )

        return min(margins)

    def capped_statistics(self, initial_state, cap):
        if (
            type(initial_state) is not int
            or not 0 <= initial_state < len(self.potentials)
        ):
            raise ValueError("Invalid initial state")

        if type(cap) is not int or cap < 1:
            raise ValueError("Cap must be a positive integer")

        delta = self.uniform_drift_margin()
        n = len(self.potentials)

        distribution = [
            Fraction(i == initial_state)
            for i in range(n)
        ]

        expected_attempts = Fraction(0)

        for _ in range(cap):
            expected_attempts += sum(
                distribution[i]
                for i in range(n)
                if self.potentials[i] > 0
            )

            distribution = [
                sum(
                    distribution[i] * self.transitions[i][j]
                    for i in range(n)
                )
                for j in range(n)
            ]

        failure = sum(
            distribution[i]
            for i in range(n)
            if self.potentials[i] > 0
        )

        residual = sum(
            distribution[i] * self.potentials[i]
            for i in range(n)
        )

        initial = self.potentials[initial_state]
        expected_upper = initial / delta

        failure_upper = min(
            Fraction(1),
            initial / (delta * cap),
        )

        if (
            expected_attempts > expected_upper
            or failure > failure_upper
        ):
            raise RuntimeError(
                "Drift certificate inconsistency"
            )

        return {
            "uniform_drift_margin": delta,
            "expected_attempts": expected_attempts,
            "probability_not_recovered_by_cap": failure,
            "expected_residual": residual,
            "expected_attempts_upper_bound": expected_upper,
            "failure_probability_upper_bound": failure_upper,
        }
