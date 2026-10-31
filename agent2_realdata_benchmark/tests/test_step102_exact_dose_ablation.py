"""Step102 matched-question-dose checks, all fictional development only."""
import pytest

from scripts.step102_exact_dose_ablation import (
    NO_RESOURCE_POLICIES, SCENARIOS, SEED_START,
    episode, experiment, parity_check, policy_action,
)
from src.prototype.step99_inventory_aware_pomcp import InventoryProgress
from src.prototype.study_v3_pomcp import CONCEPTS, PRACTICE


def test_independent_environment_matches_frozen_step100_reference():
    result = parity_check(simulations=41)
    assert result["frozen_step100_environment_parity"] is True
    assert result["number_of_parity_cases"] == 4


def test_new_policies_only_offer_questions_with_equal_dose():
    for policy in NO_RESOURCE_POLICIES:
        result = episode(policy, "nominal", SEED_START, simulations=41)
        assert result["practice_answers"] == 55
        assert result["resource_actions"] == 0
        assert result["total_actions"] == 55
        assert result["nominal_action_cost"] == .055
        assert result["resources_by_kind"] == {}


def test_both_new_policies_have_identical_first_question_warmup():
    belief = {c: .2 if c == CONCEPTS[2] else .9 for c in CONCEPTS}
    p = InventoryProgress()
    actions = [policy_action(name, belief, p, sim_count=41, seed=SEED_START,
                             scenario="nominal", step=0)
               for name in NO_RESOURCE_POLICIES]
    assert actions == [(PRACTICE, CONCEPTS[2])] * 2


def test_selected_concept_is_feasible_and_assistance_is_prohibited():
    p = InventoryProgress().after((PRACTICE, CONCEPTS[1]))
    belief = {c: .2 for c in CONCEPTS}
    for name in NO_RESOURCE_POLICIES:
        selected = policy_action(name, belief, p, sim_count=41,
                                 seed=SEED_START, scenario="nominal", step=1)
        assert selected[0] == PRACTICE
        assert selected in p.legal()


def test_new_policy_episode_reproducibility():
    a = episode("step99_practice_only", "half_learning", SEED_START + 2,
                simulations=41)
    b = episode("step99_practice_only", "half_learning", SEED_START + 2,
                simulations=41)
    assert a == b


def test_quick_report_preserves_all_scenarios_and_dose():
    report = experiment(quick=True)
    assert report["human_participants"] is False
    assert report["sealed_heldout_accessed"] is False
    assert report["preexisting_step100_development_seeds_reused"] is True
    assert len(report["episodes"]) == len(SCENARIOS) * len(NO_RESOURCE_POLICIES) * 2
    for scenario in SCENARIOS:
        contrast = report["primary_paired_contrasts"][scenario]
        assert contrast["paired_development_seeds"] == 2
        assert sum(contrast["wins_ties_losses"]) == 2
        assert all(report["policy_means"][scenario][policy]["mean_resources"] == 0
                   for policy in NO_RESOURCE_POLICIES)


@pytest.mark.parametrize("invalid_seed", [-1, 149999, 200000, 200001, True])
def test_heldout_or_invalid_seeds_rejected(invalid_seed):
    with pytest.raises(ValueError, match="development learner"):
        episode("step99_practice_only", "nominal", invalid_seed,
                simulations=41)


def test_unknown_policy_and_scenario_rejected():
    with pytest.raises(ValueError):
        episode("unknown", "nominal", SEED_START, simulations=41)
    with pytest.raises(ValueError):
        episode("v3_practice_only", "unknown", SEED_START, simulations=41)
