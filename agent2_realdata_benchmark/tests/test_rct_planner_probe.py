"""Shadow policy probe must distinguish exploration from selected action."""
import pytest

from scripts.rct_planner_probe import PROFILES, probe
from src.prototype.study_v2 import RECOVERY_ACTIONS


def test_shadow_probe_does_not_change_any_rct_record():
    report = probe(seeds=2, simulations=41)
    assert not report["model_changes"]
    assert not report["participant_database_accessed"]
    for name in PROFILES:
        values = report["profiles"][name]
        assert values["socratic_offered_in_action_set"] == 2
        assert 0 <= values["socratic_explored_at_root"] <= 2
        assert 0 <= values["socratic_choices"] <= 2
        assert sum(values["choices"].values()) == 2
        assert set(RECOVERY_ACTIONS).issubset(values["choices"])


@pytest.mark.parametrize("seeds,simulations", [(0,240), (101,240), (1,40), (1,2001), (True,240)])
def test_shadow_probe_input_bounds(seeds,simulations):
    with pytest.raises(ValueError):
        probe(seeds=seeds,simulations=simulations)
