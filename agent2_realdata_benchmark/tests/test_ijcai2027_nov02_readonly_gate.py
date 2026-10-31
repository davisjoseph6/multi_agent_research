"""Regression tests for the read-only November 2 evidence gate."""
from copy import deepcopy

import pytest

from scripts.ijcai2027_nov02_readonly_gate import build_packet


@pytest.fixture
def evidence():
    names = ("stationary_nominal", "slow_forgetting", "rapid_forgetting",
             "noisy_slow_forgetting", "weak_learning")
    means = (0.01, 0.02, -0.01, 0.003, -0.02)
    scenarios = {name: {"paired_v6_minus": {"no_recovery": {
        "mean": mean, "descriptive_interval": [mean - .01, mean + .01]}}}
                 for name, mean in zip(names, means)}
    preflight = {"candidate_sha256": "a" * 64, "mechanical_gate_passed": False,
                 "blockers": ["external reviews missing"]}
    smoke = {"software_rehearsal_passed": True,
             "human_enrollment_authorized": False,
             "fictional_completed": 9,
             "arm_counts": {"A": 3, "B": 3, "C": 3},
             "audit": {"mode": "rehearsal", "candidate_sha256": "a" * 64}}
    v6 = {"human_participants": False, "no_heldout_access": True,
          "scenarios": scenarios, "decision": {
              "total_development_scenarios": 5,
              "screening_only_no_confirmatory_claim": True,
              "real_student_intervention_effect_established": False,
              "independent_algorithmic_novelty_established": False,
              "development_scenarios_with_positive_mean_recovery_contrast": 3,
              "conservative_predeclared_screening_pass": False}}
    witness = {"synthetic_only": True,
               "strict_positive_uniform_drift_disproved_for_this_configuration": True,
               "expected_one_step_deficit_change": "0"}
    return preflight, smoke, v6, witness


def test_negative_result_preserved(evidence):
    packet = build_packet(*evidence)
    assert packet["v6"]["broad_recovery_claim_screen"] == "NO_GO"
    assert packet["release"]["human_enrollment_authorized"] is False
    assert packet["v3"]["universal_statewise_negative_drift_claim"] == "NOT_SUPPORTED"


def test_mismatched_candidate_rejected(evidence):
    p, s, v, w = deepcopy(evidence)
    s["audit"]["candidate_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="different candidate"):
        build_packet(p, s, v, w)


def test_fake_screening_pass_rejected(evidence):
    p, s, v, w = deepcopy(evidence)
    v["decision"]["conservative_predeclared_screening_pass"] = True
    with pytest.raises(ValueError, match="criterion"):
        build_packet(p, s, v, w)


def test_missing_scenario_rejected(evidence):
    p, s, v, w = deepcopy(evidence)
    v["scenarios"].pop("weak_learning")
    with pytest.raises(ValueError, match="scenario"):
        build_packet(p, s, v, w)


def test_false_approval_rejected(evidence):
    p, s, v, w = deepcopy(evidence)
    p["mechanical_gate_passed"] = True
    with pytest.raises(ValueError, match="unreleased"):
        build_packet(p, s, v, w)


def test_absent_drift_counterexample_rejected(evidence):
    p, s, v, w = deepcopy(evidence)
    w["expected_one_step_deficit_change"] = "-1/100"
    with pytest.raises(ValueError, match="counterexample"):
        build_packet(p, s, v, w)
