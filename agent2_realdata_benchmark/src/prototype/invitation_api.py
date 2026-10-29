"""Invitation-protected, loopback-only experimental API.

Development and synthetic participants only.

Not an approved RCT deployment. Invitations are bearer
credentials, not verified real-world identities.

Unlike experimental_api.py, this application does not
register unauthenticated trial-development endpoints.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3

from contextlib import closing
from dataclasses import asdict
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, request

from src.prototype.assistance_store import (
    AssistanceConflict,
)
from src.prototype.experimental_session_store import (
    SQLiteExperimentalQuizRepository,
)
from src.prototype.invitation_enrollment import (
    InvalidInvitation,
    InvitationIntegrityError,
    SQLiteInvitationEnrollmentStore,
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


PREFIX = "/api/v1/trial-invite"

TOKEN_PATTERN = re.compile(
    r"inv1_[0-9a-f]{64}"
)


def create_invitation_app(
    database_path: str | Path,
    *,
    threshold: float = 0.30,
    block_sizes: tuple[int, ...] = (6, 9),
) -> Flask:
    """Create an isolated, invitation-protected local API."""

    database = Path(database_path).expanduser().resolve()

    enrollment = SQLiteInvitationEnrollmentStore(
        database,
        threshold=threshold,
        block_sizes=block_sizes,
    )

    quiz = SQLiteExperimentalQuizRepository(
        database,
        items=INSTRUCTIONAL_DEMO_ITEMS,
        bank_version=INSTRUCTIONAL_DEMO_VERSION,
        threshold=threshold,
    )

    # No automatically registered static-file route.
    # A separate authenticated browser will be designed later.
    app = Flask(__name__, static_folder=None)

    app.extensions["invitation_enrollment"] = enrollment
    app.extensions["invitation_quiz"] = quiz

    def error(code: str, status: int):
        return jsonify({"error": code}), status

    def exact_json(fields):
        payload = request.get_json(silent=True)

        if (
            type(payload) is not dict
            or set(payload) != set(fields)
        ):
            return None

        return payload

    def bearer_token() -> str | None:
        """Extract a strictly formatted invitation credential."""

        header = request.headers.get(
            "Authorization", ""
        )

        parts = header.split(" ", 1)

        if (
            len(parts) != 2
            or parts[0] != "Bearer"
            or TOKEN_PATTERN.fullmatch(parts[1]) is None
        ):
            return None

        return parts[1]

    def authorized_for_session(
        token: str,
        session_id: str,
    ) -> bool:
        """Read-only verification of token/session ownership.

        This does not allocate, enroll, or mutate state.
        """

        digest = hashlib.sha256(
            token.encode("ascii")
        ).hexdigest()

        uri = database.as_uri() + "?mode=ro"

        with closing(
            sqlite3.connect(uri, uri=True)
        ) as connection:

            connection.execute("PRAGMA query_only=ON")

            match = connection.execute(
                """
                SELECT 1

                FROM trial_invitations AS invitation

                JOIN trial_allocations AS allocation
                  ON allocation.participant_id =
                     invitation.participant_id

                JOIN experimental_session_policies
                     AS binding
                  ON binding.participant_id =
                     allocation.participant_id

                JOIN sessions AS session
                  ON session.session_id =
                     binding.session_id

                WHERE invitation.token_digest = ?
                  AND binding.session_id = ?
                  AND binding.policy_mode =
                      allocation.policy_mode
                """,
                (digest, session_id),
            ).fetchone()

        return match is not None

    def protect_session(handler):
        """Authorize before reading or modifying any session."""

        @wraps(handler)
        def protected(session_id, *args, **kwargs):

            token = bearer_token()

            if token is None:
                return error("authorization_required", 401)

            if not authorized_for_session(
                token, session_id
            ):
                return error("session_access_denied", 403)

            return handler(
                session_id, *args, **kwargs
            )

        return protected

    @app.before_request
    def require_local_connection():
        """Defense in depth; not real participant identity."""

        try:
            hostname = urlsplit(
                "//" + request.host
            ).hostname
        except ValueError:
            hostname = None

        if (
            request.remote_addr not in (
                "127.0.0.1", "::1"
            )
            or hostname not in (
                "localhost", "127.0.0.1", "::1"
            )
        ):
            return error(
                "development_local_only", 403
            )

        return None

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
            "mode": "invitation_development_only",
        })

    @app.post(f"{PREFIX}/enroll")
    def enroll():
        """Only a valid invitation can create a session."""

        token = bearer_token()

        if token is None:
            return error("authorization_required", 401)

        try:
            receipt = enrollment.redeem_invitation(
                token
            )

        except InvalidInvitation:
            return error("invalid_invitation", 401)

        except InvitationIntegrityError:
            return error("enrollment_integrity_error", 409)

        return jsonify({
            "session_id": receipt.session_id,
            "replayed": receipt.replayed,
            "mode": "invitation_development_only",
        }), (200 if receipt.replayed else 201)

    @app.get(
        f"{PREFIX}/sessions/<session_id>/question"
    )
    @protect_session
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
                if offer is not None else None
            ),
        })

    @app.post(
        f"{PREFIX}/sessions/<session_id>/responses"
    )
    @protect_session
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
            if str(exc) == (
                "Assistance decision or delivery is pending"
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
    @protect_session
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
    @protect_session
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
    @protect_session
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
