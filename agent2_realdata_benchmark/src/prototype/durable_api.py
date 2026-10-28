"""Local-only durable Flask quiz API.

SQLite is the authoritative response store.
BKT is reconstructed from committed practice history.
POMCP is shadow-only and never delivers assistance.

Not authorized for collecting real participant data.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from src.prototype.assistance_store import AssistanceConflict
from src.prototype.gated_assistance_store import (
    SQLiteFixedSummaryQuizRepository,
)
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
    fixed_summary: bool = False,
) -> Flask:
    """Create an isolated, file-backed development API."""

    if type(fixed_summary) is not bool:
        raise TypeError("fixed_summary must be boolean")

    repository_class = (
        SQLiteFixedSummaryQuizRepository
        if fixed_summary
        else SQLiteQuizRepository
    )

    repository = repository_class(
        database_path,
        items=items,
        bank_version=bank_version,
    )

    api_mode = (
        "fixed_summary_demo_only"
        if fixed_summary
        else "local_demo_only"
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
            "mode": api_mode,
        })

    @app.get("/demo")
    def local_browser_demo():
        if fixed_summary:
            return error(
                "fixed_summary_browser_not_yet_supported",
                409,
            )

        response = app.make_response(
            render_template("durable_quiz.html")
        )

        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'none'; "
            "frame-ancestors 'none'"
        )

        return response

    @app.post("/api/v1/durable/sessions")
    def create_session():
        session_id = repository.create_session()

        return jsonify({
            "session_id": session_id,
            "bank_version": bank_version,
            "mode": api_mode,
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

        offer = (
            repository.current_offer(session_id)
            if fixed_summary and not progress.completed
            else None
        )

        pending = (
            offer is not None
            and offer.status in ("offered", "accepted")
        )

        response = {
            "complete": progress.completed,
            "position": progress.position,
            "bank_version": progress.bank_version,
            "question": (
                None if pending else progress.current_question
            ),
        }

        if fixed_summary:
            response["assistance_pending"] = pending
            response["assistance"] = (
                {
                    "source_position": offer.source_position,
                    "target_position": offer.target_position,
                    "resource_id": offer.resource_id,
                    "title": offer.title,
                    "status": offer.status,
                }
                if offer is not None
                else None
            )

        return jsonify(response)

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
        except ResponseConflict as exc:
            if (
                fixed_summary
                and str(exc)
                == "Assistance decision or delivery is pending"
            ):
                return error("assistance_pending", 409)

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

        next_action = "no_offer"

        if fixed_summary:
            offer = repository.current_offer(session_id)

            if (
                offer is not None
                and offer.status in ("offered", "accepted")
            ):
                next_action = "assistance_pending"

        # Correctness, BKT beliefs, and simulated planner
        # actions must never be included in this response.
        return jsonify({
            "accepted": True,
            "replayed": receipt.replayed,
            "complete": receipt.completed,
            "feedback": "withheld",
            "next_action": next_action,
        })


    # Only fixed-summary mode registers assistance routes.
    if fixed_summary:

        def assistance_error(exc):
            if isinstance(exc, SessionNotFound):
                return error("unknown_session", 404)
            if isinstance(exc, ItemBankMismatch):
                return error("item_bank_mismatch", 409)
            if isinstance(exc, AssistanceConflict):
                return error("assistance_conflict", 409)
            return error("invalid_assistance_request", 400)

        @app.get(
            "/api/v1/durable/sessions/<session_id>/assistance"
        )
        def current_assistance(session_id: str):
            try:
                offer = repository.current_offer(session_id)
            except (SessionNotFound, ItemBankMismatch) as exc:
                return assistance_error(exc)
            return jsonify({"offer": asdict(offer) if offer else None})

        @app.post(
            "/api/v1/durable/sessions/<session_id>"
            "/assistance/decision"
        )
        def assistance_decision(session_id: str):
            payload = request.get_json(silent=True)
            if (
                not isinstance(payload, dict)
                or set(payload) != {"source_position", "accept"}
            ):
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
                offer = repository.decide(
                    session_id=session_id,
                    source_position=source,
                    accept=accept,
                )
            except (
                SessionNotFound, ItemBankMismatch, AssistanceConflict
            ) as exc:
                return assistance_error(exc)
            return jsonify({"offer": asdict(offer)})

        @app.post(
            "/api/v1/durable/sessions/<session_id>"
            "/assistance/delivery"
        )
        def assistance_delivery(session_id: str):
            payload = request.get_json(silent=True)
            if (
                not isinstance(payload, dict)
                or set(payload) != {"source_position"}
            ):
                return error("invalid_assistance_request", 400)

            source = payload["source_position"]
            if type(source) is not int or source < 0:
                return error("invalid_assistance_request", 400)

            try:
                offer = repository.deliver(
                    session_id=session_id,
                    source_position=source,
                )
            except (
                SessionNotFound, ItemBankMismatch, AssistanceConflict
            ) as exc:
                return assistance_error(exc)
            return jsonify({"offer": asdict(offer)})

    return app
