"""Read-only synthetic trial audit regression tests."""

import json
import sqlite3

import pytest

from scripts.step62_simulated_trial_audit import run_audit
from scripts.step63_readonly_audit import audit


def prepared_database(tmp_path):
    path = tmp_path / "step63_synthetic.sqlite3"

    run_audit(
        path,
        completed=6,
        incomplete=6,
    )

    return path


def test_aggregate_integrity(tmp_path):
    path = prepared_database(tmp_path)

    result = audit(path)

    assert result["invariants"] == "passed"
    assert result["causal_evidence"] is False
    assert result["real_participants"] == 0

    assert result["totals"]["assigned"] == 12
    assert result["totals"]["responses"] == 30
    assert result["totals"]["policy_decisions"] == 18

    assert all(
        data["assigned"] == 4
        and data["completed"] == 2
        and data["missing_probe"] == 2
        for data in result["by_arm"].values()
    )


def test_aggregate_has_no_raw_identifiers(tmp_path):
    path = prepared_database(tmp_path)

    result = audit(path)
    output = json.dumps(result)

    assert "participant_id" not in output
    assert "session_id" not in output
    assert "enrollment_request_id" not in output
    assert "choice_id" not in output


def test_detects_policy_tampering(tmp_path):
    path = prepared_database(tmp_path)

    with sqlite3.connect(path) as db:
        db.execute(
            """
            UPDATE experimental_session_policies
            SET policy_mode = 'control'
            WHERE session_id = (
                SELECT session_id
                FROM experimental_session_policies
                WHERE policy_mode = 'fixed_summary'
                LIMIT 1
            )
            """
        )

    with pytest.raises(AssertionError):
        audit(path)


def test_detects_missing_assistance_event(tmp_path):
    path = prepared_database(tmp_path)

    with sqlite3.connect(path) as db:
        db.execute(
            """
            DELETE FROM assistance_events
            WHERE event_id = (
                SELECT MIN(event_id)
                FROM assistance_events
                WHERE event_type = 'offered'
            )
            """
        )

    with pytest.raises(AssertionError):
        audit(path)


def test_nonexistent_database_is_not_created(tmp_path):
    missing = tmp_path / "nonexistent.sqlite3"

    with pytest.raises(FileNotFoundError):
        audit(missing)

    assert not missing.exists()
