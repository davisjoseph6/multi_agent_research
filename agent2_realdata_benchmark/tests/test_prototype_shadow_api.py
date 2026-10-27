"""Tests for internal-only shadow planning in the local API."""

from src.prototype import api as api_module


def start(client):
    response = client.post("/api/v1/demo/sessions")
    assert response.status_code == 201
    return response.get_json()["session_id"]


def submit(client, sid, item_id, choice):
    return client.post(
        f"/api/v1/demo/sessions/{sid}/responses",
        json={
            "item_id": item_id,
            "choice_id": choice,
        },
    )


def capture_shadow(monkeypatch):
    observed = []
    original = api_module.propose_shadow_recovery

    def wrapped(*args, **kwargs):
        result = original(*args, **kwargs)
        observed.append(result)
        return result

    monkeypatch.setattr(
        api_module,
        "propose_shadow_recovery",
        wrapped,
    )

    return observed


def test_incorrect_practice_triggers_internal_shadow(monkeypatch):
    observed = capture_shadow(monkeypatch)
    client = api_module.create_app().test_client()
    sid = start(client)

    response = submit(
        client, sid, "demo_main_1", "A"
    )

    assert response.status_code == 200
    assert len(observed) == 1

    decision = observed[0]

    assert decision.detector_status == "flag"
    assert decision.recovery_disposition == "proposed"
    assert decision.mode == "hypothetical_shadow_only"

    # Actual HTTP workflow remains fixed and unassisted.
    data = response.get_json()

    assert data["next_action"] == "no_offer"
    assert "simulated_action" not in data
    assert "mastery_belief" not in data
    assert "predicted_correctness" not in data


def test_correct_practice_does_not_flag(monkeypatch):
    observed = capture_shadow(monkeypatch)
    client = api_module.create_app().test_client()
    sid = start(client)

    response = submit(
        client, sid, "demo_main_1", "B"
    )

    assert response.status_code == 200
    assert len(observed) == 1

    assert observed[0].detector_status == "no_flag"
    assert observed[0].simulated_action == "no_offer"


def test_independent_probe_does_not_replan(monkeypatch):
    observed = capture_shadow(monkeypatch)
    client = api_module.create_app().test_client()
    sid = start(client)

    first = submit(
        client, sid, "demo_main_1", "A"
    )
    assert first.status_code == 200
    assert len(observed) == 1

    probe = submit(
        client, sid, "demo_probe_1", "A"
    )

    assert probe.status_code == 200
    assert len(observed) == 1
    assert probe.get_json()["complete"] is True


def test_invalid_practice_answer_does_not_plan(monkeypatch):
    observed = capture_shadow(monkeypatch)
    client = api_module.create_app().test_client()
    sid = start(client)

    response = submit(
        client, sid, "demo_main_1", "Z"
    )

    assert response.status_code == 400
    assert observed == []


def test_shadow_result_is_not_public(monkeypatch):
    observed = capture_shadow(monkeypatch)
    client = api_module.create_app().test_client()
    sid = start(client)

    response = submit(
        client, sid, "demo_main_1", "A"
    )

    assert len(observed) == 1
    data = response.get_json()

    assert data["feedback"] == "withheld"
    assert data["next_action"] == "no_offer"

    forbidden = {
        "correct",
        "mastery",
        "mastery_belief",
        "predicted_correctness",
        "simulated_action",
        "allowed_actions",
        "simulated_expected_return",
    }

    assert forbidden.isdisjoint(data)


def test_planner_failure_does_not_duplicate_response(monkeypatch):
    """An unavailable shadow planner must not corrupt quiz flow."""

    from src.prototype.belief import DemoBeliefTracker

    updates = []
    original_update = DemoBeliefTracker.observe_practice

    def recording_update(self, *, correct):
        result = original_update(self, correct=correct)
        updates.append(result)
        return result

    def failing_planner(*args, **kwargs):
        raise RuntimeError("Synthetic planner failure")

    monkeypatch.setattr(
        DemoBeliefTracker,
        "observe_practice",
        recording_update,
    )

    monkeypatch.setattr(
        api_module,
        "propose_shadow_recovery",
        failing_planner,
    )

    client = api_module.create_app().test_client()
    sid = start(client)

    response = submit(
        client, sid, "demo_main_1", "A"
    )

    assert response.status_code == 200
    assert response.get_json()["accepted"] is True
    assert response.get_json()["next_action"] == "no_offer"
    assert len(updates) == 1

    # The question index must have advanced despite
    # the shadow planner's failure.
    current = client.get(
        f"/api/v1/demo/sessions/{sid}/question"
    )

    assert current.status_code == 200
    assert (
        current.get_json()["question"]["id"]
        == "demo_probe_1"
    )

    # Replaying the previous response must fail.
    duplicate = submit(
        client, sid, "demo_main_1", "A"
    )

    assert duplicate.status_code == 409
    assert len(updates) == 1

    # The independent probe remains usable.
    completed = submit(
        client, sid, "demo_probe_1", "A"
    )

    assert completed.status_code == 200
    assert completed.get_json()["complete"] is True
    assert len(updates) == 1
