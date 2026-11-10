"""SSH-tunnel-only, synthetic unified-SQLite browser rehearsal.

This is NOT a human RCT: it has no real credentials/identity, recruitment,
consent form, student database, staff authorization, or institutional release.
It intentionally never exposes the randomized treatment arm to the browser.
An offline operator shell command starts subsequent fictional visits.

Production rule: NEVER proxy or bind this app publicly. The launcher binds
only 127.0.0.1. Headers/nonce/loopback checks provide defense in depth but
are NOT a replacement for authenticated participant web sessions.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from pathlib import Path
import secrets

from flask import Flask, jsonify, render_template, request, send_file

from .pilot_admission_controls_draft import AdmissionDenied
from .pilot_session_flow_draft import PilotSequenceError
from .pilot_unified_sqlite_synthetic import (
    UnifiedSyntheticStudyStore, UnifiedSyntheticError,
)

SYNTHETIC_EPOCH = datetime(2026, 11, 20, 9, tzinfo=timezone.utc)
FIXTURE_IDS = ("F1", "F2", "F3")


class FixtureClock:
    """A private process-local clock controlled only by the offline CLI."""

    def __init__(self):
        self.value = SYNTHETIC_EPOCH

    def __call__(self):
        return self.value


def ensure_unified_fictional_roster(
    study: UnifiedSyntheticStudyStore, operator_key: bytes,
    *, screening_version: str, information_sha256: str,
) -> dict[str, str]:
    """Seed exactly three randomly allocated fixture records, once only.

    An interrupted partial seed is rejected rather than silently rebuilt;
    use a separate new fictional database to restart a failed setup.
    """
    study.admission._require(operator_key, "operator")
    with study.admission._transaction() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS unified_demo_roster ("
            "fixture TEXT PRIMARY KEY CHECK (fixture IN ('F1','F2','F3')),"
            "admission_pid TEXT NOT NULL UNIQUE "
            "REFERENCES admission_people(pid))"
        )
        rows = db.execute(
            "SELECT fixture,admission_pid FROM unified_demo_roster ORDER BY fixture"
        ).fetchall()
        admissions = db.execute(
            "SELECT COUNT(*) FROM admission_people"
        ).fetchone()[0]
        learners = db.execute(
            "SELECT COUNT(*) FROM pilot_people"
        ).fetchone()[0]
    if not rows and not admissions and not learners:
        for fixture in FIXTURE_IDS:
            invitation = study.issue_invitation(operator_key)
            pid = invitation["synthetic_pid"]
            study.screen(
                operator_key, pid, eligible=True,
                screening_version=screening_version,
            )
            result = study.consent_and_create(
                invitation["private_invitation"],
                agreed=True, information_sha256=information_sha256,
            )
            if not result["created"]:
                raise UnifiedSyntheticError("fictional consent did not create learner")
            with study.admission._transaction() as db:
                db.execute(
                    "INSERT INTO unified_demo_roster(fixture,admission_pid)"
                    " VALUES(?,?)", (fixture, pid),
                )
            study.start_visit(operator_key, pid, 1)
        with study.admission._transaction() as db:
            rows = db.execute(
                "SELECT fixture,admission_pid "
                "FROM unified_demo_roster ORDER BY fixture"
            ).fetchall()
            admissions = db.execute(
                "SELECT COUNT(*) FROM admission_people"
            ).fetchone()[0]
            learners = db.execute(
                "SELECT COUNT(*) FROM pilot_people"
            ).fetchone()[0]
    if (len(rows) != 3 or admissions != 3 or learners != 3
            or tuple(row["fixture"] for row in rows) != FIXTURE_IDS
            or any(not row["admission_pid"].startswith("SYN_ADMISSION_")
                   for row in rows)):
        raise UnifiedSyntheticError(
            "expected exactly three already-consented fictional records; "
            "refusing partial/external data"
        )
    for row in rows:
        study.operator_lookup(operator_key, row["admission_pid"])
    return {row["fixture"]: row["admission_pid"] for row in rows}


def _offline_finish_if_needed(
    study: UnifiedSyntheticStudyStore, operator_key: bytes,
    pid: str, visit: int, clock: FixtureClock,
) -> None:
    with study.admission._transaction() as db:
        row = db.execute(
            "SELECT finished_at FROM admission_visits "
            "WHERE pid=? AND visit=?", (pid, visit),
        ).fetchone()
    if row is None:
        raise UnifiedSyntheticError("fictional visit attendance is missing")
    if row["finished_at"] is None:
        clock.value = (
            SYNTHETIC_EPOCH + timedelta(days=4 * (visit - 1), minutes=70)
        )
        study.finish_visit(operator_key, pid, visit)


def advance_unified_fictional_visit(
    study: UnifiedSyntheticStudyStore, operator_key: bytes,
    fixture: str, roster: dict[str, str], clock: FixtureClock,
    *, finish_final: bool = False,
) -> dict:
    """Only the separate operator CLI calls this; never a Flask route."""
    if fixture not in FIXTURE_IDS or fixture not in roster:
        raise UnifiedSyntheticError("unknown fictional fixture")
    pid = roster[fixture]
    learning_pid, _hidden_arm = study.operator_lookup(operator_key, pid)
    state = study.learning.snapshot(learning_pid)
    if finish_final:
        if state["stage"] != "complete" or state["session"] != 3:
            raise UnifiedSyntheticError("all three fictional learning visits required")
        _offline_finish_if_needed(study, operator_key, pid, 3, clock)
        return {"fixture": fixture, "visits_finished": 3,
                "synthetic_only": True, "human_enrollment_authorized": False}
    if state["stage"] != "awaiting_visit" or state["session"] not in (1, 2):
        raise UnifiedSyntheticError("complete this fictional visit first")
    finished = state["session"]
    _offline_finish_if_needed(study, operator_key, pid, finished, clock)
    next_visit = finished + 1
    clock.value = SYNTHETIC_EPOCH + timedelta(days=4 * (next_visit - 1))
    study.start_visit(operator_key, pid, next_visit)
    return {"fixture": fixture, "visit_started": next_visit,
            "synthetic_only": True, "human_enrollment_authorized": False}


def create_unified_fictional_browser_app(
    study: UnifiedSyntheticStudyStore, operator_key: bytes,
    roster: dict[str, str], *, port: int = 8767,
) -> Flask:
    """No enrollment/consent/visit-start/withdrawal/assignment HTTP route."""
    if not isinstance(study, UnifiedSyntheticStudyStore):
        raise TypeError("unified synthetic study required")
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("unprivileged loopback port required")
    study.admission._require(operator_key, "operator")
    if set(roster) != set(FIXTURE_IDS):
        raise UnifiedSyntheticError("exactly three fictional fixture aliases required")
    nonce = secrets.token_urlsafe(32)
    root = Path(__file__).resolve().parent
    app = Flask(
        "unified_fictional_browser_preview", static_folder=None,
        template_folder=str(root / "templates"),
    )
    app.config.update(
        DEBUG=False, TESTING=False, MAX_CONTENT_LENGTH=4096,
    )

    @app.before_request
    def only_loopback():
        if request.remote_addr not in ("127.0.0.1", "::1"):
            return jsonify(error="private fictional loopback only"), 403
        if request.host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            return jsonify(error="unexpected fictional preview host"), 403
        if request.method == "POST":
            if request.headers.get("Origin") != request.host_url.rstrip("/"):
                return jsonify(error="same origin required"), 403
            supplied = request.headers.get("X-Preview-Nonce", "")
            if not compare_digest(supplied, nonce):
                return jsonify(error="synthetic preview nonce required"), 403
            if request.mimetype != "application/json":
                return jsonify(error="JSON request required"), 415

    @app.after_request
    def protected(response):
        response.headers.update({
            "Cache-Control": "no-store",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
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

    @app.errorhandler((AdmissionDenied, UnifiedSyntheticError))
    def admission_conflict(error):
        return jsonify(error=str(error), synthetic_only=True), 409

    @app.errorhandler(PilotSequenceError)
    def sequence_conflict(error):
        return jsonify(error=str(error), synthetic_only=True), 409

    @app.errorhandler(ValueError)
    def bad_value(error):
        return jsonify(error=str(error), synthetic_only=True), 422

    def resolve():
        body = request.get_json(silent=True)
        if type(body) is not dict:
            raise UnifiedSyntheticError("fictional JSON object required")
        fixture = body.get("fixture")
        if type(fixture) is not str or fixture not in roster:
            raise UnifiedSyntheticError("fictional F1/F2/F3 fixture required")
        pid = roster[fixture]
        learner, _hidden_arm = study.operator_lookup(operator_key, pid)
        return fixture, learner, body

    def virtual_action_time(learner: str) -> datetime:
        state = study.learning.snapshot(learner)
        if state["session"] not in (1, 2, 3):
            raise PilotSequenceError("fictional visit has not started")
        return (
            SYNTHETIC_EPOCH
            + timedelta(days=4 * (state["session"] - 1))
            + timedelta(minutes=state["completed_actions"] + 1)
        )

    @app.get("/")
    def index():
        return render_template(
            "pilot_unified_fictional_browser.html", preview_nonce=nonce,
        )

    @app.get("/unified.js")
    def javascript():
        return send_file(
            root / "static/pilot_unified_fictional_browser.js",
            mimetype="text/javascript",
        )

    @app.get("/unified.css")
    def stylesheet():
        return send_file(
            root / "static/pilot_fictional_preview.css", mimetype="text/css",
        )

    @app.post("/unified/api/status")
    def status():
        fixture, learner, body = resolve()
        if set(body) != {"fixture"}:
            raise UnifiedSyntheticError("unexpected fictional status fields")
        state = study.learning.snapshot(learner)
        # Deliberately no treatment assignment, PID, invitation, token.
        return jsonify(
            fixture=fixture, stage=state["stage"], session=state["session"],
            index=state["index"],
            completed_actions=state["completed_actions"],
            visits_finished=state["visits_finished"],
            synthetic_only=True, human_enrollment_authorized=False,
        )

    @app.post("/unified/api/next")
    def next_action():
        _fixture, learner, body = resolve()
        if set(body) != {"fixture"}:
            raise UnifiedSyntheticError("unexpected fictional action fields")
        return jsonify(study.learning.next_action(
            learner, at=virtual_action_time(learner),
        ))

    @app.post("/unified/api/rendered")
    def rendered():
        _fixture, learner, body = resolve()
        if set(body) != {"fixture", "action_id"} or type(body["action_id"]) is not str:
            raise UnifiedSyntheticError("invalid fictional render fields")
        return jsonify(study.learning.mark_rendered(
            learner, body["action_id"], at=virtual_action_time(learner),
        ))

    @app.post("/unified/api/act")
    def act():
        _fixture, learner, body = resolve()
        if (set(body) != {"fixture", "action_id", "request_id", "response"}
                or type(body["action_id"]) is not str
                or type(body["request_id"]) is not str
                or type(body["response"]) is not dict):
            raise UnifiedSyntheticError("invalid fictional response fields")
        return jsonify(study.learning.submit(
            learner, body["action_id"], body["request_id"],
            body["response"], at=virtual_action_time(learner),
        ))

    return app
