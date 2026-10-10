"""Local-only tests for BKT integration with the quiz API."""

import pytest

from src.prototype import api as api_module
from src.prototype.belief import DemoBeliefTracker


def start(client):
    result = client.post("/api/v1/demo/sessions")
    assert result.status_code == 201
    return result.get_json()["session_id"]


def submit(client, sid, item_id, choice):
    return client.post(
        f"/api/v1/demo/sessions/{sid}/responses",
        json={
            "item_id": item_id,
            "choice_id": choice,
        },
    )


def test_only_practice_updates_belief(monkeypatch):
    observed = []
    original = DemoBeliefTracker.observe_practice

    def recording_update(self, *, correct):
        event = original(self, correct=correct)
        observed.append(event)
        return event

    monkeypatch.setattr(
        DemoBeliefTracker,
        "observe_practice",
        recording_update,
    )

    client = api_module.create_app().test_client()
    sid = start(client)

    first = submit(
        client, sid, "demo_main_1", "B"
    )

    assert first.status_code == 200
    assert len(observed) == 1
    assert observed[0].correct is True
    assert observed[0].mastery_after > 0.2

    second = submit(
        client, sid, "demo_probe_1", "A"
    )

    assert second.status_code == 200

    # The independent probe must not cause a
    # second practice-model learning transition.
    assert len(observed) == 1


def test_sessions_have_independent_beliefs(monkeypatch):
    trackers = []

    class CapturingTracker(DemoBeliefTracker):
        def __init__(self):
            super().__init__()
            trackers.append(self)

    monkeypatch.setattr(
        api_module,
        "DemoBeliefTracker",
        CapturingTracker,
    )

    client = api_module.create_app().test_client()

    first = start(client)
    second = start(client)

    assert len(trackers) == 2

    result = submit(
        client, first, "demo_main_1", "B"
    )

    assert result.status_code == 200
    assert trackers[0].mastery > 0.2
    assert trackers[1].mastery == pytest.approx(0.2)

    assert first != second


def test_api_does_not_expose_internal_beliefs():
    client = api_module.create_app().test_client()
    sid = start(client)

    response = submit(
        client, sid, "demo_main_1", "B"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["accepted"] is True
    assert data["feedback"] == "withheld"
    assert data["next_action"] == "no_offer"

    assert "correct" not in data
    assert "mastery" not in data
    assert "belief_events" not in data
    assert "pre_response_probability" not in data
