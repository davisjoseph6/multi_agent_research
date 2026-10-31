"""Step 101 verification tests with an entirely fabricated report fixture.

No external data, no heldout seeds, no full simulator runs.
"""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from statistics import mean

import pytest

from scripts.step100_inventory_policy_comparison import (
    FULL_COUNT, HORIZON, POLICIES, SCENARIOS, SEED_START, SIMULATIONS,
    paired_contrast,
)
from scripts.step101_step100_evidence_audit import (
    CONTRASTS, MEAN_FIELDS, SOURCES, markdown, verify,
)


@pytest.fixture(scope="module")
def synthetic_full_report():
    rows = []
    for scenario in SCENARIOS:
        for seed in range(SEED_START, SEED_START + FULL_COUNT):
            for policy in POLICIES:
                resources = 2 if policy in ("step99", "v3") else 0
                correct = (8 + seed % 3 + int(policy == "step99")
                           - int(scenario == "half_learning"))
                rows.append({
                    "scenario": scenario, "seed": seed, "policy": policy,
                    "synthetic_only": True, "practice_answers": 55,
                    "resource_actions": resources,
                    "resources_by_kind": {"WORKED_EXAMPLE": resources}
                                         if resources else {},
                    "total_actions": 55 + resources,
                    "nominal_action_cost": .08 if resources else .055,
                    "posttest_correct_of_16": correct,
                    "posttest_accuracy": correct / 16,
                    "final_latent_mastery_fraction": .5,
                })
    return {
        "status": "EXPLORATORY_DEVELOPMENT_ONLY; NO_STUDENT_EFFICACY",
        "quick_smoke_only": False,
        "human_participants": False,
        "heldout_data_accessed": False,
        "can_establish_ai_novelty": False,
        "original_ijcai_rct_unchanged": True,
        "manifest": {
            "study": "step100_paired_finite_inventory_dev_v1",
            "seeds": list(range(SEED_START, SEED_START + FULL_COUNT)),
            "policies": list(POLICIES),
            "scenarios": list(SCENARIOS),
            "planner_simulations": SIMULATIONS, "horizon": HORIZON,
            "practice_session_quotas": [20, 20, 15],
            "resource_slots_per_session": 2,
        },
        "source_sha256": {
            s: sha256(Path(s).read_bytes()).hexdigest() for s in SOURCES
        },
        "episodes": rows,
        "policy_means": {
            scenario: {
                policy: {
                    out: mean(row[source] for row in rows
                              if row["scenario"] == scenario
                              and row["policy"] == policy)
                    for out, source in MEAN_FIELDS.items()
                } for policy in POLICIES
            } for scenario in SCENARIOS
        },
        "contrasts": {
            scenario: {
                name: paired_contrast(rows, *pair, scenario)
                for name, pair in CONTRASTS.items()
            } for scenario in SCENARIOS
        },
    }


def test_consistent_480_row_development_report_is_verifiable(synthetic_full_report):
    result = verify(synthetic_full_report)
    assert result["verified_episode_count"] == 480
    assert result["source_fingerprints_verified"] is True
    assert result["human_learning_effect_established"] is False
    assert result["algorithmic_novelty_established"] is False
    assert result["broad_step99_superiority_established"] is False
    assert "Step 99" in markdown(result)


def test_single_score_tamper_detected(synthetic_full_report):
    report = deepcopy(synthetic_full_report)
    report["episodes"][0]["posttest_correct_of_16"] += 1
    with pytest.raises(ValueError, match="posttest"):
        verify(report)


def test_missing_seed_detected(synthetic_full_report):
    report = deepcopy(synthetic_full_report)
    report["episodes"].pop()
    with pytest.raises(ValueError, match="episode count"):
        verify(report)


def test_duplicate_policy_seed_detected(synthetic_full_report):
    report = deepcopy(synthetic_full_report)
    report["episodes"][-1] = deepcopy(report["episodes"][0])
    with pytest.raises(ValueError, match="duplicated"):
        verify(report)


def test_tampered_primary_mean_detected(synthetic_full_report):
    report = deepcopy(synthetic_full_report)
    report["contrasts"]["nominal"]["primary_step99_vs_v3"][
        "mean_posttest_accuracy_difference"] = 1.0
    with pytest.raises(ValueError, match="contrast mean"):
        verify(report)


def test_tampered_descriptive_interval_detected(synthetic_full_report):
    report = deepcopy(synthetic_full_report)
    report["contrasts"]["nominal"]["primary_step99_vs_v3"][
        "descriptive_seed_bootstrap_95pct"][0] = -1.0
    with pytest.raises(ValueError, match="bootstrap"):
        verify(report)


def test_tampered_source_file_hash_detected(synthetic_full_report):
    report = deepcopy(synthetic_full_report)
    report["source_sha256"][SOURCES[0]] = "0" * 64
    with pytest.raises(ValueError, match="Source changed"):
        verify(report)


def test_quick_report_refused_even_if_other_data_unchanged(synthetic_full_report):
    report = deepcopy(synthetic_full_report)
    report["quick_smoke_only"] = True
    with pytest.raises(ValueError, match="FULL synthetic"):
        verify(report)


def test_no_resource_baseline_with_resource_is_rejected(synthetic_full_report):
    report = deepcopy(synthetic_full_report)
    for row in report["episodes"]:
        if row["policy"] == "greedy_no_resource":
            row["resource_actions"] = 1
            row["resources_by_kind"] = {"SOCRATIC_HINT": 1}
            row["total_actions"] = 56
            break
    with pytest.raises(ValueError, match="No-resource"):
        verify(report)
