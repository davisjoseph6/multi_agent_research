"""Local-only assistance state-machine and persistence tests."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from src.prototype.assistance import DEMO_SUMMARY
from src.prototype.assistance_store import (
    AssistanceConflict,
    SQLiteAssistanceRepository,
)
from src.prototype.item_bank import (
    INSTRUCTIONAL_DEMO_ITEMS,
    INSTRUCTIONAL_DEMO_VERSION,
)


@pytest.fixture
def store(tmp_path):
    return SQLiteAssistanceRepository(
        tmp_path / "offers.sqlite3",
        items=INSTRUCTIONAL_DEMO_ITEMS,
        bank_version=INSTRUCTIONAL_DEMO_VERSION,
    )


def answer(store, sid, position, choice="A"):
    item = INSTRUCTIONAL_DEMO_ITEMS[position]
    return store.submit(
        session_id=sid,
        item_id=item.item_id,
        choice_id=choice,
        request_id=f"answer-{position}",
    )


def ready(store):
    sid = store.create_session()
    answer(store, sid, 0)
    return sid


def test_resource_content_is_explicit():
    assert DEMO_SUMMARY.concept_id == "loss_aversion"
    assert DEMO_SUMMARY.resource_type == "concept_summary"
    assert DEMO_SUMMARY.body


def test_offer_requires_committed_practice(store):
    sid = store.create_session()

    with pytest.raises(AssistanceConflict):
        store.offer_after_practice(
            session_id=sid, source_position=0
        )


def test_eligible_offer_hides_content(store):
    sid = ready(store)

    offer = store.offer_after_practice(
        session_id=sid, source_position=0
    )

    assert offer.status == "offered"
    assert offer.target_position == 1
    assert offer.body is None
    assert store.read_events(
        session_id=sid, source_position=0
    ) == ("proposed", "offered")


def test_offer_creation_is_idempotent(store):
    sid = ready(store)

    first = store.offer_after_practice(
        session_id=sid, source_position=0
    )
    retry = store.offer_after_practice(
        session_id=sid, source_position=0
    )

    assert first == retry
    assert len(store.read_events(
        session_id=sid, source_position=0
    )) == 2


def test_acceptance_records_separate_delivery_event(store):
    sid = ready(store)
    store.offer_after_practice(
        session_id=sid, source_position=0
    )

    accepted = store.decide(
        session_id=sid, source_position=0, accept=True
    )

    assert accepted.status == "accepted"
    assert accepted.body is None
    assert store.read_events(
        session_id=sid, source_position=0
    ) == ("proposed", "offered", "accepted")

    delivered = store.deliver(
        session_id=sid, source_position=0
    )

    assert delivered.status == "delivered"
    assert delivered.body == DEMO_SUMMARY.body
    assert store.read_events(
        session_id=sid, source_position=0
    ) == (
        "proposed", "offered", "accepted", "delivered"
    )


def test_decline_never_reveals_resource_body(store):
    sid = ready(store)
    store.offer_after_practice(
        session_id=sid, source_position=0
    )

    result = store.decide(
        session_id=sid, source_position=0, accept=False
    )

    assert result.status == "declined"
    assert result.body is None
    assert store.read_events(
        session_id=sid, source_position=0
    ) == ("proposed", "offered", "declined")


def test_repeated_decision_is_idempotent(store):
    sid = ready(store)
    store.offer_after_practice(
        session_id=sid, source_position=0
    )

    first = store.decide(
        session_id=sid, source_position=0, accept=True
    )
    retry = store.decide(
        session_id=sid, source_position=0, accept=True
    )

    assert first == retry
    assert len(store.read_events(
        session_id=sid, source_position=0
    )) == 3


def test_conflicting_final_decision_is_rejected(store):
    sid = ready(store)
    store.offer_after_practice(
        session_id=sid, source_position=0
    )
    store.decide(
        session_id=sid, source_position=0, accept=False
    )

    with pytest.raises(AssistanceConflict):
        store.decide(
            session_id=sid, source_position=0, accept=True
        )


def test_probe_boundary_cannot_receive_offer(store):
    sid = ready(store)

    answer(store, sid, 1)
    answer(store, sid, 2)

    with pytest.raises(AssistanceConflict):
        store.offer_after_practice(
            session_id=sid, source_position=2
        )


def test_stale_undecided_offer_is_not_deliverable(store):
    sid = ready(store)
    store.offer_after_practice(
        session_id=sid, source_position=0
    )

    # The current API does not gate the next question yet.
    answer(store, sid, 1)

    with pytest.raises(AssistanceConflict):
        store.decide(
            session_id=sid, source_position=0, accept=True
        )


def test_concurrent_opposing_decisions_have_one_winner(store):
    sid = ready(store)
    store.offer_after_practice(
        session_id=sid, source_position=0
    )

    def attempt(value):
        try:
            return store.decide(
                session_id=sid,
                source_position=0,
                accept=value,
            )
        except AssistanceConflict as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (True, False)))

    assert sum(
        not isinstance(result, Exception)
        for result in results
    ) == 1

    events = store.read_events(
        session_id=sid, source_position=0
    )

    assert ("accepted" in events) != ("declined" in events)
    assert "delivered" not in events


def test_delivery_before_acceptance_is_rejected(store):
    sid = ready(store)

    store.offer_after_practice(
        session_id=sid, source_position=0
    )

    with pytest.raises(AssistanceConflict):
        store.deliver(
            session_id=sid, source_position=0
        )

    assert store.read_events(
        session_id=sid, source_position=0
    ) == ("proposed", "offered")


def test_declined_resource_cannot_be_delivered(store):
    sid = ready(store)

    store.offer_after_practice(
        session_id=sid, source_position=0
    )

    store.decide(
        session_id=sid, source_position=0, accept=False
    )

    with pytest.raises(AssistanceConflict):
        store.deliver(
            session_id=sid, source_position=0
        )

    assert "delivered" not in store.read_events(
        session_id=sid, source_position=0
    )


def test_delivery_and_acceptance_retries_are_idempotent(store):
    sid = ready(store)

    store.offer_after_practice(
        session_id=sid, source_position=0
    )

    store.decide(
        session_id=sid, source_position=0, accept=True
    )

    first = store.deliver(
        session_id=sid, source_position=0
    )

    second = store.deliver(
        session_id=sid, source_position=0
    )

    acceptance_retry = store.decide(
        session_id=sid, source_position=0, accept=True
    )

    assert first == second
    assert acceptance_retry == first
    assert first.status == "delivered"
    assert first.body == DEMO_SUMMARY.body

    assert store.read_events(
        session_id=sid, source_position=0
    ) == (
        "proposed", "offered", "accepted", "delivered"
    )


def test_accepted_but_stale_resource_cannot_be_delivered(store):
    sid = ready(store)

    store.offer_after_practice(
        session_id=sid, source_position=0
    )

    accepted = store.decide(
        session_id=sid, source_position=0, accept=True
    )

    assert accepted.status == "accepted"

    # The present standalone repository still permits
    # advancing the quiz before resource delivery.
    answer(store, sid, 1)

    with pytest.raises(AssistanceConflict):
        store.deliver(
            session_id=sid, source_position=0
        )

    assert "delivered" not in store.read_events(
        session_id=sid, source_position=0
    )
