"""Synthetic-only tests for hypothetical recovery selection."""

from dataclasses import FrozenInstanceError, replace

import pytest

from src.recovery.controller import RecoveryContext, plan_recovery
from src.recovery.hypothetical_selector import (
    HypotheticalScore,
    select_hypothetical,
)
from src.uncertainty.bridge import signal_record
from src.uncertainty.event_detector import TriggerConfig, detect_event


def make_plan(
    *,
    probability=0.1,
    supported=True,
    permission=True,
    hint=True,
    scaffold=True,
):
    """Create a genuine plan through the existing controller."""

    signal = signal_record(
        source_row=12,
        student_id="synthetic-student",
        model="neuralcd_v1",
        supported=supported,
        probability=probability if supported else None,
    )

    decision = detect_event(
        signal,
        TriggerConfig(
            policy="risk_only",
            risk_threshold=0.7,
            entropy_threshold=0.8,
        ),
    )

    return plan_recovery(
        decision,
        context=RecoveryContext(
            permission_to_offer=permission,
            hint_available=hint,
            scaffold_available=scaffold,
        ),
    )


def score(benefit, burden):
    return HypotheticalScore(
        assumed_benefit=benefit,
        assumed_burden=burden,
    )


def test_selects_highest_positive_assumed_utility():
    plan = make_plan()

    result = select_hypothetical(
        plan,
        scores={
            "optional_hint": score(0.8, 0.1),
            "optional_scaffold": score(0.9, 0.4),
        },
    )

    assert result.disposition == "selected"
    assert result.selected_option == "optional_hint"
    assert result.assumed_net_score == pytest.approx(0.7)
    assert result.reason == "highest_positive_assumed_utility"

    # Selection must not mutate the upstream proposal.
    assert plan.proposed_options == (
        "optional_hint",
        "optional_scaffold",
    )


def test_respects_available_options():
    plan = make_plan(scaffold=False)

    result = select_hypothetical(
        plan,
        scores={"optional_hint": score(0.4, 0.1)},
    )

    assert result.selected_option == "optional_hint"
    assert plan.proposed_options == ("optional_hint",)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"probability": 0.9},
        {"supported": False},
        {"permission": False},
        {"hint": False, "scaffold": False},
    ],
)
def test_upstream_non_proposal_causes_abstention(kwargs):
    plan = make_plan(**kwargs)

    result = select_hypothetical(plan, scores={})

    assert plan.disposition != "proposed"
    assert result.disposition == "abstain"
    assert result.selected_option is None
    assert result.assumed_net_score is None
    assert result.reason == "upstream_plan_not_proposed"


def test_zero_or_negative_utility_causes_abstention():
    result = select_hypothetical(
        make_plan(),
        scores={
            "optional_hint": score(0.25, 0.25),
            "optional_scaffold": score(0.1, 0.5),
        },
    )

    assert result.disposition == "abstain"
    assert result.selected_option is None
    assert result.reason == "no_positive_assumed_utility"


def test_equal_positive_utilities_have_deterministic_tie():
    plan = make_plan()

    scores = {
        "optional_scaffold": score(0.75, 0.5),
        "optional_hint": score(0.5, 0.25),
    }

    first = select_hypothetical(plan, scores=scores)
    second = select_hypothetical(plan, scores=scores)

    assert first == second
    assert first.selected_option == "optional_hint"
    assert first.assumed_net_score == 0.25


@pytest.mark.parametrize(
    "scores",
    [
        {},
        {"optional_hint": score(0.5, 0.1)},
        {
            "optional_hint": score(0.5, 0.1),
            "optional_scaffold": score(0.6, 0.2),
            "unavailable_action": score(0.9, 0.0),
        },
    ],
)
def test_rejects_missing_or_extra_scores(scores):
    with pytest.raises(ValueError, match="match proposed options"):
        select_hypothetical(make_plan(), scores=scores)


@pytest.mark.parametrize(
    "benefit,burden,error",
    [
        (True, 0.1, TypeError),
        (0.5, False, TypeError),
        (float("nan"), 0.1, ValueError),
        (float("inf"), 0.1, ValueError),
        (0.5, float("-inf"), ValueError),
        (1.1, 0.1, ValueError),
        (-1.1, 0.1, ValueError),
        (0.5, -0.1, ValueError),
        (0.5, 1.1, ValueError),
    ],
)
def test_rejects_invalid_hypothetical_scores(
    benefit, burden, error
):
    with pytest.raises(error):
        score(benefit, burden)


def test_rejects_incorrect_score_value_type():
    with pytest.raises(TypeError, match="HypotheticalScore"):
        select_hypothetical(
            make_plan(),
            scores={
                "optional_hint": 0.5,
                "optional_scaffold": score(0.6, 0.2),
            },
        )


def test_rejects_scores_on_non_proposed_plan():
    with pytest.raises(ValueError, match="Non-proposed"):
        select_hypothetical(
            make_plan(permission=False),
            scores={"optional_hint": score(0.5, 0.1)},
        )


@pytest.mark.parametrize(
    "options",
    [
        ("optional_hint", "optional_hint"),
        ("optional_hint", "unknown_action"),
    ],
)
def test_rejects_invalid_proposed_options(options):
    altered_plan = replace(
        make_plan(),
        proposed_options=options,
    )

    with pytest.raises(ValueError):
        select_hypothetical(
            altered_plan,
            scores={},
        )


def test_rejects_non_plan_input():
    with pytest.raises(TypeError, match="RecoveryPlan"):
        select_hypothetical(
            {"disposition": "proposed"},
            scores={},
        )


def test_results_and_scores_are_immutable():
    result = select_hypothetical(
        make_plan(scaffold=False),
        scores={"optional_hint": score(0.5, 0.1)},
    )

    with pytest.raises(FrozenInstanceError):
        result.disposition = "delivered"

    assumptions = score(0.5, 0.1)

    with pytest.raises(FrozenInstanceError):
        assumptions.assumed_benefit = 1.0
