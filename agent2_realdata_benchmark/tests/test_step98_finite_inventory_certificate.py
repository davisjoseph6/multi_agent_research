"""Tests of finite question inventory and rate-uncertainty scope."""
from fractions import Fraction
import pytest

from src.prototype.step98_finite_inventory_certificate import (
    PracticeInventory, demo_bank_snapshots, feasible_coverage_mixture,
    hypothetical_rate_bounds, never_learned_floor, robust_statewise_certificate,
)
from src.prototype.study_v3_pomcp import CONCEPTS, PRACTICE


COUNTS = (7, 7, 7, 7, 7, 7, 7, 6)
P, F = hypothetical_rate_bounds()


def evaluate(inventory, exploration=1):
    first = inventory.legal_actions()[0]
    weights = feasible_coverage_mixture(inventory, primary=first,
                                        exploration=exploration)
    return robust_statewise_certificate(
        inventory, weights, learning_lower=P, forgetting_upper=F)


def test_initial_inventory_hypothetically_supports_every_concept():
    inv = PracticeInventory(COUNTS, 2)
    result = evaluate(inv)
    assert sum(inv.remaining) == 55
    assert result["strict_uniform_negative_one_step_drift"] is True
    assert Fraction(result["uniform_drift_margin"]) == Fraction(1, 1280)


def test_one_concept_exhaustion_ends_uniform_certificate_even_with_resources():
    inv = PracticeInventory(COUNTS[:-1] + (0,), 2)
    result = evaluate(inv)
    assert "Nudge Theory" in result["infeasible_target_concepts"]
    assert result["strict_uniform_negative_one_step_drift"] is False
    assert Fraction(result["worst_expected_deficit_change"]) == 0
    assert all(concept != "Nudge Theory" for _, concept in inv.legal_actions())


def test_no_questions_remain_even_with_resources():
    inv = PracticeInventory((0,) * 8, 2)
    assert inv.legal_actions() == ()
    with pytest.raises(ValueError, match="not feasible"):
        feasible_coverage_mixture(inv, primary=(PRACTICE, CONCEPTS[0]),
                                  exploration=1)


def test_warmup_excludes_recovery_resources():
    inv = PracticeInventory(COUNTS, 2, forced_warmup=True)
    assert all(action == PRACTICE for action, _ in inv.legal_actions())


def test_zero_resource_budget_excludes_resources():
    inv = PracticeInventory(COUNTS, 0)
    assert len(inv.legal_actions()) == 8


def test_exploration_zero_does_not_certify():
    result = evaluate(PracticeInventory(COUNTS, 2), exploration=0)
    assert result["strict_uniform_negative_one_step_drift"] is False


def test_robust_forgetting_invalidates_coverage():
    bounds = {concept: "0.001" for concept in CONCEPTS}
    inv = PracticeInventory(COUNTS, 2)
    weights = feasible_coverage_mixture(inv, primary=(PRACTICE, CONCEPTS[0]),
                                        exploration=1)
    result = robust_statewise_certificate(
        inv, weights, learning_lower=P, forgetting_upper=bounds)
    assert result["strict_uniform_negative_one_step_drift"] is False
    assert Fraction(result["worst_expected_deficit_change"]) == Fraction(3, 32000)


def test_lower_success_probability_zero_invalidates_some_coverage():
    learning = dict(P)
    learning[PRACTICE] = 0
    inv = PracticeInventory(COUNTS, 0)
    weights = feasible_coverage_mixture(inv, primary=(PRACTICE, CONCEPTS[0]),
                                        exploration=1)
    result = robust_statewise_certificate(
        inv, weights, learning_lower=learning, forgetting_upper=F)
    assert not result["strict_uniform_negative_one_step_drift"]


def test_resource_opportunity_failure_floor_is_not_zero():
    floor = never_learned_floor(
        practice_opportunities=6, resource_opportunities=6,
        practice_success_upper="0.05", resource_success_upper="0.14")
    assert floor == Fraction(19, 20)**6 * Fraction(43, 50)**6
    assert 0 < floor < 1


def test_invalid_remaining_and_distributions_fail_closed():
    with pytest.raises(ValueError):
        PracticeInventory((-1,) + COUNTS[1:], 2)
    inv = PracticeInventory(COUNTS, 2)
    with pytest.raises(ValueError, match="Invalid action"):
        robust_statewise_certificate(
            inv, {("NOT_AN_ACTION", CONCEPTS[0]): 1},
            learning_lower=P, forgetting_upper=F)


def test_original_draft_bank_exact_counts_and_exhaustion():
    from pathlib import Path
    bank = Path(__file__).resolve().parents[1] / "docs/rct_candidate_v1/items.csv"
    report = demo_bank_snapshots(bank)
    assert report["original_bank_counts"]["Nudge Theory"] == 6
    assert report["initial_inventory"]["strict_uniform_negative_one_step_drift"]
    assert not report["nudge_practice_exhausted"]["strict_uniform_negative_one_step_drift"]
    assert report["all_practice_exhausted"]["status"] == "NO_PRACTICE_ACTION_REMAINS"
    assert report["rct_candidate_draft_content_reviewed"] is False
