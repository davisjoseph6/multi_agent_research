"""Fail-closed reproducibility and ablation checks, development-only."""
import pytest
from scripts import step95_nonstationary_heldout as base
from scripts.step95_v6_development import v6_episode
from scripts.step95_v6_mechanism_audit import audited_episode, verify_parity, audit


@pytest.mark.parametrize("scenario", tuple(base.SCENARIOS))
def test_independent_simulation_matches_v6(scenario):
    for seed in (100000, 100001, 100002):
        verify_parity(scenario, seed, audited_episode(scenario, seed))


def test_no_recovery_ablation_really_never_uses_resource():
    for seed in (100000, 100001, 100002):
        x = audited_episode("slow_forgetting", seed, allow_recovery=False)
        assert x["resource_actions"] == 0
        assert x["signal_triggered_resources"] == 0
        assert x["steps"] == 55


def test_ground_truth_event_counts_partition_triggers():
    x = audited_episode("slow_forgetting", 100002)
    assert x["signal_triggered_resources"] == (x["mastered_at_signal_resource"] + x["unmastered_at_signal_resource"])
    assert x["unmastered_at_signal_resource"] == (x["forgotten_and_unmastered_at_trigger"] + x["unmastered_without_recorded_forgetting_at_trigger"])


def test_stationary_model_has_no_true_forgetting():
    for seed in range(100000, 100010):
        x = audited_episode("stationary_nominal", seed)
        assert x["latent_forgetting_events"] == 0
        assert x["forgotten_and_unmastered_at_trigger"] == 0


def test_audit_uses_only_development_seeds():
    x = audit("slow_forgetting", 3, lengths=(2, 2))
    assert x["manifest"]["seed_start"] == base.DEV_START
    assert x["manifest"]["seed_end"] == base.DEV_START + 2
    assert x["manifest"]["no_heldout_seeds_accessed"] is True
    assert set(x["paired_v6_minus"]) == {"fixed", "greedy", "no_recovery", "no_risk_credit", "no_coverage_weight"}
    assert x["human_evidence"] is False


def test_parity_verifier_fails_closed_on_drift():
    x = audited_episode("slow_forgetting", 100000)
    altered = dict(x)
    altered["resource_actions"] += 1
    with pytest.raises(AssertionError, match="parity failure"):
        verify_parity("slow_forgetting", 100000, altered)


@pytest.mark.parametrize("invalid", (99999, 200000, 200001, "100000"))
def test_heldout_or_invalid_seeds_forbidden(invalid):
    with pytest.raises(ValueError):
        audited_episode("slow_forgetting", invalid)


def test_invalid_count_rejected():
    with pytest.raises(ValueError):
        audit("slow_forgetting", 0)


def test_no_exposure_of_hidden_latent_to_controller():
    # The episode diagnostics may inspect latent state; controller's choose()
    # signature still accepts beliefs and budget only.
    from inspect import signature
    from src.prototype.step95_v6_decline_candidate import ObservationChangeController
    assert list(signature(ObservationChangeController.choose).parameters) == ["self", "belief", "resources_left"]
