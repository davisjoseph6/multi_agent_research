"""Participant interface for the isolated RCT candidate; no admin HTTP routes."""
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.middleware.proxy_fix import ProxyFix

from .study_v2_runtime import ProtocolError


def create_app(engine, *, allowed_hosts=None, behind_one_local_tls_proxy=None):
    root = Path(__file__).resolve().parent
    app = Flask(__name__, static_folder=None, template_folder=str(root / "templates"))
    app.config["MAX_CONTENT_LENGTH"] = 16384
    app.extensions["rct_engine"] = engine
    deployment = engine.policy["deployment"]
    if allowed_hosts is not None and list(allowed_hosts) != deployment["allowed_hosts"]:
        raise ValueError("host configuration differs from frozen candidate")
    if behind_one_local_tls_proxy is not None and behind_one_local_tls_proxy != deployment["behind_one_local_tls_proxy"]:
        raise ValueError("proxy configuration differs from frozen candidate")
    allowed_hosts = deployment["allowed_hosts"]
    behind_one_local_tls_proxy = deployment["behind_one_local_tls_proxy"]
    if engine.mode == "rehearsal" and behind_one_local_tls_proxy:
        raise ValueError("rehearsal must not trust proxy headers")
    if engine.mode == "operator_demo" and not behind_one_local_tls_proxy:
        raise ValueError("operator demo must use its one trusted TLS proxy")
    if behind_one_local_tls_proxy:
        # Use only with the documented loopback-bound WSGI server and one trusted proxy.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    allowed_hosts = set(allowed_hosts)
    if not allowed_hosts:
        raise ValueError("explicit host allowlist required")

    @app.before_request
    def guard():
        host = urlsplit("//" + request.host).hostname
        if host not in allowed_hosts:
            return jsonify(error="unexpected host"), 403
        if engine.mode == "rehearsal" and request.remote_addr not in ("127.0.0.1", "::1"):
            return jsonify(error="rehearsal is local only"), 403
        if engine.mode == "operator_demo":
            # ProxyFix changes REMOTE_ADDR to the visitor address. Its stored
            # original must be the SAME-HOST loopback reverse proxy.
            original = request.environ.get("werkzeug.proxy_fix.orig", {})
            if original.get("REMOTE_ADDR") not in ("127.0.0.1", "::1"):
                return jsonify(error="trusted local proxy required"), 403
        if engine.mode in ("live", "operator_demo") and not request.is_secure:
            return jsonify(error="HTTPS required"), 403
        origin = request.headers.get("Origin")
        if origin and origin != request.host_url.rstrip("/"):
            return jsonify(error="cross-origin requests are forbidden"), 403

    @app.after_request
    def headers(response):
        response.headers.update({
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        })
        if engine.mode in ("live", "operator_demo"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if engine.mode == "operator_demo":
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    @app.errorhandler(ProtocolError)
    def rejected(error):
        return jsonify(error=str(error)), 409

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error="request too large"), 413

    def body(expected):
        supplied = request.get_json(silent=True)
        if not isinstance(supplied, dict) or set(supplied) != set(expected):
            raise ProtocolError("unexpected request fields")
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise ProtocolError("invitation required")
        return authorization[7:], supplied

    @app.get("/")
    def page():
        return render_template("rct_candidate.html", rehearsal=engine.mode == "rehearsal",
                               operator_demo=engine.mode == "operator_demo")

    @app.get("/app.js")
    def javascript():
        return send_file(root / "static/rct_candidate.js", mimetype="text/javascript")

    @app.get("/app.css")
    def stylesheet():
        return send_file(root / "static/rct_candidate.css", mimetype="text/css")

    @app.post("/api/rct/information")
    def information():
        token, _ = body(())
        return jsonify(engine.information(token))

    @app.post("/api/rct/enroll")
    def enroll():
        if engine.mode == "operator_demo":
            # Operator seeds synthetic participants OFFLINE before opening
            # restricted staging. The HTTP endpoint must never recruit.
            return jsonify(error="operator demonstration has no public enrollment"), 403
        token, data = body(("agreed", "information_version"))
        return jsonify(engine.enroll(token, **data))

    @app.post("/api/rct/next")
    def next_action():
        token, _ = body(())
        return jsonify(engine.next_action(token))

    @app.post("/api/rct/rendered")
    def rendered():
        token, data = body(("action_id",))
        return jsonify(engine.rendered(token, **data))

    @app.post("/api/rct/act")
    def act():
        token, data = body(("request_id", "action_id", "response"))
        return jsonify(engine.act(token, **data))

    @app.post("/api/rct/withdraw")
    def withdraw():
        token, _ = body(())
        return jsonify(engine.withdraw(token))

    return app
