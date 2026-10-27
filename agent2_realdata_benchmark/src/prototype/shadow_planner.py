"""Synthetic shadow-mode recovery planning for the local quiz.

Produces internal diagnostics only. Does not offer or deliver
assistance, change actual BKT state, or use student outcomes
to estimate intervention effects.

The detector assesses a hypothetical NEXT practice opportunity,
not the independent probe in the current two-item demo.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.planning.exact_solver import available_actions_from_plan
from src.planning.pomcp import solve_pomcp
from src.planning.pomdp import (
    ToyPOMDPParameters,
    ToySingleSkillPOMDP,
)
from src.prototype.belief import DemoBeliefTracker
from src.recovery.controller import RecoveryContext, plan_recovery
from src.uncertainty.bridge import signal_record
from src.uncertainty.event_detector import (
    TriggerConfig,
    detect_event,
)


@dataclass(frozen=True)
class ShadowRecoveryDiagnostic:
    """Internal synthetic research diagnostic; never an actual offer."""

    source_row: int
    mastery_belief: float
    predicted_correctness: float
    detector_status: str
    recovery_disposition: str
    allowed_actions: tuple[str, ...]
    simulated_action: str
    simulated_expected_return: float
    simulations: int
    mode: str = "hypothetical_shadow_only"


def _illustrative_model() -> ToySingleSkillPOMDP:
    """Construct an explicitly uncalibrated toy transition model."""

    return ToySingleSkillPOMDP(
        ToyPOMDPParameters(
            baseline_learning=0.1,
            hint_increment=0.5,
            scaffold_increment=0.7,
            hint_uptake=0.8,
            scaffold_uptake=0.5,
            slip=0.1,
            guess=0.2,
            hint_cost=0.04,
            scaffold_cost=0.12,
        )
    )


def propose_shadow_recovery(
    tracker: DemoBeliefTracker,
    *,
    source_row: int,
    session_id: str,
    simulated_permission_to_offer: bool = False,
    hint_available: bool = True,
    scaffold_available: bool = True,
    simulations: int = 300,
    seed: int = 2027,
) -> ShadowRecoveryDiagnostic:
    """Plan hypothetically after an already observed practice answer.

    The supplied BKT belief is not changed. A simulated permission
    flag is NOT institutional approval or participant consent.
    """

    if not isinstance(tracker, DemoBeliefTracker):
        raise TypeError("Expected DemoBeliefTracker")

    current_mastery = tracker.mastery

    # The detector expects next-response correctness probability,
    # not latent mastery probability.
    predicted_correctness = tracker.predict_practice()

    signal = signal_record(
        source_row=source_row,
        student_id=session_id,
        model="bkt_v1",
        supported=True,
        probability=predicted_correctness,
    )

    # Illustrative threshold; not fitted to pilot-domain data.
    decision = detect_event(
        signal,
        TriggerConfig(
            policy="risk_only",
            risk_threshold=0.65,
            entropy_threshold=0.8,
        ),
    )

    context = RecoveryContext(
        permission_to_offer=simulated_permission_to_offer,
        hint_available=hint_available,
        scaffold_available=scaffold_available,
    )

    proposal = plan_recovery(
        decision,
        context=context,
    )

    allowed = available_actions_from_plan(proposal)

    # The model simulates future learning only.
    # No future transition is applied to the live BKT tracker.
    result = solve_pomcp(
        _illustrative_model(),
        belief=current_mastery,
        horizon=2,
        simulations=simulations,
        seed=seed,
        allowed_actions=allowed,
    )

    return ShadowRecoveryDiagnostic(
        source_row=source_row,
        mastery_belief=current_mastery,
        predicted_correctness=predicted_correctness,
        detector_status=decision.status,
        recovery_disposition=proposal.disposition,
        allowed_actions=allowed,
        simulated_action=result.first_action,
        simulated_expected_return=result.estimated_return,
        simulations=result.simulations,
    )
