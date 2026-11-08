"""Pure session-flow draft tests; no real participants, DB, or network."""
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from src.prototype.pilot_session_flow_draft import (
    PilotSequenceError, PilotSessionFlow, answer_question, fatigue_deltas,
    record_mvas, start_visit,
)

T0 = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
AUTH = dict(staff_authorized=True, release_authorized=True)


def advance_questions(state, number, at):
    for _ in range(number):
        state = answer_question(state, at=at)
    return state


def visit1():
    state = start_visit(PilotSessionFlow(), at=T0, visit=1, **AUTH)
    state = advance_questions(state, 16, T0 + timedelta(minutes=30))
    assert state.stage == "mvas_pre"
    state = record_mvas(state, at=T0 + timedelta(minutes=31), rating=22)
    assert state.stage == "practice"
    state = advance_questions(state, 20, T0 + timedelta(minutes=60))
    state = record_mvas(state, at=T0 + timedelta(minutes=61), rating=43)
    return state


def test_first_visit_and_time_gated_second_visit():
    state = visit1()
    assert state.stage == "awaiting_visit"
    assert state.session == 1
    assert fatigue_deltas(state) == (21, None, None)
    with pytest.raises(PilotSequenceError, match="72..120"):
        start_visit(state, visit=2, at=T0 + timedelta(days=2), **AUTH)
    state = start_visit(state, visit=2, at=state.visit_finished_at[-1]+timedelta(days=4), **AUTH)
    assert state.stage == "mvas_pre"
    assert state.session == 2


def test_complete_three_visits_with_six_ratings_and_55_practice_questions():
    state = visit1()
    v2 = state.visit_finished_at[-1] + timedelta(days=4)
    state = start_visit(state, at=v2, visit=2, **AUTH)
    state = record_mvas(state, at=v2, rating=18)
    state = advance_questions(state, 20, v2 + timedelta(minutes=29))
    state = record_mvas(state, at=v2+timedelta(minutes=30), rating=30)
    assert state.stage == "awaiting_visit"
    v3 = state.visit_finished_at[-1] + timedelta(days=4)
    state = start_visit(state, at=v3, visit=3, **AUTH)
    state = record_mvas(state, at=v3, rating=31)
    state = advance_questions(state, 15, v3 + timedelta(minutes=30))
    state = record_mvas(state, at=v3+timedelta(minutes=31), rating=39)
    assert state.stage == "posttest"
    state = advance_questions(state, 16, v3+timedelta(minutes=45))
    assert state.stage == "complete"
    assert state.index == 0
    assert len(state.visit_finished_at) == len(state.visit_started_at) == 3
    assert fatigue_deltas(state) == (21, 12, 8)
    with pytest.raises(PilotSequenceError):
        answer_question(state, at=v3 + timedelta(minutes=46))
    with pytest.raises(PilotSequenceError):
        start_visit(state, at=v3 + timedelta(days=4), visit=4, **AUTH)


def test_no_unapproved_or_unstaffed_start():
    state = PilotSessionFlow()
    with pytest.raises(PilotSequenceError):
        start_visit(state, at=T0, visit=1, staff_authorized=False, release_authorized=True)
    with pytest.raises(PilotSequenceError):
        start_visit(state, at=T0, visit=1, staff_authorized=True, release_authorized=False)
    with pytest.raises(PilotSequenceError):
        start_visit(state, at=T0.replace(tzinfo=None), visit=1, **AUTH)


def test_rejected_duplicate_measurement_and_invalid_rating():
    state = visit1()
    with pytest.raises((ValueError, PilotSequenceError)):
        record_mvas(state, at=T0 + timedelta(days=1), rating=50)
    state = start_visit(state, at=state.visit_finished_at[-1]+timedelta(days=3), visit=2, **AUTH)
    with pytest.raises(ValueError):
        record_mvas(state, at=state.visit_started_at[-1], rating=True)
    state = record_mvas(state, at=state.visit_started_at[-1], rating=0)
    with pytest.raises(PilotSequenceError):
        record_mvas(state, at=state.visit_started_at[-1], rating=40)


def test_wrong_order_or_missing_early_stage():
    state = PilotSessionFlow()
    with pytest.raises(PilotSequenceError):
        answer_question(state, at=T0)
    with pytest.raises(PilotSequenceError):
        record_mvas(state, at=T0, rating=10)
    state = start_visit(state, at=T0, visit=1, **AUTH)
    with pytest.raises(PilotSequenceError):
        start_visit(state, at=T0, visit=1, **AUTH)
    with pytest.raises(PilotSequenceError):
        record_mvas(state, at=T0, rating=20)
    with pytest.raises(PilotSequenceError):
        start_visit(state, at=T0 + timedelta(days=4), visit=2, **AUTH)


def test_immutable_state_and_exact_window_boundaries():
    a = PilotSessionFlow()
    with pytest.raises(FrozenInstanceError):
        a.stage = "complete"
    state = visit1()
    finish = state.visit_finished_at[-1]
    assert start_visit(state, at=finish+timedelta(days=3), visit=2, **AUTH).stage == "mvas_pre"
    assert start_visit(state, at=finish+timedelta(days=5), visit=2, **AUTH).stage == "mvas_pre"
    with pytest.raises(PilotSequenceError):
        start_visit(state, at=finish+timedelta(days=5,seconds=1), visit=2, **AUTH)


def test_no_backward_clock_events_and_timestamps_persist():
    state = start_visit(PilotSessionFlow(), at=T0, visit=1, **AUTH)
    with pytest.raises(PilotSequenceError, match="precedes"):
        answer_question(state, at=T0-timedelta(minutes=1))
    state = advance_questions(state, 16, T0+timedelta(minutes=10))
    state = record_mvas(state, at=T0+timedelta(minutes=11), rating=20)
    assert state.rating_timestamps[0][0] == T0+timedelta(minutes=11)
    with pytest.raises(PilotSequenceError, match="precedes"):
        answer_question(state, at=T0+timedelta(minutes=10))
    state = advance_questions(state, 20, T0+timedelta(minutes=20))
    with pytest.raises(PilotSequenceError):
        record_mvas(state, at=T0+timedelta(minutes=11), rating=25)
    state = record_mvas(state, at=T0+timedelta(minutes=21), rating=25)
    assert state.rating_timestamps[0][1] == T0+timedelta(minutes=21)
