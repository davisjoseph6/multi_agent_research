"""Atomic fixed-summary assistance gate regression tests."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from src.prototype.assistance_store import AssistanceConflict
from src.prototype.gated_assistance_store import (
    SQLiteFixedSummaryQuizRepository,
)
from src.prototype.item_bank import (
    BANK_VERSION,
    DEMO_ITEMS,
    INSTRUCTIONAL_DEMO_ITEMS,
    INSTRUCTIONAL_DEMO_VERSION,
)
from src.prototype.sqlite_store import (
    ResponseConflict,
    SQLiteQuizRepository,
)


@pytest.fixture
def store(tmp_path):
    return SQLiteFixedSummaryQuizRepository(
        tmp_path / "gated.sqlite3",
        items=INSTRUCTIONAL_DEMO_ITEMS,
        bank_version=INSTRUCTIONAL_DEMO_VERSION,
    )


def answer(store, sid, position, request=None):
    item = store._items[position]

    return store.submit(
        session_id=sid,
        item_id=item.item_id,
        choice_id="A",
        request_id=request or f"response-{position}",
    )


def begin(store):
    sid = store.create_session()
    result = answer(store, sid, 0)
    assert result.replayed is False
    return sid


def test_first_answer_atomically_creates_offer(store):
    sid = begin(store)

    assert store.read_progress(sid).position == 1
    assert len(store.read_responses(sid)) == 1

    offer = store.current_offer(sid)

    assert offer is not None
    assert offer.status == "offered"
    assert offer.source_position == 0
    assert offer.target_position == 1
    assert offer.body is None

    assert store.read_events(
        session_id=sid,
        source_position=0,
    ) == ("proposed", "offered")


def test_offered_resource_blocks_next_answer(store):
    sid = begin(store)

    with pytest.raises(ResponseConflict, match="pending"):
        answer(store, sid, 1)

    assert store.read_progress(sid).position == 1
    assert len(store.read_responses(sid)) == 1


def test_accepted_resource_still_blocks_progress(store):
    sid = begin(store)

    accepted = store.decide(
        session_id=sid,
        source_position=0,
        accept=True,
    )

    assert accepted.status == "accepted"
    assert accepted.body is None

    with pytest.raises(ResponseConflict, match="pending"):
        answer(store, sid, 1)


def test_explicit_delivery_unlocks_next_question(store):
    sid = begin(store)

    store.decide(
        session_id=sid,
        source_position=0,
        accept=True,
    )

    delivered = store.deliver(
        session_id=sid,
        source_position=0,
    )

    assert delivered.status == "delivered"
    assert delivered.body is not None

    second = answer(store, sid, 1)

    assert second.replayed is False
    assert store.read_progress(sid).position == 2

    # Question 2 is followed by another practice item,
    # so the fixed policy creates another offer.
    next_offer = store.current_offer(sid)

    assert next_offer is not None
    assert next_offer.source_position == 1
    assert next_offer.status == "offered"


def test_decline_unlocks_progression(store):
    sid = begin(store)

    declined = store.decide(
        session_id=sid,
        source_position=0,
        accept=False,
    )

    assert declined.status == "declined"
    assert declined.body is None

    second = answer(store, sid, 1)

    assert second.replayed is False
    assert store.read_progress(sid).position == 2


def test_retry_does_not_create_duplicate_offer(store):
    sid = begin(store)

    replay = answer(store, sid, 0)

    assert replay.replayed is True
    assert store.read_progress(sid).position == 1
    assert len(store.read_responses(sid)) == 1

    assert store.read_events(
        session_id=sid,
        source_position=0,
    ) == ("proposed", "offered")


def test_restart_preserves_pending_gate(store):
    sid = begin(store)

    reopened = SQLiteFixedSummaryQuizRepository(
        store._path,
        items=INSTRUCTIONAL_DEMO_ITEMS,
        bank_version=INSTRUCTIONAL_DEMO_VERSION,
    )

    assert reopened.current_offer(sid).status == "offered"

    with pytest.raises(ResponseConflict):
        answer(reopened, sid, 1)

    reopened.decide(
        session_id=sid,
        source_position=0,
        accept=False,
    )

    assert answer(reopened, sid, 1).replayed is False


def test_offer_insert_failure_rolls_back_practice(
    store,
):
    sid = store.create_session()

    with sqlite3.connect(store._path) as connection:
        connection.execute(
            """
            CREATE TRIGGER inject_offer_failure
            BEFORE INSERT ON assistance_offers
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'injected offer creation failure'
                );
            END;
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        answer(store, sid, 0)

    assert store.read_progress(sid).position == 0
    assert store.read_responses(sid) == ()
    assert store.current_offer(sid) is None


def test_offer_event_failure_rolls_back_everything(store):
    sid = store.create_session()

    with sqlite3.connect(store._path) as connection:
        connection.execute(
            """
            CREATE TRIGGER inject_event_failure
            BEFORE INSERT ON assistance_events
            WHEN NEW.event_type = 'offered'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'injected event creation failure'
                );
            END;
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        answer(store, sid, 0)

    assert store.read_progress(sid).position == 0
    assert store.read_responses(sid) == ()
    assert store.current_offer(sid) is None

    assert store.read_events(
        session_id=sid,
        source_position=0,
    ) == ()


def test_parallel_attempts_cannot_skip_pending_offer(store):
    sid = begin(store)

    def attempt(number):
        try:
            return answer(
                store,
                sid,
                1,
                request=f"concurrent-{number}",
            )
        except ResponseConflict as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, (1, 2)))

    assert all(
        isinstance(result, ResponseConflict)
        for result in results
    )

    assert store.read_progress(sid).position == 1
    assert len(store.read_responses(sid)) == 1


def test_probe_boundary_never_gets_offer(store):
    sid = begin(store)

    for source, next_position in (
        (0, 1),
        (1, 2),
    ):
        store.decide(
            session_id=sid,
            source_position=source,
            accept=False,
        )

        answer(store, sid, next_position)

    assert store.read_progress(sid).position == 3

    # The upcoming fourth item is an independent probe.
    assert store.current_offer(sid) is None

    assert answer(store, sid, 3).completed is True


def test_other_concept_does_not_receive_summary(tmp_path):
    other = replace(
        DEMO_ITEMS[0],
        item_id="other_concept_practice",
        concept_id="anchoring",
        prompt="Different concept fixture",
    )

    items = (
        DEMO_ITEMS[0],
        other,
        DEMO_ITEMS[1],
    )

    store = SQLiteFixedSummaryQuizRepository(
        tmp_path / "other_concept.sqlite3",
        items=items,
        bank_version="mixed_concept_fixture_v1",
    )

    sid = store.create_session()

    answer(store, sid, 0)

    assert store.current_offer(sid) is None

    answer(store, sid, 1)

    assert store.read_progress(sid).position == 2


def test_original_repository_remains_ungated(tmp_path):
    original = SQLiteQuizRepository(
        tmp_path / "ungated.sqlite3",
        items=DEMO_ITEMS,
        bank_version=BANK_VERSION,
    )

    sid = original.create_session()

    assert answer(original, sid, 0).replayed is False
    assert answer(original, sid, 1).completed is True


def test_delivery_cannot_precede_acceptance(store):
    sid = begin(store)

    with pytest.raises(AssistanceConflict):
        store.deliver(
            session_id=sid,
            source_position=0,
        )
