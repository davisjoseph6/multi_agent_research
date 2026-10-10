"""Local-only IJCAI quiz API demonstration.

Not for real participant recruitment or research data collection.
No persistence, learner modelling, intervention delivery, or POMCP.
"""

from __future__ import annotations

from uuid import uuid4

from flask import Flask, abort, jsonify, request

from src.prototype.belief import DemoBeliefTracker


_DEMO_ITEMS = (
    {
        "id": "demo_main_1",
        "kind": "practice",
        "concept_id": "loss_aversion",
        "prompt": (
            "Which concept describes losses being felt more "
            "strongly than equivalent gains?"
        ),
        "choices": (
            {"id": "A", "text": "Anchoring"},
            {"id": "B", "text": "Loss aversion"},
            {"id": "C", "text": "Mental accounting"},
        ),
        "correct_id": "B",
    },
    {
        "id": "demo_probe_1",
        "kind": "independent_probe",
        "concept_id": "loss_aversion",
        "prompt": (
            "Which observation is most consistent with "
            "loss aversion?"
        ),
        "choices": (
            {
                "id": "A",
                "text": (
                    "Avoiding a loss matters more than "
                    "an equally sized gain"
                ),
            },
            {
                "id": "B",
                "text": "Losses and gains always feel identical",
            },
            {
                "id": "C",
                "text": "Prior prices never affect decisions",
            },
        ),
        "correct_id": "A",
    },
)


def _public_question(item: dict) -> dict:
    """Never expose answer keys through the question API."""

    return {
        "id": item["id"],
        "kind": item["kind"],
        "concept_id": item["concept_id"],
        "prompt": item["prompt"],
        "choices": list(item["choices"]),
    }


def create_app() -> Flask:
    """Create a new isolated in-memory development application."""

    app = Flask(__name__)
    sessions: dict[str, dict] = {}

    def get_session(session_id: str) -> dict:
        session = sessions.get(session_id)

        if session is None:
            abort(404, description="Unknown demo session")

        return session

    @app.get("/api/v1/demo/health")
    def health():
        return jsonify({
            "status": "ok",
            "mode": "local_demo_only",
        })

    @app.post("/api/v1/demo/sessions")
    def start_session():
        session_id = uuid4().hex

        sessions[session_id] = {
            "index": 0,
            "responses": [],
            "belief_tracker": DemoBeliefTracker(),
            "belief_events": [],
        }

        return jsonify({
            "session_id": session_id,
            "mode": "local_demo_only",
        }), 201

    @app.get(
        "/api/v1/demo/sessions/<session_id>/question"
    )
    def current_question(session_id: str):
        session = get_session(session_id)
        index = session["index"]

        if index >= len(_DEMO_ITEMS):
            return jsonify({
                "complete": True,
                "question": None,
            })

        return jsonify({
            "complete": False,
            "question": _public_question(
                _DEMO_ITEMS[index]
            ),
        })

    @app.post(
        "/api/v1/demo/sessions/<session_id>/responses"
    )
    def submit_response(session_id: str):
        session = get_session(session_id)
        index = session["index"]

        if index >= len(_DEMO_ITEMS):
            return jsonify({
                "error": "Session already complete"
            }), 409

        payload = request.get_json(silent=True)

        if not isinstance(payload, dict):
            return jsonify({
                "error": "Expected JSON object"
            }), 400

        item = _DEMO_ITEMS[index]

        if payload.get("item_id") != item["id"]:
            return jsonify({
                "error": "Unexpected question ID"
            }), 409

        choice = payload.get("choice_id")
        allowed = {x["id"] for x in item["choices"]}

        if type(choice) is not str or choice not in allowed:
            return jsonify({
                "error": "Invalid answer choice"
            }), 400

        is_correct = choice == item["correct_id"]

        session["responses"].append({
            "item_id": item["id"],
            "kind": item["kind"],
            "correct": is_correct,
        })

        # Practice updates the internal learner belief.
        # Independent assessment does not update this
        # practice model before the probe outcome is recorded.
        if item["kind"] == "practice":
            event = session[
                "belief_tracker"
            ].observe_practice(correct=is_correct)

            session["belief_events"].append(event)

        session["index"] += 1

        return jsonify({
            "accepted": True,
            "complete": (
                session["index"] == len(_DEMO_ITEMS)
            ),
            "feedback": "withheld",
            "next_action": "no_offer",
        })

    return app


if __name__ == "__main__":
    create_app().run(
        host="127.0.0.1",
        port=5050,
        debug=False,
    )
