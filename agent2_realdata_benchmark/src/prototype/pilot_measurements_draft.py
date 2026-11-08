"""DRAFT ONLY: pure pilot measurement rules, not wired into deployed Flask/RCT.

A six-timepoint single-item 0..100 M-VAS is PROPOSED, not approved. The
existing fictional six-item questionnaire and operator-demo mode remain
unchanged. Researcher must select validated wording/anchors and visit-spacing
semantics before any human enrollment.

No database access, no display, no production study mode.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


MVAS_PROPOSED_VERSION = "MVAS_MENTAL_FATIGUE_STATE_0_100_PROPOSED_V1"
VISITS = (1, 2, 3)
TIMEPOINTS = ("pre", "post")


def validate_mvas_rating(rating: int) -> int:
    """Prevent missing/boolean/float responses from silently becoming a score."""
    if type(rating) is not int or not 0 <= rating <= 100:
        raise ValueError("expected an explicitly selected integer from 0 through 100")
    return rating


def fatigue_delta(pre: int, post: int) -> int:
    """Post minus pre: positive scores indicate increased perceived fatigue."""
    return validate_mvas_rating(post) - validate_mvas_rating(pre)


@dataclass(frozen=True)
class RatingEvent:
    session: int
    timepoint: str
    rating: int
    timestamp: datetime
    instrument_version: str = MVAS_PROPOSED_VERSION

    def __post_init__(self):
        if type(self.session) is not int or self.session not in VISITS:
            raise ValueError("session must be 1, 2 or 3")
        if self.timepoint not in TIMEPOINTS:
            raise ValueError("timepoint must be pre or post")
        validate_mvas_rating(self.rating)
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must include timezone")
        if self.instrument_version != MVAS_PROPOSED_VERSION:
            raise ValueError("unexpected instrument version")


def validate_visit_gap(previous_finished: datetime,
                       next_started: datetime) -> timedelta:
    """Provisional 72..120 elapsed hours; exact convention requires PI approval."""
    for date in (previous_finished, next_started):
        if date.tzinfo is None or date.utcoffset() is None:
            raise ValueError("visit times must contain a timezone")
    gap = next_started - previous_finished
    if not timedelta(days=3) <= gap <= timedelta(days=5):
        raise ValueError("requires 72..120 elapsed hours between visits (DRAFT)")
    return gap


def check_six_ratings(events: list[RatingEvent]) -> dict[int, int]:
    """Return deltas only after exactly 6 unique, correctly ordered ratings."""
    if len(events) != 6:
        raise ValueError("exactly six ratings required: pre/post in each of 3 sessions")
    lookup: dict[tuple[int, str], RatingEvent] = {}
    for event in events:
        key = (event.session, event.timepoint)
        if key in lookup:
            raise ValueError("duplicate session/timepoint response")
        lookup[key] = event
    if set(lookup) != {(s, p) for s in VISITS for p in TIMEPOINTS}:
        raise ValueError("missing a session or timepoint")
    for s in VISITS:
        if lookup[s, "pre"].timestamp >= lookup[s, "post"].timestamp:
            raise ValueError("post rating must follow pre rating")
    return {
        s: fatigue_delta(lookup[s, "pre"].rating, lookup[s, "post"].rating)
        for s in VISITS
    }
