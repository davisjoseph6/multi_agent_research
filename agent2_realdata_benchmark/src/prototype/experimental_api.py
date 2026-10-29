"""Local-only experimental quiz API.

Synthetic development sessions only.
No authentication, approved trial, or participant consent
management is provided by this module.

Do not deploy to a public interface.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from flask import Flask, jsonify, request

from src.prototype.assistance_store import AssistanceConflict
from src.prototype.experimental_session_store import (
    ExperimentalConfigurationMismatch,
    SQLiteExperimentalQuizRepository,
)
from src.prototype.item_bank import (
    INSTRUCTIONAL_DEMO_ITEMS,
    INSTRUCTIONAL_DEMO_VERSION,
)
from src.prototype.sqlite_store import (
    ItemBankMismatch,
    ResponseConflict,
    SessionNotFound,
)
from src.prototype.trial_allocation import (
    SQLiteTrialAllocationStore,
)


PREFIX = "/api/v1/trial-dev"


def create_experimental_app(
    database_path: str | Path,
    *,
    threshold: float = 0.30,
    block_sizes: tuple[int, ...] = (6, 9),
) -> Flask:
    """Create a development-only experimental API."""

    allocator = SQLiteTrialAllocationStore(
        database_path,
        block_sizes=block_sizes,
    )

    quiz = SQLiteExperimentalQuizRepository(
        database_path,
        items=INSTRUCTIONAL_DEMO_ITEMS,
        bank_version=INSTRUCTIONAL_DEMO_VERSION,
        threshold=threshold,
    )

    app = Flask(__name__)

    app.extensions["trial_dev_allocator"] = allocator
    app.extensions["trial_dev_quiz"] = quiz

    def error(code, status):
        return jsonify({"error": code}), status

    def exact_json(keys):
        payload = request.get_json(silent=True)

        if (
            type(payload) is not dict
            or set(payload) != set(keys)
        ):
            return None

        return payload

    @app.after_request
    def protect_response(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get(f"{PREFIX}/health")
    def health():
        return jsonify({
            "status": "ok",
            "mode": "trial_development_only",
        })

    @app.post(f"{PREFIX}/enroll")
    def enroll():
        """Synthetic enrollment; never returns the policy arm."""

        payload = exact_json({"enrollment_request_id"})

        if payload is None:
            return error("invalid_enrollment", 400)

        try:
            assignment = allocator.allocate(
                enrollment_request_id=payload[
                    "enrollment_request_id"
                ]
            )

            session_id = quiz.create_session_for_participant(
                participant_id=assignment.participant_id
            )

        except (TypeError, ValueError):
            return error("invalid_enrollment", 400)

        return jsonify({
            "session_id": session_id,
            "replayed": assignment.replayed,
            "mode": "trial_development_only",
        }), (200 if assignment.replayed else 201)

    @app.get(f"{PREFIX}/sessions/<session_id>/question")
    def question(session_id):
        try:
            progress = quiz.read_progress(session_id)

            offer = (
                None
                if progress.completed
                else quiz.current_offer(session_id)
            )

        except SessionNotFound:
            return error("unknown_session", 404)

        except ItemBankMismatch:
            return error("item_bank_mismatch", 409)

        pending = (
            offer is not None
            and offer.status in ("offered", "accepted")
        )

        # No correct answers, mastery estimates or
        # experimental assignments are returned.
        return jsonify({
            "complete": progress.completed,
            "position": progress.position,
            "bank_version": progress.bank_version,
            "question": (
                None if pending
                else progress.current_question
            ),
            "assistance_pending": pending,
            "assistance": (
                {
                    "source_position": offer.source_position,
                    "target_position": offer.target_position,
                    "resource_id": offer.resource_id,
                    "title": offer.title,
                    "status": offer.status,
                }
                if offer is not None
                else None
            ),
        })

    @app.post(f"{PREFIX}/sessions/<session_id>/responses")
    def submit_response(session_id):
        payload = exact_json({
            "item_id",
            "choice_id",
            "request_id",
        })

        if payload is None:
            return error("invalid_submission", 400)

        try:
            receipt = quiz.submit(
                session_id=session_id,
                item_id=payload["item_id"],
                choice_id=payload["choice_id"],
                request_id=payload["request_id"],
            )

            offer = quiz.current_offer(session_id)

        except SessionNotFound:
            return error("unknown_session", 404)

        except ItemBankMismatch:
            return error("item_bank_mismatch", 409)

        except ResponseConflict as exc:
            if (
                str(exc)
                == "Assistance decision or delivery is pending"
            ):
                return error("assistance_pending", 409)

            return error("response_conflict", 409)

        except ValueError:
            return error("invalid_submission", 400)

        pending = (
            offer is not None
            and offer.status in ("offered", "accepted")
        )

        return jsonify({
            "accepted": True,
            "replayed": receipt.replayed,
            "complete": receipt.completed,
            "feedback": "withheld",
            "next_action": (
                "assistance_pending"
                if pending else "no_offer"
            ),
        })

    @app.get(
        f"{PREFIX}/sessions/<session_id>/assistance"
    )
    def assistance(session_id):
        try:
            offer = quiz.current_offer(session_id)

        except SessionNotFound:
            return error("unknown_session", 404)

        except ItemBankMismatch:
            return error("item_bank_mismatch", 409)

        return jsonify({
            "offer": asdict(offer) if offer else None
        })

    @app.post(
        f"{PREFIX}/sessions/<session_id>"
        "/assistance/decision"
    )
    def assistance_decision(session_id):
        payload = exact_json({
            "source_position",
            "accept",
        })

        if payload is None:
            return error("invalid_assistance_request", 400)

        source = payload["source_position"]
        accept = payload["accept"]

        if (
            type(source) is not int
            or source < 0
            or type(accept) is not bool
        ):
            return error("invalid_assistance_request", 400)

        try:
            offer = quiz.decide(
                session_id=session_id,
                source_position=source,
                accept=accept,
            )

        except SessionNotFound:
            return error("unknown_session", 404)

        except ItemBankMismatch:
            return error("item_bank_mismatch", 409)

        except AssistanceConflict:
            return error("assistance_conflict", 409)

        return jsonify({"offer": asdict(offer)})

    @app.post(
        f"{PREFIX}/sessions/<session_id>"
        "/assistance/delivery"
    )
    def assistance_delivery(session_id):
        payload = exact_json({"source_position"})

        if payload is None:
            return error("invalid_assistance_request", 400)

        source = payload["source_position"]

        if type(source) is not int or source < 0:
            return error("invalid_assistance_request", 400)

        try:
            offer = quiz.deliver(
                session_id=session_id,
                source_position=source,
            )

        except SessionNotFound:
            return error("unknown_session", 404)

        except ItemBankMismatch:
            return error("item_bank_mismatch", 409)

        except AssistanceConflict:
            return error("assistance_conflict", 409)

        return jsonify({"offer": asdict(offer)})

    return app
