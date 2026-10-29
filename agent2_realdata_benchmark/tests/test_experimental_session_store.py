"""Development-only allocated-policy integration tests."""

import sqlite3

from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.prototype.assistance_store import AssistanceConflict

from src.prototype.experimental_session_store import (
    ExperimentalConfigurationMismatch,
    SQLiteExperimentalQuizRepository,
)

from src.prototype.gated_assistance_store import (
    SQLiteFixedSummaryQuizRepository,
)

from src.prototype.item_bank import (
    INSTRUCTIONAL_DEMO_ITEMS,
    INSTRUCTIONAL_DEMO_VERSION,
)

from src.prototype.sqlite_store import (
    RepositoryModeMismatch,
    ResponseConflict,
)

from src.prototype.trial_allocation import (
    SQLiteTrialAllocationStore,
)


def setup_stores(tmp_path, *, threshold=0.30):

    path = tmp_path / "trial-dev.sqlite3"

    allocator = SQLiteTrialAllocationStore(
        path,
        block_sizes=(6,),
    )

    quiz = SQLiteExperimentalQuizRepository(
        path,
        items=INSTRUCTIONAL_DEMO_ITEMS,
        bank_version=INSTRUCTIONAL_DEMO_VERSION,
        threshold=threshold,
    )

    return path, allocator, quiz


def allocated_sessions(allocator, quiz):
    """Find one synthetic participant in each arm."""

    sessions = {}

    for i in range(6):

        assignment = allocator.allocate(
            enrollment_request_id=f"synthetic-{i}"
        )

        session_id = quiz.create_session_for_participant(
            participant_id=assignment.participant_id
        )

        sessions.setdefault(
            assignment.policy_mode,
            (assignment, session_id),
        )

    assert set(sessions) == {
        "control",
        "fixed_summary",
        "adaptive_threshold",
    }

    return sessions


def answer(quiz, session_id, position, choice):

    item = INSTRUCTIONAL_DEMO_ITEMS[position]

    return quiz.submit(
        session_id=session_id,
        item_id=item.item_id,
        choice_id=choice,
        request_id=f"request-{session_id}-{position}",
    )


def test_allocated_session_is_idempotent(tmp_path):

    path, allocator, quiz = setup_stores(tmp_path)

    assignment = allocator.allocate(
        enrollment_request_id="one"
    )

    first = quiz.create_session_for_participant(
        participant_id=assignment.participant_id
    )

    second = quiz.create_session_for_participant(
        participant_id=assignment.participant_id
    )

    restarted = SQLiteExperimentalQuizRepository(
        path,
        items=INSTRUCTIONAL_DEMO_ITEMS,
        bank_version=INSTRUCTIONAL_DEMO_VERSION,
    )

    third = restarted.create_session_for_participant(
        participant_id=assignment.participant_id
    )

    assert first == second == third

    assert restarted.read_policy(first) == (
        assignment.policy_mode
    )


def test_cannot_create_unallocated_session(tmp_path):

    _, _, quiz = setup_stores(tmp_path)

    with pytest.raises(PermissionError):
        quiz.create_session()

    with pytest.raises(LookupError):
        quiz.create_session_for_participant(
            participant_id="unknown"
        )


def test_policy_modes_are_isolated(tmp_path):

    _, allocator, quiz = setup_stores(tmp_path)

    sessions = allocated_sessions(allocator, quiz)

    for mode, (_, session_id) in sessions.items():

        answer(quiz, session_id, 0, "A")

        decision, = quiz.read_policy_decisions(
            session_id
        )

        assert decision.policy_mode == mode

        assert decision.offer_summary == (
            mode != "control"
        )

        assert (
            quiz.current_offer(session_id) is not None
        ) == (mode != "control")


def test_adaptive_policy_uses_past_response_only(tmp_path):

    _, allocator, quiz = setup_stores(tmp_path)

    session = allocated_sessions(
        allocator,
        quiz,
    )["adaptive_threshold"][1]

    answer(quiz, session, 0, "B")

    decision, = quiz.read_policy_decisions(session)

    assert decision.offer_summary is False

    assert decision.mastery_belief == pytest.approx(
        0.5263157894736842
    )

    assert quiz.current_offer(session) is None


def test_pending_assistance_blocks_progress(tmp_path):

    _, allocator, quiz = setup_stores(tmp_path)

    session = allocated_sessions(
        allocator,
        quiz,
    )["fixed_summary"][1]

    answer(quiz, session, 0, "B")

    with pytest.raises(ResponseConflict):
        answer(quiz, session, 1, "B")

    quiz.decide(
        session_id=session,
        source_position=0,
        accept=False,
    )

    answer(quiz, session, 1, "B")

    assert len(
        quiz.read_policy_decisions(session)
    ) == 2


def test_replayed_response_does_not_repeat_decision(tmp_path):

    _, allocator, quiz = setup_stores(tmp_path)

    session = allocated_sessions(
        allocator,
        quiz,
    )["fixed_summary"][1]

    first = answer(quiz, session, 0, "B")
    replay = answer(quiz, session, 0, "B")

    assert first.replayed is False
    assert replay.replayed is True

    assert len(
        quiz.read_policy_decisions(session)
    ) == 1

    assert quiz.read_events(
        session_id=session,
        source_position=0,
    ) == ("proposed", "offered")


def test_control_completes_without_extra_assistance(tmp_path):

    _, allocator, quiz = setup_stores(tmp_path)

    session = allocated_sessions(
        allocator,
        quiz,
    )["control"][1]

    for i, choice in enumerate(
        ("B", "B", "B", "A")
    ):
        answer(quiz, session, i, choice)

    assert quiz.read_progress(session).completed

    decisions = quiz.read_policy_decisions(session)

    assert [
        decision.offer_summary
        for decision in decisions
    ] == [False, False]

    assert quiz.current_offer(session) is None


def test_manual_offer_bypass_is_forbidden(tmp_path):

    _, allocator, quiz = setup_stores(tmp_path)

    session = allocated_sessions(
        allocator,
        quiz,
    )["control"][1]

    answer(quiz, session, 0, "B")

    with pytest.raises(AssistanceConflict):
        quiz.offer_after_practice(
            session_id=session,
            source_position=0,
        )


def test_rejects_policy_tampering(tmp_path):

    path, allocator, quiz = setup_stores(tmp_path)

    sessions = allocated_sessions(allocator, quiz)

    _, session = sessions["fixed_summary"]

    with sqlite3.connect(path) as connection:

        connection.execute(
            """
            UPDATE experimental_session_policies
            SET policy_mode = 'control'
            WHERE session_id = ?
            """,
            (session,),
        )

    with pytest.raises(
        ExperimentalConfigurationMismatch
    ):
        quiz.read_policy(session)


def test_threshold_cannot_change_on_restart(tmp_path):

    path, _, _ = setup_stores(tmp_path)

    with pytest.raises(
        ExperimentalConfigurationMismatch
    ):
        SQLiteExperimentalQuizRepository(
            path,
            items=INSTRUCTIONAL_DEMO_ITEMS,
            bank_version=INSTRUCTIONAL_DEMO_VERSION,
            threshold=0.40,
        )


def test_existing_fixed_summary_mode_is_incompatible(
    tmp_path,
):

    path, _, _ = setup_stores(tmp_path)

    with pytest.raises(RepositoryModeMismatch):
        SQLiteFixedSummaryQuizRepository(
            path,
            items=INSTRUCTIONAL_DEMO_ITEMS,
            bank_version=INSTRUCTIONAL_DEMO_VERSION,
        )


def test_concurrent_rebinding_is_idempotent(tmp_path):

    _, allocator, quiz = setup_stores(tmp_path)

    participant = allocator.allocate(
        enrollment_request_id="concurrent"
    ).participant_id

    with ThreadPoolExecutor(
        max_workers=8
    ) as pool:

        session_ids = list(
            pool.map(
                lambda _: quiz.create_session_for_participant(
                    participant_id=participant
                ),
                range(20),
            )
        )

    assert len(set(session_ids)) == 1
