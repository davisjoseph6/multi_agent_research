"""LOOPBACK-ONLY SYNTHETIC DEVELOPMENT browser, not for human recruitment.

No personal identifiers, consent collection, production authentication,
TLS/CSRF production hardening, or real learning materials are provided.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import hmac
import re
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request, send_file

from .study_v2 import synthetic_bank
from .study_v3_pomcp import EightConceptPOMCP
from .study_v3_runtime import SyntheticPOMCPProtocolEngine
from .study_v2_runtime import ProtocolError

VALID_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
PID = re.compile(r"^SYN_[A-Za-z0-9_-]{3,50}$")


def create_synthetic_browser_app(database, *, token: str, simulations: int = 64):
    if not isinstance(token, str) or len(token) < 24:
        raise ValueError("provide an unpredictable private development token")
    secret_hash = sha256(token.encode()).digest()
    directory = Path(__file__).resolve().parent
    app = Flask(__name__, static_folder=None, template_folder=str(directory / "templates"))
    engine = SyntheticPOMCPProtocolEngine(
        database, synthetic_bank(), planner=EightConceptPOMCP(simulations=simulations))
    app.extensions["synthetic_v3_engine"] = engine

    @app.before_request
    def loopback_guard():
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            return jsonify(error="local development only"), 403
        if urlsplit(f"//{request.host}").hostname not in {"127.0.0.1", "localhost", "::1"}:
            return jsonify(error="unexpected host"), 403
        if request.path.startswith("/api/v3/"):
            credential = request.headers.get("Authorization", "")
            if not credential.startswith("Bearer "):
                return jsonify(error="development token required"), 401
            supplied = credential[len("Bearer "):]
            if not hmac.compare_digest(sha256(supplied.encode()).digest(), secret_hash):
                return jsonify(error="invalid development token"), 401

    @app.after_request
    def disable_caching(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/trial-v3")
    def browser():
        response = app.make_response(render_template("study_v3_demo.html"))
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'")
        return response

    @app.get("/trial-v3/app.js")
    def js():
        return send_file(directory / "static" / "study_v3_demo.js", mimetype="text/javascript")

    @app.get("/trial-v3/base.css")
    def css():
        return send_file(directory / "static" / "study_v3_demo.css", mimetype="text/css")

    def posted_pid():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise ProtocolError("expected a JSON object")
        pid = body.get("participant_id")
        if not isinstance(pid,str) or not PID.fullmatch(pid):
            raise ProtocolError("use synthetic IDs beginning SYN_ only")
        return pid, body

    @app.errorhandler(ProtocolError)
    @app.errorhandler(ValueError)
    def bad_request(error):
        return jsonify(error=str(error)), 400

    @app.post("/api/v3/enroll")
    def enroll():
        pid, body = posted_pid()
        arm = body.get("arm")
        if arm not in ("A","B","C"):
            raise ProtocolError("invalid synthetic arm")
        created = engine.enroll(pid,arm)
        return jsonify(created=created, synthetic_only=True), (201 if created else 200)

    @app.post("/api/v3/next")
    def next_action():
        pid, _ = posted_pid()
        return jsonify({**engine.next_action(pid), "synthetic_only": True})

    @app.post("/api/v3/act")
    def act():
        pid, body = posted_pid()
        request_id = body.get("request_id")
        action = body.get("response")
        if not isinstance(request_id, str) or not isinstance(action,dict):
            raise ProtocolError("request_id and response object required")
        return jsonify({**engine.act(pid, request_id, action), "synthetic_only": True})

    @app.post("/api/v3/status")
    def status():
        pid, _ = posted_pid()
        snapshot = engine.snapshot(pid)
        return jsonify(synthetic_only=True, arm=snapshot["arm"], stage=snapshot["stage"],
                       session=snapshot["session"], index=snapshot["index"],
                       resources_spent=snapshot["recovery"].get("pomcp_resource_spent",0))

    return app
