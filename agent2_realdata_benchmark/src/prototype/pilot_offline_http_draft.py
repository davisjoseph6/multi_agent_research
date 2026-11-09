"""Flask test_client ONLY bridge to synthetic three-arm pilot state machine.

This file is not imported by the real RCTCandidateEngine, application WSGI
factory, operator demo, or VPS.  Do NOT expose it on any network port, attach
real students, use real consent, or interpret this as research authorization.

The only public constructor returns a Flask TEST CLIENT, never a WSGI app.
It provides no participant creation or session-start HTTP endpoints.
All identities and visit starts must be generated OFFLINE by test fixtures.
HTTP request timestamps are fixture data, not trusted production timestamps.
"""
from __future__ import annotations

from datetime import datetime
import re

from flask import Flask, jsonify, request

from .pilot_session_flow_draft import PilotSequenceError
from .pilot_three_arm_store_draft import SyntheticThreeArmPilotStore

PID_PATTERN = re.compile(r"SYN_PILOT_[0-9a-f]{32}\Z")


def create_offline_test_client(store: SyntheticThreeArmPilotStore):
    """Return an in-process Flask test client, not a deployable Flask app."""
    if not isinstance(store, SyntheticThreeArmPilotStore):
        raise TypeError("only an isolated synthetic three-arm store is supported")

    app = Flask("synthetic_pilot_test_client_only")
    app.config.update(TESTING=True, MAX_CONTENT_LENGTH=4096)

    @app.before_request
    def restrict_to_test_environment():
        # These controls are defense-in-depth for an in-process test harness,
        # NOT authentication or suitable network deployment protection.
        if request.host != "localhost" or request.remote_addr not in ("127.0.0.1", "::1"):
            return jsonify(error="not a network service"), 403
        if request.headers.get("Origin") is not None:
            return jsonify(error="browser-origin requests are not supported"), 403

    @app.after_request
    def no_store(response):
        response.headers.update({
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-Synthetic-Only": "1",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        })
        return response

    @app.errorhandler(PilotSequenceError)
    def rejected(error):
        return jsonify(error=str(error), synthetic_only=True), 409

    @app.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error), synthetic_only=True), 422

    @app.errorhandler(413)
    def oversized(_):
        return jsonify(error="test request too large", synthetic_only=True), 413

    def data(expected: tuple[str, ...]) -> dict:
        body = request.get_json(silent=True)
        if type(body) is not dict or set(body) != set(expected):
            raise PilotSequenceError("unexpected synthetic request fields")
        if type(body.get("pid")) is not str or PID_PATTERN.fullmatch(body["pid"]) is None:
            raise PilotSequenceError("synthetic participant ID required")
        return body

    def when(value: object) -> datetime:
        if type(value) is not str or len(value) > 50:
            raise PilotSequenceError("timezone-aware ISO timestamp required")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise PilotSequenceError("invalid synthetic ISO timestamp") from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise PilotSequenceError("timezone-aware timestamp required")
        return parsed

    @app.get("/_offline/health")
    def health():
        return jsonify(synthetic_only=True, human_enrollment_authorized=False,
                       http_test_client_only=True)

    @app.post("/_offline/next")
    def next_action():
        body = data(("pid", "at"))
        return jsonify(store.next_action(body["pid"], at=when(body["at"])))

    @app.post("/_offline/rendered")
    def rendered():
        body = data(("pid", "action_id", "at"))
        if type(body["action_id"]) is not str:
            raise PilotSequenceError("action_id must be text")
        return jsonify(store.mark_rendered(body["pid"], body["action_id"],
                                          at=when(body["at"])))

    @app.post("/_offline/act")
    def act():
        body = data(("pid", "action_id", "request_id", "response", "at"))
        if (type(body["action_id"]) is not str or
                type(body["request_id"]) is not str or
                type(body["response"]) is not dict):
            raise PilotSequenceError("action, request and response types invalid")
        return jsonify(store.submit(
            body["pid"], body["action_id"], body["request_id"],
            body["response"], at=when(body["at"]),
        ))

    # No enrollment, start visit, consent, export, full-score, admin,
    # operator or WSGI server endpoint is implemented.
    return app.test_client()
