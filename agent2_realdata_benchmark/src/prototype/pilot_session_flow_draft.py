"""Disconnected, fail-closed educational pilot session-flow prototype.

**NOT approved**, NOT imported by the active RCT candidate, Flask or the VPS.
The live demonstration's existing six-item post-session questionnaire is unchanged.

Scientific assumptions still needing approval:
- One 0-100 state M-VAS immediately before/after learning, at each visit.
- Session 1 is preceded by the 16-question baseline assessment.
- Visits 2/3 begin 72 to 120 elapsed hours after the previous visit ends.
- Three blocks of practice: 20/20/15; final independent posttest: 16.

This immutable pure model does NOT authenticate staff, verify signatures,
write to a database, implement HTTP idempotency, or handle real consent.
A caller must implement independently authorized and audited server checks.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

from .pilot_measurements_draft import validate_mvas_rating, validate_visit_gap


Stage = Literal["awaiting_visit", "pretest", "mvas_pre", "practice",
                "mvas_post", "posttest", "complete"]
PRACTICE_TARGETS = (20, 20, 15)


class PilotSequenceError(ValueError):
    """State transition not possible under draft research sequence."""


@dataclass(frozen=True)
class PilotSessionFlow:
    stage: Stage = "awaiting_visit"
    session: int = 0
    index: int = 0
    # Deliberately fixed to 3 sessions; NOT a psychometric validation.
    ratings: tuple[tuple[int | None, int | None], ...] = (
        (None, None), (None, None), (None, None)
    )
    rating_timestamps: tuple[tuple[datetime | None, datetime | None], ...] = (
        (None, None), (None, None), (None, None)
    )
    visit_started_at: tuple[datetime, ...] = ()
    visit_finished_at: tuple[datetime, ...] = ()
    last_event_at: datetime | None = None


def _check_time(at: datetime) -> None:
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise PilotSequenceError("server timestamp must be timezone-aware")


def _check_order(state: PilotSessionFlow, at: datetime) -> None:
    _check_time(at)
    if state.last_event_at is not None and at < state.last_event_at:
        raise PilotSequenceError("event timestamp precedes previous accepted event")


def start_visit(
    state: PilotSessionFlow, *, at: datetime, visit: int,
    staff_authorized: bool, release_authorized: bool,
) -> PilotSessionFlow:
    """Represent external authorization decisions; does not perform them.

    In production, authorizations MUST be established server-side and audited;
    a web client boolean is not an acceptable authorization source.
    """
    _check_order(state, at)
    if staff_authorized is not True or release_authorized is not True:
        raise PilotSequenceError("externally approved study release and staff authorization required")
    if state.stage != "awaiting_visit" or visit != state.session + 1 or visit not in (1, 2, 3):
        raise PilotSequenceError("out-of-order visit or session already active")
    if visit > 1:
        if len(state.visit_finished_at) != visit - 1:
            raise PilotSequenceError("prior visit has no valid completed timestamp")
        try:
            validate_visit_gap(state.visit_finished_at[-1], at)
        except ValueError as e:
            raise PilotSequenceError(str(e)) from e
    return replace(state, stage="pretest" if visit == 1 else "mvas_pre",
                   session=visit, index=0,
                   visit_started_at=state.visit_started_at + (at,), last_event_at=at)


def answer_question(state: PilotSessionFlow, *, at: datetime) -> PilotSessionFlow:
    """Advance the flow on verified recorded completion of one distinct MCQ.

    Does not validate an actual answer or its ownership; real action logic
    must check action IDs, rendered acknowledgement and request replay.
    """
    _check_order(state, at)
    if state.stage == "pretest":
        limit, next_stage = 16, "mvas_pre"
    elif state.stage == "practice":
        limit, next_stage = PRACTICE_TARGETS[state.session - 1], "mvas_post"
    elif state.stage == "posttest":
        limit, next_stage = 16, "complete"
    else:
        raise PilotSequenceError("no MCQ expected in this stage")
    if not state.visit_started_at or at < state.visit_started_at[-1]:
        raise PilotSequenceError("question event precedes supervised visit")
    index = state.index + 1
    if index > limit:
        raise PilotSequenceError("question budget exceeded")
    if index == limit:
        return replace(state, stage=next_stage, index=0, last_event_at=at,
                       visit_finished_at=(state.visit_finished_at + (at,) if
                                          next_stage == "complete" else state.visit_finished_at))
    return replace(state, index=index, last_event_at=at)


def record_mvas(state: PilotSessionFlow, *, at: datetime, rating: int) -> PilotSessionFlow:
    """Record exactly one expressly selected proposed 0..100 measurement."""
    _check_order(state, at)
    validate_mvas_rating(rating)
    if state.stage not in ("mvas_pre", "mvas_post") or state.session not in (1, 2, 3):
        raise PilotSequenceError("M-VAS is not expected in this stage")
    if not state.visit_started_at or at < state.visit_started_at[-1]:
        raise PilotSequenceError("fatigue response precedes visit")
    ratings = [list(v) for v in state.ratings]
    slot = 0 if state.stage == "mvas_pre" else 1
    if ratings[state.session - 1][slot] is not None:
        raise PilotSequenceError("duplicate fatigue response")
    if slot == 1 and ratings[state.session - 1][0] is None:
        raise PilotSequenceError("post-fatigue requires pre-fatigue")
    rating_times = [list(v) for v in state.rating_timestamps]
    if slot == 1 and rating_times[state.session - 1][0] is not None and at <= rating_times[state.session - 1][0]:
        raise PilotSequenceError("post-fatigue timestamp must be after pre-fatigue")
    ratings[state.session - 1][slot] = rating
    rating_times[state.session - 1][slot] = at
    new_ratings = tuple(tuple(x) for x in ratings)
    new_times = tuple(tuple(x) for x in rating_times)
    if slot == 0:
        return replace(state, stage="practice", index=0, ratings=new_ratings,
                       rating_timestamps=new_times, last_event_at=at)
    if state.session == 3:
        return replace(state, stage="posttest", index=0, ratings=new_ratings,
                       rating_timestamps=new_times, last_event_at=at)
    return replace(state, stage="awaiting_visit", index=0,
                   ratings=new_ratings, rating_timestamps=new_times, last_event_at=at,
                   visit_finished_at=state.visit_finished_at + (at,))


def fatigue_deltas(state: PilotSessionFlow) -> tuple[int | None, int | None, int | None]:
    """Missing results stay NULL, never silently converted to zero."""
    return tuple(
        None if pre is None or post is None else post - pre
        for pre, post in state.ratings
    )  # type: ignore[return-value]
