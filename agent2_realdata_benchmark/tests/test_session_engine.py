"""Tests for the local fixed-sequence quiz session engine."""

from dataclasses import FrozenInstanceError, replace

import pytest

from src.prototype.item_bank import BANK_VERSION, DEMO_ITEMS
from src.prototype.session_engine import (
    FixedQuizSession,
    ResponseRecord,
)


@pytest.fixture
def items():
    second_practice = replace(
        DEMO_ITEMS[0],
        item_id="synthetic_main_2",
        bloom_level=2,
        prompt="Synthetic second practice fixture",
    )

    return (
        DEMO_ITEMS[0],
        second_practice,
        DEMO_ITEMS[1],
    )


@pytest.fixture
def session(items):
    return FixedQuizSession(
        items=items,
        bank_version=BANK_VERSION,
    )


def test_session_starts_with_first_practice(session):
    assert session.completed is False
    assert session.position == 0
    assert session.bank_version == BANK_VERSION

    question = session.current_public_question()

    assert question["id"] == "demo_main_1"
    assert question["kind"] == "practice"


def test_three_question_sequence(session):
    assert session.current_item.item_id == "demo_main_1"

    session.submit(
        item_id="demo_main_1",
        choice_id="B",
    )

    assert session.position == 1
    assert session.current_item.item_id == "synthetic_main_2"

    session.submit(
        item_id="synthetic_main_2",
        choice_id="A",
    )

    assert session.position == 2
    assert session.current_item.item_id == "demo_probe_1"
    assert session.current_item.kind == "independent_probe"

    session.submit(
        item_id="demo_probe_1",
        choice_id="A",
    )

    assert session.completed is True
    assert session.position == 3
    assert session.current_item is None
    assert session.current_public_question() is None
    assert len(session.responses) == 3


def test_rejected_question_does_not_advance(session):
    with pytest.raises(ValueError, match="Unexpected question"):
        session.submit(
            item_id="demo_probe_1",
            choice_id="A",
        )

    assert session.position == 0
    assert session.responses == ()


def test_invalid_choice_does_not_advance(session):
    with pytest.raises(ValueError, match="Invalid answer"):
        session.submit(
            item_id="demo_main_1",
            choice_id="Z",
        )

    assert session.position == 0
    assert session.responses == ()


def test_non_string_choice_rejected(session):
    with pytest.raises(ValueError, match="Invalid answer"):
        session.submit(
            item_id="demo_main_1",
            choice_id=True,
        )

    assert session.position == 0


def test_duplicate_previous_answer_rejected(session):
    session.submit(
        item_id="demo_main_1",
        choice_id="B",
    )

    with pytest.raises(ValueError, match="Unexpected question"):
        session.submit(
            item_id="demo_main_1",
            choice_id="B",
        )

    assert session.position == 1
    assert len(session.responses) == 1


def test_completed_session_rejects_answers(session):
    for item_id, choice in (
        ("demo_main_1", "B"),
        ("synthetic_main_2", "A"),
        ("demo_probe_1", "A"),
    ):
        session.submit(item_id=item_id, choice_id=choice)

    with pytest.raises(ValueError, match="already complete"):
        session.submit(
            item_id="demo_probe_1",
            choice_id="A",
        )


def test_records_correctness_privately(session):
    correct = session.submit(
        item_id="demo_main_1",
        choice_id="B",
    )

    incorrect = session.submit(
        item_id="synthetic_main_2",
        choice_id="A",
    )

    assert type(correct) is ResponseRecord
    assert correct.correct is True
    assert incorrect.correct is False
    assert correct.position == 0
    assert incorrect.position == 1


def test_answer_keys_not_in_public_question(session):
    question = session.current_public_question()

    assert "correct_id" not in question
    assert "correct" not in question
    assert "answer_key" not in question

    # Public mutations cannot change the internal question bank.
    question["choices"][0]["text"] = "Changed"

    fresh = session.current_public_question()

    assert fresh["choices"][0]["text"] == "Anchoring"


def test_practice_after_probe_is_rejected(items):
    invalid_order = (
        items[0],
        items[2],
        items[1],
    )

    with pytest.raises(ValueError, match="Practice cannot follow"):
        FixedQuizSession(
            items=invalid_order,
            bank_version=BANK_VERSION,
        )


def test_invalid_bank_version_rejected(items):
    for invalid in ("", "  ", None, 123):
        with pytest.raises(ValueError, match="version"):
            FixedQuizSession(
                items=items,
                bank_version=invalid,
            )


def test_independent_sessions(items):
    first = FixedQuizSession(
        items=items,
        bank_version=BANK_VERSION,
    )

    second = FixedQuizSession(
        items=items,
        bank_version=BANK_VERSION,
    )

    first.submit(
        item_id="demo_main_1",
        choice_id="B",
    )

    assert first.position == 1
    assert second.position == 0
    assert second.responses == ()


def test_response_records_are_immutable(session):
    record = session.submit(
        item_id="demo_main_1",
        choice_id="B",
    )

    with pytest.raises(FrozenInstanceError):
        record.correct = False


def test_original_two_question_bank_is_supported():
    session = FixedQuizSession(
        items=DEMO_ITEMS,
        bank_version=BANK_VERSION,
    )

    assert session.current_item.item_id == "demo_main_1"

    session.submit(
        item_id="demo_main_1",
        choice_id="B",
    )

    assert session.current_item.item_id == "demo_probe_1"
