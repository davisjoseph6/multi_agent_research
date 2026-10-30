"""Step 79/86: distinguish low mastery, observed decline, and latent forgetting.

Synthetic and statistical audit utilities only. No clinical, educational or
human-participant efficacy claims are authorized by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import comb, isfinite
import random

from .study_v3_pomcp import (
    ACTIONS, CONCEPTS, PRACTICE, GenerativeAssumptions, PlanningState,
)


@dataclass(frozen=True)
class AnchorWindow:
    """Binary responses to version-matched, uniquely identified anchor items.

    Reusing anchors in human studies may cause recall/leakage, and matching
    IDs alone does not establish score validity or stable response difficulty.
    """
    wave: int
    instrument_version: str
    responses: tuple[tuple[str, bool], ...]

    def __post_init__(self) -> None:
        if type(self.wave) is not int or self.wave < 0:
            raise ValueError("wave must be a nonnegative integer")
        if not isinstance(self.instrument_version, str) or not self.instrument_version.strip():
            raise ValueError("instrument_version required")
        if not isinstance(self.responses, tuple) or not self.responses:
            raise ValueError("responses must be a nonempty tuple")
        ids = []
        for entry in self.responses:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise ValueError("responses need (item_id, bool) pairs")
            item_id, correct = entry
            if not isinstance(item_id, str) or not item_id.strip() or type(correct) is not bool:
                raise ValueError("invalid item response")
            ids.append(item_id)
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate anchor item IDs")


@dataclass(frozen=True)
class PairedResponseChange:
    total_items: int
    earlier_correct: int
    later_correct: int
    correct_to_incorrect: int
    incorrect_to_correct: int
    unchanged: int
    one_sided_exact_p: Fraction
    alpha: Fraction
    observed_decline_signal: bool
    latent_forgetting_proven: bool = False
    synthetic_or_exploratory_only: bool = True


def paired_response_change(
    earlier: AnchorWindow,
    later: AnchorWindow,
    *,
    alpha: Fraction = Fraction(1, 20),
) -> PairedResponseChange:
    """One-sided exact paired sign/McNemar alert for correct->incorrect excess.

    Under the null, discordance directions must be exchangeable, conditional
    on the total number of discordant paired anchors. The result is NOT an
    identification of latent cognitive forgetting or a validated clinical test.
    """
    if type(alpha) is not Fraction or not 0 < alpha < 1:
        raise ValueError("alpha must be a Fraction strictly between 0 and 1")
    if later.wave <= earlier.wave:
        raise ValueError("later wave must follow earlier wave")
    if earlier.instrument_version != later.instrument_version:
        raise ValueError("instrument versions differ")
    old = dict(earlier.responses)
    new = dict(later.responses)
    if old.keys() != new.keys():
        raise ValueError("anchor item identifiers differ")
    loss = sum(old[i] and not new[i] for i in old)
    gain = sum(not old[i] and new[i] for i in old)
    discordant = loss + gain
    p_value = (
        Fraction(sum(comb(discordant, k) for k in range(loss, discordant + 1)), 2 ** discordant)
        if discordant else Fraction(1)
    )
    return PairedResponseChange(
        total_items=len(old),
        earlier_correct=sum(old.values()),
        later_correct=sum(new.values()),
        correct_to_incorrect=loss,
        incorrect_to_correct=gain,
        unchanged=len(old) - discordant,
        one_sided_exact_p=p_value,
        alpha=alpha,
        observed_decline_signal=bool(discordant and loss > gain and p_value <= alpha),
    )


@dataclass(frozen=True)
class NonstationaryAssumptions:
    """An explicitly hypothetical forgetting process for falsification tests."""
    forgetting_probability: float = 0.0

    def __post_init__(self) -> None:
        value = self.forgetting_probability
        if type(value) not in (float, int) or not isfinite(value) or not 0 <= value <= 1:
            raise ValueError("invalid hypothetical forgetting probability")


def nonstationary_transition(
    state: PlanningState,
    action: tuple[str, str],
    rng: random.Random,
    *,
    learning: GenerativeAssumptions | None = None,
    nonstationarity: NonstationaryAssumptions | None = None,
) -> PlanningState:
    """Stress-test transition, NOT a drop-in replacement for V3's POMCP model.

    All mastered concepts may be forgotten on a step; then the targeted concept
    may be learned. No observation or educational-validity claim is made.
    """
    if not isinstance(state, PlanningState):
        raise TypeError("state must be PlanningState")
    if not isinstance(rng, random.Random):
        raise TypeError("rng must be random.Random")
    if not isinstance(action, tuple) or len(action) != 2:
        raise ValueError("action must be (kind, concept)")
    kind, concept = action
    if kind not in ACTIONS or concept not in CONCEPTS:
        raise ValueError("unknown action or concept")
    if kind != PRACTICE and state.resources_left == 0:
        raise ValueError("resource action without remaining resources")
    learning = learning or GenerativeAssumptions()
    nonstationarity = nonstationarity or NonstationaryAssumptions()
    f = nonstationarity.forgetting_probability
    next_mastery = [old and not (rng.random() < f) for old in state.mastered]
    target = CONCEPTS.index(concept)
    if not next_mastery[target] and rng.random() < learning.rate(kind):
        next_mastery[target] = True
    return PlanningState(
        tuple(next_mastery), state.resources_left - int(kind != PRACTICE),
    )
