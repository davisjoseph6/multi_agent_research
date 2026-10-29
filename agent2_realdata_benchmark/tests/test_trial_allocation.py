"""Tests for isolated development-only trial allocation."""

from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import sqlite3

import pytest

from src.prototype.trial_allocation import (
    SQLiteTrialAllocationStore,
    TrialConfigurationMismatch,
)


def test_single_assignment_and_idempotency(tmp_path):
    database = tmp_path / "a.sqlite3"
    store = SQLiteTrialAllocationStore(database)

    first = store.allocate(
        enrollment_request_id="synthetic-request-01"
    )

    second = store.allocate(
        enrollment_request_id="synthetic-request-01"
    )

    assert first.participant_id == second.participant_id
    assert first.policy_mode == second.policy_mode

    assert not first.replayed
    assert second.replayed

    restored = store.read_assignment(
        participant_id=first.participant_id
    )

    assert restored.policy_mode == first.policy_mode


def test_restart_and_config_stamp(tmp_path):
    database = tmp_path / "b.sqlite3"

    original = SQLiteTrialAllocationStore(
        database,
        block_sizes=(6,),
    )

    assignment = original.allocate(
        enrollment_request_id="one"
    )

    restarted = SQLiteTrialAllocationStore(
        database,
        block_sizes=(6,),
    )

    assert (
        restarted.allocate(
            enrollment_request_id="one"
        ).participant_id
        == assignment.participant_id
    )

    with pytest.raises(TrialConfigurationMismatch):
        SQLiteTrialAllocationStore(
            database,
            block_sizes=(9,),
        )


def test_balanced_complete_blocks(tmp_path):
    store = SQLiteTrialAllocationStore(
        tmp_path / "c.sqlite3",
        block_sizes=(6,),
    )

    assignments = [
        store.allocate(
            enrollment_request_id=f"demo-{i}"
        )
        for i in range(24)
    ]

    for start in range(0, 24, 6):

        counts = Counter(
            item.policy_mode
            for item in assignments[start:start + 6]
        )

        assert sorted(counts.values()) == [2, 2, 2]

    assert len({
        item.participant_id
        for item in assignments
    }) == 24


def test_concurrent_assignments_are_unique(tmp_path):
    store = SQLiteTrialAllocationStore(
        tmp_path / "d.sqlite3",
        block_sizes=(6,),
    )

    with ThreadPoolExecutor(max_workers=8) as pool:

        assignments = list(
            pool.map(
                lambda i: store.allocate(
                    enrollment_request_id=f"seed-{i}"
                ),
                range(30),
            )
        )

    assert len({
        item.participant_id
        for item in assignments
    }) == 30

    counts = Counter(
        item.policy_mode
        for item in assignments
    )

    assert sorted(counts.values()) == [10, 10, 10]


def test_invalid_request_ids(tmp_path):
    store = SQLiteTrialAllocationStore(
        tmp_path / "e.sqlite3"
    )

    for invalid in (
        "",
        None,
        False,
        "   ",
        "z" * 129,
    ):
        with pytest.raises(ValueError):
            store.allocate(
                enrollment_request_id=invalid
            )


def test_existing_quiz_tables_not_created(tmp_path):
    database = tmp_path / "f.sqlite3"

    SQLiteTrialAllocationStore(database)

    with sqlite3.connect(database) as connection:

        names = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                """
            )
        }

    assert "sessions" not in names
    assert "responses" not in names


def test_invalid_configuration_rejected(tmp_path):
    with pytest.raises(ValueError):
        SQLiteTrialAllocationStore(
            tmp_path / "g.sqlite3",
            arms=("control", "control"),
        )

    with pytest.raises(ValueError):
        SQLiteTrialAllocationStore(
            tmp_path / "h.sqlite3",
            block_sizes=(4,),
        )
