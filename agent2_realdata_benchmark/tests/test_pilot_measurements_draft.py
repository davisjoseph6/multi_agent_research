"""Unit tests for draft pure rules; NOT a validated fatigue instrument or RCT."""
from datetime import datetime, timedelta, timezone

import pytest

from src.prototype.pilot_measurements_draft import (
    RatingEvent, check_six_ratings, fatigue_delta,
    validate_mvas_rating, validate_visit_gap,
)


def test_mvas_rating_boundaries_and_no_silent_cast():
    assert validate_mvas_rating(0) == 0
    assert validate_mvas_rating(100) == 100
    for invalid in (-1, 101, 25.0, True, None, "50"):
        with pytest.raises(ValueError):
            validate_mvas_rating(invalid)


def test_fatigue_post_minus_pre():
    assert fatigue_delta(32, 51) == 19
    assert fatigue_delta(35, 21) == -14


def test_exact_six_observations_and_duplicates():
    start = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    events = [
        RatingEvent(session=s, timepoint=point, rating=10*s + (4 if point=="post" else 0),
                    timestamp=start + timedelta(days=4*(s-1),hours=1 if point=="post" else 0))
        for s in (1, 2, 3) for point in ("pre", "post")
    ]
    assert check_six_ratings(events) == {1: 4, 2: 4, 3: 4}
    with pytest.raises(ValueError):
        check_six_ratings(events[:-1])
    with pytest.raises(ValueError):
        check_six_ratings(events[:-1] + [events[0]])


def test_provisional_elapsed_hours_gap():
    t = datetime(2026, 11, 20, 10, tzinfo=timezone.utc)
    assert validate_visit_gap(t, t + timedelta(days=3)) == timedelta(days=3)
    assert validate_visit_gap(t, t + timedelta(days=5)) == timedelta(days=5)
    with pytest.raises(ValueError):
        validate_visit_gap(t, t + timedelta(hours=71))
    with pytest.raises(ValueError):
        validate_visit_gap(t, t + timedelta(hours=121))
    with pytest.raises(ValueError):
        validate_visit_gap(t.replace(tzinfo=None), t + timedelta(days=3))
