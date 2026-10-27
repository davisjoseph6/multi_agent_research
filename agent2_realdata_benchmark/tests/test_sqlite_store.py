"""Transactional and restart-recovery tests for local SQLite."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from src.prototype.belief import DemoBeliefTracker
from src.prototype.item_bank import BANK_VERSION, DEMO_ITEMS
from src.prototype.sqlite_store import (
    ItemBankMismatch,
    ResponseConflict,
    SessionNotFound,
    SQLiteQuizRepository,
)


@pytest.fixture
def database(tmp_path):
    return tmp_path / "prototype.sqlite3"


@pytest.fixture
def store(database):
    return SQLiteQuizRepository(
        database,
        items=DEMO_ITEMS,
        bank_version=BANK_VERSION,
    )


def submit(
    store,
    session_id,
    *,
    item="demo_main_1",
    choice="B",
    request="request-1",
):
    return store.submit(
        session_id=session_id,
        item_id=item,
        choice_id=choice,
        request_id=request,
    )


def test_creates_session_and_excludes_answer_key(store):
    sid = store.create_session()
    progress = store.read_progress(sid)

    assert progress.position == 0
    assert progress.completed is False
    assert progress.bank_version == BANK_VERSION
    assert progress.current_question["id"] == "demo_main_1"
    assert "correct_id" not in progress.current_question
    assert store.read_responses(sid) == ()


def test_accepted_response_advances_to_probe(store):
    sid = store.create_session()
    result = submit(store, sid)

    assert result.record.correct is True
    assert result.replayed is False
    assert result.completed is False

    progress = store.read_progress(sid)

    assert progress.position == 1
    assert progress.current_question["kind"] == "independent_probe"


def test_exact_retry_does_not_duplicate_record(store):
    sid = store.create_session()

    first = submit(store, sid)
    replay = submit(store, sid)

    assert first.replayed is False
    assert replay.replayed is True
    assert replay.record == first.record
    assert store.read_progress(sid).position == 1
    assert len(store.read_responses(sid)) == 1


def test_changed_payload_with_same_request_is_rejected(store):
    sid = store.create_session()
    submit(store, sid)

    with pytest.raises(ResponseConflict):
        submit(store, sid, choice="A")

    assert len(store.read_responses(sid)) == 1


def test_new_request_cannot_answer_previous_item(store):
    sid = store.create_session()
    submit(store, sid)

    with pytest.raises(ResponseConflict):
        submit(store, sid, request="request-2")

    assert store.read_progress(sid).position == 1


def test_invalid_choice_does_not_advance(store):
    sid = store.create_session()

    with pytest.raises(ValueError, match="Invalid answer"):
        submit(store, sid, choice="Z")

    assert store.read_progress(sid).position == 0
    assert store.read_responses(sid) == ()


def test_out_of_order_question_is_rejected(store):
    sid = store.create_session()

    with pytest.raises(ResponseConflict):
        submit(
            store,
            sid,
            item="demo_probe_1",
            choice="A",
        )

    assert store.read_progress(sid).position == 0


def test_restart_preserves_session_and_response(database):
    first = SQLiteQuizRepository(
        database,
        items=DEMO_ITEMS,
        bank_version=BANK_VERSION,
    )

    sid = first.create_session()
    submit(first, sid)

    reopened = SQLiteQuizRepository(
        database,
        items=DEMO_ITEMS,
        bank_version=BANK_VERSION,
    )

    progress = reopened.read_progress(sid)

    assert progress.position == 1
    assert progress.current_question["id"] == "demo_probe_1"
    assert len(reopened.read_responses(sid)) == 1

    final = submit(
        reopened,
        sid,
        item="demo_probe_1",
        choice="A",
        request="request-2",
    )

    assert final.completed is True
    assert reopened.read_progress(sid).current_question is None


def test_sessions_are_independent(store):
    first = store.create_session()
    second = store.create_session()

    submit(store, first)

    assert first != second
    assert store.read_progress(first).position == 1
    assert store.read_progress(second).position == 0


def test_changed_question_bank_is_rejected(database):
    first = SQLiteQuizRepository(
        database,
        items=DEMO_ITEMS,
        bank_version=BANK_VERSION,
    )

    sid = first.create_session()

    changed = replace(
        DEMO_ITEMS[0],
        prompt="Changed question that must not silently replace old content",
    )

    reopened = SQLiteQuizRepository(
        database,
        items=(changed, DEMO_ITEMS[1]),
        bank_version=BANK_VERSION,
    )

    with pytest.raises(ItemBankMismatch):
        reopened.read_progress(sid)


def test_unknown_session_is_rejected(store):
    with pytest.raises(SessionNotFound):
        store.read_progress("unknown")


def test_idempotency_identifier_is_required(store):
    sid = store.create_session()

    for invalid in ("", "   ", None, 12):
        with pytest.raises(ValueError, match="request identifier"):
            submit(store, sid, request=invalid)

    assert store.read_progress(sid).position == 0


def test_parallel_duplicate_request_is_recorded_once(store):
    sid = store.create_session()

    def attempt(_):
        return submit(store, sid)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))

    assert sorted(result.replayed for result in results) == [
        False,
        True,
    ]

    assert store.read_progress(sid).position == 1
    assert len(store.read_responses(sid)) == 1


def test_database_insert_failure_rolls_back_position(
    store,
    database,
):
    sid = store.create_session()

    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_insert
            BEFORE INSERT ON responses
            BEGIN
                SELECT RAISE(ABORT, 'injected failure');
            END;
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        submit(store, sid)

    assert store.read_progress(sid).position == 0
    assert store.read_responses(sid) == ()


def test_saved_practice_can_rebuild_bkt_without_probe_update(
    store,
):
    sid = store.create_session()

    submit(store, sid)
    submit(
        store,
        sid,
        item="demo_probe_1",
        choice="A",
        request="request-2",
    )

    tracker = DemoBeliefTracker()

    for response in store.read_responses(sid):
        if response.kind == "practice":
            tracker.observe_practice(
                correct=response.correct
            )

    # Only one correct practice answer is used.
    assert tracker.mastery == pytest.approx(
        0.5263157894736842
    )


def test_late_replay_preserves_original_completion_result(store):
    """Old retries must not adopt the session's current status."""

    sid = store.create_session()

    first = submit(
        store,
        sid,
        item="demo_main_1",
        choice="B",
        request="practice-request",
    )

    final = submit(
        store,
        sid,
        item="demo_probe_1",
        choice="A",
        request="probe-request",
    )

    assert first.completed is False
    assert final.completed is True

    # Repeat the first request after the entire quiz ended.
    replay_first = submit(
        store,
        sid,
        item="demo_main_1",
        choice="B",
        request="practice-request",
    )

    replay_final = submit(
        store,
        sid,
        item="demo_probe_1",
        choice="A",
        request="probe-request",
    )

    assert replay_first.replayed is True
    assert replay_first.record == first.record
    assert replay_first.completed is False

    assert replay_final.replayed is True
    assert replay_final.record == final.record
    assert replay_final.completed is True

    assert store.read_progress(sid).position == 2
    assert len(store.read_responses(sid)) == 2


def test_position_update_failure_rolls_back_insert(
    store,
    database,
):
    """Failure in the second write rolls back the first write."""

    sid = store.create_session()

    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_position_update
            BEFORE UPDATE OF position ON sessions
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'injected position update failure'
                );
            END;
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        submit(
            store,
            sid,
            item="demo_main_1",
            choice="B",
            request="failed-update",
        )

    assert store.read_progress(sid).position == 0
    assert store.read_responses(sid) == ()


def test_concurrent_distinct_requests_accept_only_one(store):
    """Two logical submissions cannot consume one position twice."""

    from src.prototype.sqlite_store import SubmissionReceipt

    sid = store.create_session()

    def attempt(request_id):
        try:
            return submit(
                store,
                sid,
                item="demo_main_1",
                choice="B",
                request=request_id,
            )
        except ResponseConflict as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                attempt,
                ("concurrent-one", "concurrent-two"),
            )
        )

    accepted = [
        result
        for result in results
        if isinstance(result, SubmissionReceipt)
    ]

    rejected = [
        result
        for result in results
        if isinstance(result, ResponseConflict)
    ]

    assert len(accepted) == 1
    assert len(rejected) == 1
    assert accepted[0].replayed is False

    assert store.read_progress(sid).position == 1
    assert len(store.read_responses(sid)) == 1
