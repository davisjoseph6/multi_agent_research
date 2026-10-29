"""Development-only tests for experimental policy selection."""

import pytest

from src.prototype.experimental_policies import (
    POLICY_MODES,
    DEFAULT_DEMO_THRESHOLD,
    choose_summary_offer,
)


@pytest.mark.parametrize("mode", sorted(POLICY_MODES))
def test_ineligible_boundary_never_offers(mode):
    decision = choose_summary_offer(
        policy_mode=mode,
        eligible=False,
        practice_history=(),
    )

    assert decision.offer_summary is False
    assert decision.mastery_belief is None


@pytest.mark.parametrize("history", [
    (False,),
    (True,),
    (False, True),
])
def test_control_never_offers(history):
    decision = choose_summary_offer(
        policy_mode="control",
        eligible=True,
        practice_history=history,
    )

    assert decision.offer_summary is False
    assert decision.mastery_belief is not None


@pytest.mark.parametrize("history", [
    (False,),
    (True,),
    (False, True),
])
def test_fixed_policy_offers_at_eligible_boundary(history):
    decision = choose_summary_offer(
        policy_mode="fixed_summary",
        eligible=True,
        practice_history=history,
    )

    assert decision.offer_summary is True


def test_adaptive_policy_offers_after_first_error():
    decision = choose_summary_offer(
        policy_mode="adaptive_threshold",
        eligible=True,
        practice_history=(False,),
    )

    assert decision.mastery_belief == pytest.approx(
        0.12903225806451613
    )
    assert decision.offer_summary is True


def test_adaptive_policy_abstains_after_first_correct():
    decision = choose_summary_offer(
        policy_mode="adaptive_threshold",
        eligible=True,
        practice_history=(True,),
    )

    assert decision.mastery_belief == pytest.approx(
        0.5263157894736842
    )
    assert decision.offer_summary is False


def test_threshold_is_explicit():
    assert DEFAULT_DEMO_THRESHOLD == 0.30

    arguments = {
        "policy_mode": "adaptive_threshold",
        "eligible": True,
        "practice_history": (False,),
    }

    low = choose_summary_offer(
        **arguments,
        threshold=0.0,
    )

    high = choose_summary_offer(
        **arguments,
        threshold=1.0,
    )

    assert low.offer_summary is False
    assert high.offer_summary is True


def test_repeated_decision_is_deterministic():
    arguments = {
        "policy_mode": "adaptive_threshold",
        "eligible": True,
        "practice_history": (False, True),
    }

    assert choose_summary_offer(
        **arguments
    ) == choose_summary_offer(**arguments)


def test_unknown_policy_is_rejected():
    with pytest.raises(ValueError):
        choose_summary_offer(
            policy_mode="unknown",
            eligible=True,
            practice_history=(False,),
        )


@pytest.mark.parametrize("history", [
    [False],
    (0,),
    ("incorrect",),
    (None,),
])
def test_invalid_history_is_rejected(history):
    with pytest.raises(TypeError):
        choose_summary_offer(
            policy_mode="control",
            eligible=True,
            practice_history=history,
        )


@pytest.mark.parametrize("threshold", [
    -0.1,
    1.1,
    float("nan"),
    float("inf"),
    True,
])
def test_invalid_threshold_is_rejected(threshold):
    with pytest.raises(ValueError):
        choose_summary_offer(
            policy_mode="adaptive_threshold",
            eligible=True,
            practice_history=(False,),
            threshold=threshold,
        )


def test_eligible_boundary_requires_history():
    with pytest.raises(ValueError):
        choose_summary_offer(
            policy_mode="fixed_summary",
            eligible=True,
            practice_history=(),
        )
