"""Fail-closed Step100 regression tests (development-only synthetic learners)."""
import pytest

from scripts.step100_inventory_policy_comparison import (
    SCENARIOS, POLICIES, SEED_START, HELDOUT_START,
    episode, experiment, paired_contrast, policy_action,
)
from src.prototype.step99_inventory_aware_pomcp import InventoryProgress
from src.prototype.study_v3_pomcp import CONCEPTS, PRACTICE


def test_common_first_practice_warmup_for_planners():
    p = InventoryProgress()
    belief = {c: .2 if i == 1 else .8 for i, c in enumerate(CONCEPTS)}
    for policy in POLICIES:
        action = policy_action(policy, belief, p,
                               sim_count=48, seed=SEED_START,
                               scenario="nominal", step=0)
        assert action[0] == PRACTICE
        assert action in p.legal()
    assert policy_action("v3", belief, p, sim_count=48,
                         seed=SEED_START, scenario="nominal", step=0)[1] == CONCEPTS[1]


def test_all_policies_account_for_55_questions_and_resource_caps():
    for policy in POLICIES:
        row = episode(policy, "nominal", SEED_START, simulations=41)
        assert row["practice_answers"] == 55
        assert row["total_actions"] == 55 + row["resource_actions"]
        assert 0 <= row["resource_actions"] <= 6
        assert 0 <= row["posttest_correct_of_16"] <= 16
        if policy.endswith("_no_resource"):
            assert row["resource_actions"] == 0


def test_repeated_paired_episode_is_exactly_reproducible():
    left = episode("step99", "forgetting_shift", SEED_START + 2,
                   simulations=41)
    right = episode("step99", "forgetting_shift", SEED_START + 2,
                    simulations=41)
    assert left == right


def test_quick_experiment_has_all_prespecified_cases():
    report = experiment(quick=True)
    assert report["quick_smoke_only"] is True
    assert report["human_participants"] is False
    assert report["heldout_data_accessed"] is False
    assert len(report["episodes"]) == len(SCENARIOS) * len(POLICIES) * 2
    for scenario in SCENARIOS:
        contrast = report["contrasts"][scenario]["primary_step99_vs_v3"]
        assert contrast["paired_development_seeds"] == 2
        assert sum(contrast["wins_ties_losses"]) == 2
        assert len(contrast["descriptive_seed_bootstrap_95pct"]) == 2


@pytest.mark.parametrize("invalid_seed", [-1, SEED_START - 1, HELDOUT_START, True])
def test_reserved_or_invalid_seeds_are_rejected(invalid_seed):
    with pytest.raises(ValueError, match="development learner"):
        episode("step99", "nominal", invalid_seed, simulations=41)


def test_missing_pair_rejected():
    first = episode("greedy_no_resource", "nominal", SEED_START,
                    simulations=41)
    with pytest.raises(ValueError, match="Missing paired"):
        paired_contrast([first], "step99", "v3", "nominal")


def test_unknown_scenario_or_policy_rejected():
    with pytest.raises(ValueError):
        episode("step99", "NOT_A_SCENARIO", SEED_START)
    with pytest.raises(ValueError):
        episode("NOT_A_POLICY", "nominal", SEED_START)
