"""Exact evaluation in an explicitly invented, one-step environment.

No human outcomes, causal estimates, intervention delivery, sampling,
or finite-horizon recovery claims are involved.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from src.recovery.controller import RecoveryPlan
from src.recovery.hypothetical_selector import (
    ALLOWED_OPTIONS,
    HypotheticalSelection,
)


@dataclass(frozen=True)
class SyntheticWorld:
    """Stipulated probabilities, action effects, and burdens."""

    baseline_success: float
    hint_effect: float
    scaffold_effect: float
    hint_burden: float
    scaffold_burden: float

    def __post_init__(self) -> None:
        names = (
            "baseline_success",
            "hint_effect",
            "scaffold_effect",
            "hint_burden",
            "scaffold_burden",
        )

        for name in names:
            value = getattr(self, name)

            if type(value) not in (int, float):
                raise TypeError(f"{name} must be numeric")

            if not isfinite(value):
                raise ValueError(f"{name} must be finite")

        if not 0.0 <= self.baseline_success <= 1.0:
            raise ValueError("Invalid baseline probability")

        for effect in (self.hint_effect, self.scaffold_effect):
            probability = self.baseline_success + effect

            if not 0.0 <= probability <= 1.0:
                raise ValueError("Invalid synthetic outcome probability")

        for burden in (self.hint_burden, self.scaffold_burden):
            if not 0.0 <= burden <= 1.0:
                raise ValueError("Invalid synthetic burden")

    def effect(self, option: str | None) -> float:
        if option is None:
            return 0.0
        if option == "optional_hint":
            return self.hint_effect
        if option == "optional_scaffold":
            return self.scaffold_effect
        raise ValueError("Unknown synthetic option")

    def burden(self, option: str | None) -> float:
        if option is None:
            return 0.0
        if option == "optional_hint":
            return self.hint_burden
        if option == "optional_scaffold":
            return self.scaffold_burden
        raise ValueError("Unknown synthetic option")

    def net_gain(self, option: str | None) -> float:
        return self.effect(option) - self.burden(option)


@dataclass(frozen=True)
class SyntheticEvaluation:
    """Exact synthetic expectations, not measured outcomes."""

    selected_option: str | None
    expected_probe_success: float
    selected_true_net_gain: float
    oracle_option: str | None
    oracle_true_net_gain: float
    synthetic_regret: float


def evaluate_synthetic(
    plan: RecoveryPlan,
    selection: HypotheticalSelection,
    world: SyntheticWorld,
) -> SyntheticEvaluation:
    """Compare a proposed choice with an available-action oracle."""

    if type(plan) is not RecoveryPlan:
        raise TypeError("Expected RecoveryPlan")

    if type(selection) is not HypotheticalSelection:
        raise TypeError("Expected HypotheticalSelection")

    if type(world) is not SyntheticWorld:
        raise TypeError("Expected SyntheticWorld")

    options = plan.proposed_options

    if type(options) is not tuple:
        raise TypeError("Expected tuple of options")

    if len(options) != len(set(options)):
        raise ValueError("Duplicate options")

    if not set(options).issubset(ALLOWED_OPTIONS):
        raise ValueError("Unknown proposed option")

    if plan.disposition == "proposed":
        if not options:
            raise ValueError("Proposed plan has no options")
    elif options:
        raise ValueError("Non-proposed plan supplies options")

    chosen = selection.selected_option

    if selection.disposition == "selected":
        if chosen not in options:
            raise ValueError("Selection is not an available option")

        assumed_score = selection.assumed_net_score

        if (
            type(assumed_score) not in (int, float)
            or not isfinite(assumed_score)
            or assumed_score <= 0.0
        ):
            raise ValueError("Invalid selected assumed score")

    elif selection.disposition == "abstain":
        if chosen is not None or selection.assumed_net_score is not None:
            raise ValueError("Inconsistent abstention")
    else:
        raise ValueError("Unknown selection disposition")

    selected_gain = world.net_gain(chosen)

    # Abstention is always an available synthetic comparator.
    oracle_option = None
    oracle_gain = 0.0

    # Deterministic tie breaking, as in the hypothetical selector.
    for option in sorted(options):
        gain = world.net_gain(option)

        if gain > oracle_gain:
            oracle_option = option
            oracle_gain = gain

    regret = oracle_gain - selected_gain

    if regret < -1e-12:
        raise AssertionError("Synthetic oracle consistency failure")

    return SyntheticEvaluation(
        selected_option=chosen,
        expected_probe_success=(
            world.baseline_success + world.effect(chosen)
        ),
        selected_true_net_gain=selected_gain,
        oracle_option=oracle_option,
        oracle_true_net_gain=oracle_gain,
        synthetic_regret=max(0.0, regret),
    )
