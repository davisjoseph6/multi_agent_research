"""Explicitly nonproduction browser PREVIEW of fictional three-arm pilot journeys.

The only runner binds 127.0.0.1, has no enrollment route, and creates three
synthetic records offline. The browser cannot authorize or start visits.
The UI and action endpoint are exclusively for local manual software rehearsal.

This is NOT imported by the existing RCT candidate or its WSGI factory.
CSRF protection, loopback checks and nonce are defense in depth, NOT suitable
for live participant authentication. Never expose through a public reverse proxy.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from pathlib import Path
import secrets

from flask import Flask, jsonify, render_template, request, send_file

from .pilot_session_flow_draft import PilotSequenceError
from .pilot_three_arm_store_draft import SyntheticThreeArmPilotStore

SYNTHETIC_EPOCH = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
ARM_VALUES = ("A", "B", "C")


def ensure_three_fictional_records(store: SyntheticThreeArmPilotStore) -> dict[str, str]:
    """Seed all three fictional arms, but NEVER silently change a populated DB.

    Only a fresh, empty synthetic preview DB is seeded. Existing DB must
    contain precisely one synthetic record per arm and no extra records.
    """
    with store._transaction() as db:
        rows = db.execute(
            "SELECT arm,pid FROM pilot_three_arm_people ORDER BY arm"
        ).fetchall()
        total = db.execute("SELECT COUNT(*) FROM pilot_people").fetchone()[0]
    if not rows and total == 0:
        for arm in ARM_VALUES:
            pid = store.new_synthetic_participant(arm=arm, at=SYNTHETIC_EPOCH)
            store.start_supervised_visit(
                pid, visit=1, at=SYNTHETIC_EPOCH,
                offline_staff_authorized=True,
                synthetic_release_authorized=True,
            )
        with store._transaction() as db:
            rows = db.execute(
                "SELECT arm,pid FROM pilot_three_arm_people ORDER BY arm"
            ).fetchall()
            total = db.execute("SELECT COUNT(*) FROM pilot_people").fetchone()[0]
    if len(rows) != 3 or total != 3 or [row["arm"] for row in rows] != list(ARM_VALUES):
        raise PilotSequenceError(
            "preview DB must have exactly one fictional participant per arm"
        )
    for row in rows:
        if not row["pid"].startswith("SYN_PILOT_"):
            raise PilotSequenceError("nonfictional records forbidden")
    return {row["arm"]: row["pid"] for row in rows}


def advance_fictional_visit(
    store: SyntheticThreeArmPilotStore, arm: str,
) -> dict:
    """OFFLINE CLI only: advance fictional time by four days per visit.

    No HTTP route invokes this function. There is no staff authentication or
    recruitment, just repeatable fixture state for local demonstration.
    """
    if arm not in ARM_VALUES:
        raise PilotSequenceError("select only fictional Arm A, B or C")
    pids = ensure_three_fictional_records(store)
    pid = pids[arm]
    state = store.snapshot(pid)
    if state["stage"] != "awaiting_visit" or state["session"] not in (1, 2):
        raise PilotSequenceError("finish previous fictional session before advancing")
    next_visit = state["session"] + 1
    at = SYNTHETIC_EPOCH + timedelta(days=4 * (next_visit - 1))
    return store.start_supervised_visit(
        pid, visit=next_visit, at=at,
        offline_staff_authorized=True, synthetic_release_authorized=True,
    )


def create_fictional_preview_app(
    store: SyntheticThreeArmPilotStore, *, port: int = 8765,
) -> Flask:
    """Create local-only preview WSGI app, for the loopback-only runner.

    No external WSGI entrypoint is supplied. This is test/demo code, never
    a human-study or production server.
    """
    if not isinstance(store, SyntheticThreeArmPilotStore):
        raise TypeError("fictional three-arm store required")
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("unprivileged loopback port required")
    participants = ensure_three_fictional_records(store)
    nonce = secrets.token_urlsafe(32)
    root = Path(__file__).resolve().parent
    app = Flask(
        "fictional_pilot_browser_preview",
        static_folder=None, template_folder=str(root / "templates"),
    )
    app.config.update(
        MAX_CONTENT_LENGTH=4096, DEBUG=False, TESTING=False,
    )

    @app.before_request
    def only_loopback():
        # Both checks prevent accidental public service, but are not
        # standalone authentication. Runner MUST bind to 127.0.0.1.
        if request.remote_addr not in ("127.0.0.1", "::1"):
            return jsonify(error="fictional preview is loopback-only"), 403
        if request.host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            return jsonify(error="unexpected preview host"), 403
        if request.method == "POST":
            if request.headers.get("Origin") != request.host_url.rstrip("/"):
                return jsonify(error="same-origin fictional requests only"), 403
            supplied = request.headers.get("X-Preview-Nonce", "")
            if not compare_digest(supplied, nonce):
                return jsonify(error="preview form nonce required"), 403
            if request.mimetype != "application/json":
                return jsonify(error="JSON body required"), 415

    @app.after_request
    def secure_headers(response):
        response.headers.update({
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": "noindex, nofollow",
            "X-Synthetic-Only": "1",
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'none'; object-src 'none'; "
                "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
            ),
        })
        return response

    @app.errorhandler(PilotSequenceError)
    def conflict(error):
        return jsonify(error=str(error), synthetic_only=True), 409

    @app.errorhandler(ValueError)
    def bad_value(error):
        return jsonify(error=str(error), synthetic_only=True), 422

    def participant():
        supplied = request.get_json(silent=True)
        if type(supplied) is not dict:
            raise PilotSequenceError("expected JSON object")
        arm = supplied.get("arm")
        if type(arm) is not str or arm not in participants:
            raise PilotSequenceError("fictional Arm A/B/C required")
        return participants[arm], supplied

    def fictional_time(pid: str) -> datetime:
        snapshot = store.snapshot(pid)
        if snapshot["session"] not in (1, 2, 3):
            raise PilotSequenceError("synthetic session has not started")
        # Server-owned virtual time; browser cannot supply a clock value.
        # Relative order is stable across refresh/retry. At least one minute
        # per completed action; visit starts remain four virtual days apart.
        return (
            SYNTHETIC_EPOCH
            + timedelta(days=4 * (snapshot["session"] - 1))
            + timedelta(minutes=snapshot["completed_actions"] + 1)
        )

    @app.get("/")
    def index():
        return render_template(
            "pilot_fictional_preview.html", preview_nonce=nonce
        )

    @app.get("/preview.js")
    def javascript():
        return send_file(
            root / "static/pilot_fictional_preview.js",
            mimetype="text/javascript",
        )

    @app.get("/preview.css")
    def stylesheet():
        return send_file(
            root / "static/pilot_fictional_preview.css",
            mimetype="text/css",
        )

    @app.post("/preview/api/status")
    def status():
        pid, supplied = participant()
        if set(supplied) != {"arm"}:
            raise PilotSequenceError("unexpected fields in status request")
        snapshot = store.snapshot(pid)
        return jsonify(
            arm=supplied["arm"], stage=snapshot["stage"],
            session=snapshot["session"], index=snapshot["index"],
            completed_actions=snapshot["completed_actions"],
            visits_finished=snapshot["visits_finished"],
            fictional_only=True, human_enrollment_authorized=False,
        )

    @app.post("/preview/api/next")
    def next_action():
        pid, supplied = participant()
        if set(supplied) != {"arm"}:
            raise PilotSequenceError("unexpected fields in next request")
        return jsonify(store.next_action(pid, at=fictional_time(pid)))

    @app.post("/preview/api/rendered")
    def rendered():
        pid, supplied = participant()
        if set(supplied) != {"arm", "action_id"} or \
                type(supplied["action_id"]) is not str:
            raise PilotSequenceError("unexpected render request")
        return jsonify(store.mark_rendered(
            pid, supplied["action_id"], at=fictional_time(pid),
        ))

    @app.post("/preview/api/act")
    def act():
        pid, supplied = participant()
        if set(supplied) != {
            "arm", "action_id", "request_id", "response"
        } or (type(supplied["action_id"]) is not str
              or type(supplied["request_id"]) is not str
              or type(supplied["response"]) is not dict):
            raise PilotSequenceError("unexpected action submission")
        return jsonify(store.submit(
            pid, supplied["action_id"], supplied["request_id"],
            supplied["response"], at=fictional_time(pid),
        ))

    # NO enrollment, start visit, identity, consent, admin, export or backup
    # routes. The only way to advance fictional visits is the OFFLINE CLI.
    return app
