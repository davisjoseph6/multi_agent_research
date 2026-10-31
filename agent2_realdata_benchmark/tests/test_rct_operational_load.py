"""Checks for strictly local rehearsal load and report invariants."""
import pytest
from scripts.rct_operational_load import exercise


def test_three_concurrent_fictional_journeys_complete():
    result=exercise(participants=3,workers=3)
    assert result["completed"]==3
    assert result["audit_pending_actions"]==0
    assert result["actual_network_tls_devices_tested"] is False
    assert result["real_people"] is False
    assert result["requests"]>result["actions"]
    # The first three places of a randomized block of six or nine need not
    # include all three treatment arms. Test only valid arms and total count.
    assert set(result["assigned_arm_counts"]).issubset({"A","B","C"})
    assert sum(result["assigned_arm_counts"].values()) == 3


@pytest.mark.parametrize("people,workers",[(0,3),(121,3),(3,0),(3,25),(True,2)])
def test_load_bounds(people,workers):
    with pytest.raises(ValueError):
        exercise(participants=people,workers=workers)
