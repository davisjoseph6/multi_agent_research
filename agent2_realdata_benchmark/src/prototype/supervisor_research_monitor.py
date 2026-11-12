"""Read-only, pseudonymous researcher monitoring for the supervisor RCT.

This is a SEPARATE loopback-bound service accessed through individual
authorized SSH tunnels, never the participant /study/ service or shared
Caddy Basic Auth. All routes also require independent administrator Basic
credentials; no contacts DB is opened, no study state is mutated, and no
client can select or change an experimental arm. A live view is descriptive
and MUST NOT inform the participant's intervention policy.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3

from flask import Flask, jsonify, request, send_file
from werkzeug.exceptions import Unauthorized, Forbidden, MethodNotAllowed

from .supervisor_trace_engine import CONCEPT_IDS

ROOT = Path(__file__).resolve().parent
STUDENT_RE = re.compile(r"STUDY_P\d{3,8}\Z")
HASH_RE = re.compile(r"pbkdf2_sha256\$(\d{6,7})\$([0-9a-f]{32})\$([0-9a-f]{64})\Z")
ITERATIONS = 360000


def password_hash(secret: str, *, salt: bytes | None = None) -> str:
    if type(secret) is not str or len(secret) < 18 or len(secret) > 512:
        raise ValueError("administrator password must have 18 to 512 characters")
    salt = secrets.token_bytes(16) if salt is None else salt
    if len(salt) != 16:
        raise ValueError("16-byte salt required")
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def password_matches(secret: str, encoded: str) -> bool:
    match = HASH_RE.fullmatch(encoded)
    if not match or not 200000 <= int(match[1]) <= 1000000:
        raise ValueError("invalid administrator password hash")
    actual = hashlib.pbkdf2_hmac(
        "sha256", secret.encode("utf-8"),
        bytes.fromhex(match[2]), int(match[1]),
    )
    return hmac.compare_digest(actual, bytes.fromhex(match[3]))


def make_monitor_app(research_db: str | Path, *, admin_password_hash: str) -> Flask:
    path = Path(research_db)
    if (not path.is_absolute() or not path.is_file() or path.is_symlink()
            or path.name != "supervisor_operational_study.sqlite3"):
        raise ValueError("existing operational research-only SQLite database required")
    if not HASH_RE.fullmatch(admin_password_hash):
        raise ValueError("administrator password hash required")
    app = Flask("supervisor_research_monitor", static_folder=None)
    app.config.update(DEBUG=False, MAX_CONTENT_LENGTH=1024)

    def connect():
        # Only the pseudonymous research database; do NOT attach PII vault.
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    @app.before_request
    def protect():
        if request.remote_addr not in ("127.0.0.1", "::1"):
            raise Forbidden("SSH tunnel and loopback are required")
        if request.method != "GET":
            raise MethodNotAllowed(["GET"])
        user = request.authorization
        if (user is None or user.type.lower() != "basic"
                or not hmac.compare_digest(user.username or "", "researcher")
                or not password_matches(user.password or "", admin_password_hash)):
            raise Unauthorized(
                "Individual authorized researcher login required",
                www_authenticate='Basic realm="Researcher monitoring", charset="UTF-8"',
            )

    @app.after_request
    def headers(response):
        response.headers.update({
            "Cache-Control": "no-store, private, max-age=0",
            "Pragma": "no-cache",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": "noindex, nofollow",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'self'; style-src 'self';"
                " connect-src 'self'; img-src 'none'; object-src 'none';"
                " frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            ),
        })
        return response

    @app.get("/admin/")
    def index():
        return send_file(ROOT / "templates" / "supervisor_research_monitor.html",
                         mimetype="text/html")

    @app.get("/admin/app.js")
    def js():
        return send_file(ROOT / "static" / "supervisor_research_monitor.js",
                         mimetype="text/javascript")

    @app.get("/admin/app.css")
    def css():
        return send_file(ROOT / "static" / "supervisor_research_monitor.css",
                         mimetype="text/css")

    @app.get("/admin/api/participants")
    def participants():
        with connect() as db:
            rows = db.execute(
                "SELECT p.learner_id,p.grp,p.status,ls.session_no,ls.step,"
                " ls.updated_at FROM participants p "
                "JOIN learner_state ls USING(learner_id) "
                "ORDER BY p.learner_id"
            ).fetchall()
            response = []
            for row in rows:
                d = dict(row)
                counts = db.execute(
                    "SELECT session_no,COUNT(*) n FROM events "
                    "WHERE learner_id=? AND phase='QUIZ' AND action_type='QUESTION' "
                    "GROUP BY session_no ORDER BY session_no",
                    (d["learner_id"],),
                ).fetchall()
                d["regular_answers_by_session"] = {
                    str(x["session_no"]): x["n"] for x in counts
                }
                response.append(d)
        return jsonify(participants=response, contains_pii=False,
                       observational_only=True, refresh_seconds=5)

    @app.get("/admin/api/mastery/<ref>")
    def mastery(ref):
        if not STUDENT_RE.fullmatch(ref):
            raise ValueError("invalid pseudonymous participant reference")
        with connect() as db:
            participant = db.execute(
                "SELECT p.learner_id,p.grp,p.status,ls.session_no,ls.step,"
                " ls.updated_at,ls.state_json FROM participants p "
                "JOIN learner_state ls USING(learner_id) "
                "WHERE p.learner_id=?", (ref,),
            ).fetchone()
            if participant is None:
                return jsonify(error="no such participant"), 404
            rows = db.execute(
                "SELECT e.event_id,e.session_no,e.action_type,e.concept_id,"
                " e.bloom_level,e.answered_at,h.state_json "
                "FROM events e JOIN state_history h USING(event_id) "
                "WHERE e.learner_id=? AND e.phase='QUIZ' "
                "AND e.action_type IN ('QUESTION','DROP_2','SOCRATIC_HINT') "
                "AND e.is_correct IS NOT NULL ORDER BY e.event_id",
                (ref,),
            ).fetchall()
        points = []
        for n, row in enumerate(rows, 1):
            state = json.loads(row["state_json"])
            model = state.get("engine")
            if not isinstance(model, dict) or not isinstance(model.get("mastery"),dict):
                raise ValueError("incomplete historic BKT state")
            curve = {}
            for concept in CONCEPT_IDS:
                value = model["mastery"][concept]
                if isinstance(value,bool) or not isinstance(value,(float,int)) or not 0<=value<=1:
                    raise ValueError("invalid historic BKT mastery probability")
                curve[concept] = round(float(value), 6)
            points.append({
                "x":n, "event_id":row["event_id"],
                "session":row["session_no"],"action":row["action_type"],
                "concept":row["concept_id"],"answered_at":row["answered_at"],
                "mastery":curve,
            })
        current_state = json.loads(participant["state_json"])
        model = current_state.get("engine",{})
        current = model.get("mastery",{}) if isinstance(model,dict) else {}
        return jsonify(
            learner_id=ref, arm=participant["grp"], status=participant["status"],
            session=participant["session_no"], stage=participant["step"],
            last_update=participant["updated_at"], concepts=list(CONCEPT_IDS),
            current_mastery={k:current.get(k) for k in CONCEPT_IDS},
            points=points, x_axis="Scored quiz/recovery response index",
            y_axis="Estimated BKT mastery probability (0–1)",
            contains_pii=False, observational_only=True,
            interpretation="BKT estimates, not measured knowledge",
        )

    return app
