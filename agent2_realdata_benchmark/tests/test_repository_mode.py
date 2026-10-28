"""Verify durable isolation of SQLite policy modes."""

import sqlite3

import pytest

from src.prototype.gated_assistance_store import (
    SQLiteFixedSummaryQuizRepository,
)
from src.prototype.item_bank import (
    INSTRUCTIONAL_DEMO_ITEMS,
    INSTRUCTIONAL_DEMO_VERSION,
)
from src.prototype.sqlite_store import (
    RepositoryModeMismatch,
    SQLiteQuizRepository,
)


def plain(path):
    return SQLiteQuizRepository(
        path,
        items=INSTRUCTIONAL_DEMO_ITEMS,
        bank_version=INSTRUCTIONAL_DEMO_VERSION,
    )


def gated(path):
    return SQLiteFixedSummaryQuizRepository(
        path,
        items=INSTRUCTIONAL_DEMO_ITEMS,
        bank_version=INSTRUCTIONAL_DEMO_VERSION,
    )


def test_gated_database_rejects_plain_repository(tmp_path):
    path = tmp_path / "gated.sqlite3"

    original = gated(path)
    session_id = original.create_session()

    with pytest.raises(RepositoryModeMismatch):
        plain(path)

    assert gated(path).read_progress(session_id).position == 0


def test_plain_database_rejects_gated_repository(tmp_path):
    path = tmp_path / "plain.sqlite3"

    original = plain(path)
    session_id = original.create_session()

    with pytest.raises(RepositoryModeMismatch):
        gated(path)

    assert plain(path).read_progress(session_id).position == 0


def test_legacy_unassisted_database_can_be_reopened(tmp_path):
    path = tmp_path / "legacy.sqlite3"

    original = plain(path)
    session_id = original.create_session()

    # Simulate an old database with sessions but without
    # the newly introduced repository-mode manifest.
    with sqlite3.connect(path) as connection:
        connection.execute(
            "DROP TABLE repository_config"
        )

    reopened = plain(path)

    assert reopened.read_progress(session_id).position == 0

    with pytest.raises(RepositoryModeMismatch):
        gated(path)


def test_gated_mode_survives_restart(tmp_path):
    path = tmp_path / "restart.sqlite3"

    first = gated(path)
    session_id = first.create_session()

    item = INSTRUCTIONAL_DEMO_ITEMS[0]

    first.submit(
        session_id=session_id,
        item_id=item.item_id,
        choice_id="A",
        request_id="mode-test-response",
    )

    reopened = gated(path)

    assert reopened.current_offer(session_id).status == "offered"

    with pytest.raises(RepositoryModeMismatch):
        plain(path)


def test_missing_manifest_cannot_downgrade_gated_session(
    tmp_path,
):
    path = tmp_path / "missing_manifest.sqlite3"

    original = gated(path)
    original.create_session()

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            DELETE FROM repository_config
            WHERE key = 'repository_mode'
            """
        )

    with pytest.raises(RepositoryModeMismatch):
        plain(path)

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            """
            SELECT value FROM repository_config
            WHERE key = 'repository_mode'
            """
        ).fetchone()

    assert row is None


def test_missing_stamp_recovers_from_valid_manifest(tmp_path):
    path = tmp_path / "stamp_recovery.sqlite3"

    original = plain(path)
    sid = original.create_session()

    with sqlite3.connect(path) as connection:
        connection.execute(
            "DROP TABLE repository_mode_stamp"
        )

    reopened = plain(path)

    assert reopened.read_progress(sid).position == 0

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            """
            SELECT value FROM repository_mode_stamp
            WHERE singleton = 1
            """
        ).fetchone()

    assert row[0] == "unassisted"


def test_ambiguous_assistance_history_fails_closed(tmp_path):
    path = tmp_path / "ambiguous.sqlite3"

    original = gated(path)
    sid = original.create_session()

    original.submit(
        session_id=sid,
        item_id=INSTRUCTIONAL_DEMO_ITEMS[0].item_id,
        choice_id="A",
        request_id="first-answer",
    )

    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE repository_config")
        connection.execute("DROP TABLE repository_mode_stamp")

    with pytest.raises(RepositoryModeMismatch):
        plain(path)
