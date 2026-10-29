"""Smaller synthetic rehearsal checks; no participant data."""

import json

import pytest

from scripts.step62_simulated_trial_audit import run_audit


def test_rehearsal_balanced_with_missing_outcomes(tmp_path):
    output = run_audit(
        tmp_path / "fresh.sqlite3",
        completed=6,
        incomplete=6,
    )
    assert output["invariants"] == "passed"
    assert output["real_participants"] == 0
    assert output["causal_evidence"] is False
    assert output["completed_sessions"] == 6
    assert output["deliberately_incomplete_sessions"] == 6
    assert output["responses"] == 30
    assert output["policy_decisions"] == 18
    assert output["restart_recoveries_checked"] == 2
    assert all(
        row == {"assigned": 4, "completed": 2, "missing_probe": 2}
        for row in output["by_arm"].values()
    )
    assert output["offers"] == output["assistance_events"]["proposed"]


def test_rehearsal_refuses_reused_database(tmp_path):
    path = tmp_path / "already-there.sqlite3"
    path.write_bytes(b"not an existing trial database")
    with pytest.raises(FileExistsError):
        run_audit(path, completed=6, incomplete=6)


@pytest.mark.parametrize("counts", [
    (0, 6), (5, 6), (6, 0), (6, 5), (7, 6),
])
def test_rehearsal_rejects_incomplete_blocks(tmp_path, counts):
    with pytest.raises(ValueError):
        run_audit(tmp_path / "bad.sqlite3", completed=counts[0], incomplete=counts[1])
