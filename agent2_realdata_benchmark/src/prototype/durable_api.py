"""Local-only durable Flask quiz API.

SQLite is the authoritative response store.
BKT is reconstructed from committed practice history.
POMCP is shadow-only and never delivers assistance.

Not authorized for collecting real participant data.
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request

from src.prototype.belief import DemoBeliefTracker
from src.prototype.item_bank import (
    BANK_VERSION,
    DEMO_ITEMS,
    QuizItem,
)
from src.prototype.shadow_planner import (
    propose_shadow_recovery,
)
from src.prototype.sqlite_store import (
    ItemBankMismatch,
    ResponseConflict,
    SessionNotFound,
    SQLiteQuizRepository,
)


def create_durable_app(
    database_path: str | Path,
    *,
    items: tuple[QuizItem, ...] = DEMO_ITEMS,
    bank_version: str = BANK_VERSION,
) -> Flask:
    """Create an isolated, file-backed development API."""

    repository = SQLiteQuizRepository(
        database_path,
        items=items,
        bank_version=bank_version,
    )

    app = Flask(__name__)

    # These diagnostics are transient development data.
    # They are not durable research event records.
    shadow_events: list[dict] = []

    app.extensions["durable_quiz_repository"] = repository
    app.extensions["durable_quiz_shadow_events"] = shadow_events

    def error(code: str, status: int):
        return jsonify({"error": code}), status

    @app.get("/api/v1/durable/health")
    def health():
        return jsonify({
            "status": "ok",
            "mode": "local_demo_only",
        })

    @app.post("/api/v1/durable/sessions")
    def create_session():
        session_id = repository.create_session()

        return jsonify({
            "session_id": session_id,
            "bank_version": bank_version,
            "mode": "local_demo_only",
        }), 201

    @app.get(
        "/api/v1/durable/sessions/<session_id>/question"
    )
    def current_question(session_id: str):
        try:
            progress = repository.read_progress(session_id)
        except SessionNotFound:
            return error("unknown_session", 404)
        except ItemBankMismatch:
            return error("item_bank_mismatch", 409)

        return jsonify({
            "complete": progress.completed,
            "position": progress.position,
            "bank_version": progress.bank_version,
            "question": progress.current_question,
        })

    @app.post(
        "/api/v1/durable/sessions/<session_id>/responses"
    )
    def submit_response(session_id: str):
        payload = request.get_json(silent=True)

        if not isinstance(payload, dict):
            return error("expected_json_object", 400)

        try:
            receipt = repository.submit(
                session_id=session_id,
                item_id=payload.get("item_id"),
                choice_id=payload.get("choice_id"),
                request_id=payload.get("request_id"),
            )
        except SessionNotFound:
            return error("unknown_session", 404)
        except ItemBankMismatch:
            return error("item_bank_mismatch", 409)
        except ResponseConflict:
            return error("response_conflict", 409)
        except ValueError:
            return error("invalid_submission", 400)

        record = receipt.record

        # Only a newly committed practice response can
        # trigger a shadow-planning diagnostic.
        #
        # Planning is meaningful here only if the next
        # scheduled item is another practice opportunity
        # addressing the same concept.
        next_position = record.position + 1

        eligible_next_practice = (
            not receipt.replayed
            and record.kind == "practice"
            and next_position < len(items)
            and items[next_position].kind == "practice"
            and (
                items[next_position].concept_id
                == record.concept_id
            )
        )

        if eligible_next_practice:
            try:
                tracker = DemoBeliefTracker()

                # Reconstruct only the causal prefix through
                # this accepted response. Concurrent later
                # answers must not leak into this decision.
                history = repository.read_responses(
                    session_id
                )

                for previous in history:
                    if (
                        previous.position <= record.position
                        and previous.kind == "practice"
                        and previous.concept_id == record.concept_id
                    ):
                        # This tracker estimates only the
                        # concept targeted by the next item.
                        tracker.observe_practice(
                            correct=previous.correct
                        )

                diagnostic = propose_shadow_recovery(
                    tracker,
                    source_row=record.position,
                    session_id=session_id,
                    simulated_permission_to_offer=True,
                    hint_available=True,
                    scaffold_available=True,
                )

                shadow_events.append({
                    "session_id": session_id,
                    "source_position": record.position,
                    "next_item_id": items[
                        next_position
                    ].item_id,
                    "status": "ok",
                    "diagnostic": diagnostic,
                })

            except Exception:
                # Optional shadow planning must never
                # invalidate a committed quiz response.
                app.logger.exception(
                    "Local-only shadow planning failed"
                )

                shadow_events.append({
                    "session_id": session_id,
                    "source_position": record.position,
                    "next_item_id": items[
                        next_position
                    ].item_id,
                    "status": "failed",
                })

        # Student-facing behavior remains fixed.
        # Correctness, BKT beliefs, and simulated actions
        # must not be exposed here.
        return jsonify({
            "accepted": True,
            "replayed": receipt.replayed,
            "complete": receipt.completed,
            "feedback": "withheld",
            "next_action": "no_offer",
        })

    return app
