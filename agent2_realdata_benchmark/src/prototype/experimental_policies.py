"""Experimental assistance policy decisions.

Development-only policy module.

Does not randomize participants, administer assistance,
estimate intervention effects, or authorize a human study.

Uses only the committed practice-response history supplied
by the caller. Never uses future responses or probe outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from src.prototype.belief import DemoBeliefTracker


POLICY_MODES = frozenset({
    "control",
    "fixed_summary",
    "adaptive_threshold",
})

DEFAULT_DEMO_THRESHOLD = 0.30


@dataclass(frozen=True)
class PolicyDecision:
    policy_mode: str
    eligible: bool
    offer_summary: bool
    mastery_belief: float | None
    reason: str


def choose_summary_offer(
    *,
    policy_mode: str,
    eligible: bool,
    practice_history: tuple[bool, ...],
    threshold: float = DEFAULT_DEMO_THRESHOLD,
) -> PolicyDecision:
    """Select a summary offer at an upcoming practice boundary.

    practice_history contains only completed practice
    correctness observations for the target concept.

    Eligibility and the input history must be established
    by trusted server-side code.
    """

    if policy_mode not in POLICY_MODES:
        raise ValueError("Unknown experimental policy")

    if type(eligible) is not bool:
        raise TypeError("eligible must be boolean")

    if type(practice_history) is not tuple:
        raise TypeError("practice_history must be a tuple")

    if any(type(value) is not bool for value in practice_history):
        raise TypeError(
            "practice_history must contain only booleans"
        )

    if (
        type(threshold) not in (int, float)
        or not isfinite(threshold)
        or not 0.0 <= threshold <= 1.0
    ):
        raise ValueError("Invalid mastery threshold")

    if not eligible:
        return PolicyDecision(
            policy_mode=policy_mode,
            eligible=False,
            offer_summary=False,
            mastery_belief=None,
            reason="ineligible_boundary",
        )

    if not practice_history:
        raise ValueError(
            "Eligible boundary requires a completed practice"
        )

    tracker = DemoBeliefTracker()

    for correct in practice_history:
        tracker.observe_practice(correct=correct)

    belief = tracker.mastery

    if policy_mode == "control":
        offer = False
        reason = "control_no_additional_summary"

    elif policy_mode == "fixed_summary":
        offer = True
        reason = "fixed_eligible_offer"

    else:
        offer = belief < threshold
        reason = (
            "belief_below_threshold"
            if offer
            else "belief_not_below_threshold"
        )

    return PolicyDecision(
        policy_mode=policy_mode,
        eligible=True,
        offer_summary=offer,
        mastery_belief=belief,
        reason=reason,
    )
