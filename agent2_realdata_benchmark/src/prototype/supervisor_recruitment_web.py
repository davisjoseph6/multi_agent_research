"""Separate, protected researcher administration and recruitment preview.

Not mounted by the existing study WSGI; deploy only on a distinct service.
The existing pseudonymous BKT dashboard remains isolated from contact PII.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hmac
import json
from pathlib import Path
import sqlite3

from flask import Flask, jsonify, request, send_file
from werkzeug.middleware.proxy_fix import ProxyFix

from .supervisor_recruitment import (
    RecruitmentLedger, RecruitmentError, ADMIN_EMAILS,
)

STATIC=Path(__file__).resolve().parent / "static"


def make_recruitment_app(
    ledger: RecruitmentLedger, *,
    hostname: str = "localhost", proxy_mode: bool = False,
    public_intake_enabled: bool = False,
    research_db: Path | None = None,
    contacts_db: Path | None = None,
) -> Flask:
    """Create application without enabling delivery or human participation."""
    if not isinstance(ledger,RecruitmentLedger):
        raise TypeError("private recruitment ledger required")
    if not isinstance(hostname,str) or not hostname or "/" in hostname:
        raise ValueError("canonical hostname required")
    if type(public_intake_enabled) is not bool or type(proxy_mode) is not bool:
        raise TypeError("explicit boolean controls required")
    if (research_db is None)!=(contacts_db is None):
        raise ValueError("paired research/contact databases required")
    if research_db is not None:
        research_db,contacts_db=Path(research_db),Path(contacts_db)
        if (not research_db.is_absolute() or not contacts_db.is_absolute()
                or not research_db.is_file() or not contacts_db.is_file()
                or research_db.is_symlink() or contacts_db.is_symlink()):
            raise ValueError("existing non-symlink private databases required")
    app=Flask("supervisor_recruitment",static_folder=None)
    app.config.update(DEBUG=False,MAX_CONTENT_LENGTH=8192,
                      MAX_FORM_MEMORY_SIZE=8192)
    if proxy_mode:
        app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1)

    def now():
        return datetime.now(timezone.utc)

    def is_control():
        return request.path.startswith("/control/")

    @app.before_request
    def protect():
        if proxy_mode:
            original=request.environ.get("werkzeug.proxy_fix.orig",{})
            if (original.get("REMOTE_ADDR") not in ("127.0.0.1","::1")
                    or not request.is_secure or request.host!=hostname):
                return jsonify(error="trusted HTTPS proxy required"),403
        else:
            if (request.remote_addr not in ("127.0.0.1","::1")
                    or request.host.split(":")[0] not in ("localhost","127.0.0.1")):
                return jsonify(error="loopback-only service"),403
        if request.method=="POST":
            if (request.mimetype!="application/json" or
                    request.headers.get("Origin")!=request.host_url.rstrip("/") or
                    request.headers.get("X-Study-Request")!="1"):
                return jsonify(error="same-origin JSON required"),403

    @app.after_request
    def security(response):
        response.headers.update({
            "Cache-Control":"private, no-store, max-age=0",
            "Pragma":"no-cache",
            "Referrer-Policy":"no-referrer",
            "X-Content-Type-Options":"nosniff",
            "X-Frame-Options":"DENY",
            "X-Robots-Tag":"noindex,nofollow",
            "Content-Security-Policy":(
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'none'; form-action 'self'; "
                "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
            ),
        })
        if proxy_mode:
            response.headers["Strict-Transport-Security"]="max-age=31536000"
        return response

    @app.errorhandler(RecruitmentError)
    def invalid(_):
        # Do not reflect emails/names or technical secrets in exception messages.
        return jsonify(error="Request rejected or credentials invalid"),409

    def body(*names):
        data=request.get_json(silent=True)
        if type(data) is not dict or set(data)!=set(names):
            raise RecruitmentError("invalid request structure")
        return data

    def admin(mutation=False, *, allow_temporary=False):
        user=ledger.authenticate(
            cookie=request.cookies.get("recruitment_admin_session",""),
            at=now(),mutation=False,
        )
        if mutation:
            ledger.authenticate(
                cookie=request.cookies.get("recruitment_admin_session",""),
                at=now(),mutation=not allow_temporary,
                csrf=request.headers.get("X-CSRF-Token"),
            ) if not allow_temporary else _check_initial_csrf()
        if user["must_change_password"] and not allow_temporary:
            raise RecruitmentError("change temporary password")
        return user

    def _check_initial_csrf():
        # A forced password-change request must also be CSRF guarded.
        token=request.headers.get("X-CSRF-Token","")
        if not hmac.compare_digest(token,request.cookies.get("recruitment_csrf","")):
            raise RecruitmentError("invalid initial password change CSRF")

    def paired_db():
        if research_db is None:
            raise RecruitmentError("private research databases not configured")
        db=sqlite3.connect(research_db.as_uri()+"?mode=ro",uri=True,timeout=5)
        db.row_factory=sqlite3.Row
        db.execute("ATTACH DATABASE ? AS pii",
                   (contacts_db.as_uri()+"?mode=ro",))
        db.execute("PRAGMA query_only=ON")
        return db

    @app.get("/control/")
    def home():
        return send_file(STATIC/"supervisor_recruitment_admin.html")

    @app.get("/control/app.js")
    def js():
        return send_file(STATIC/"supervisor_recruitment_admin.js",
                         mimetype="application/javascript")

    @app.get("/control/app.css")
    def css():
        return send_file(STATIC/"supervisor_recruitment_admin.css",
                         mimetype="text/css")

    @app.post("/control/api/login")
    def login():
        data=body("email","password")
        result=ledger.login(email=data["email"],password=data["password"],at=now())
        response=jsonify(role=result["role"],
                         must_change_password=result["must_change_password"])
        response.set_cookie(
            "recruitment_admin_session",result["cookie"],
            httponly=True,secure=proxy_mode,samesite="Strict",
            path="/control/",max_age=3600,
        )
        response.set_cookie(
            "recruitment_csrf",result["csrf"],
            httponly=False,secure=proxy_mode,samesite="Strict",
            path="/control/",max_age=3600,
        )
        return response

    @app.get("/control/api/me")
    def me():
        user=admin(allow_temporary=True)
        return jsonify(email=user["email"],role=user["role"],
                       must_change_password=user["must_change_password"])

    @app.post("/control/api/change-password")
    def password():
        admin(mutation=True,allow_temporary=True)
        data=body("current","replacement")
        ledger.rotate_password(
            cookie=request.cookies.get("recruitment_admin_session",""),
            csrf=request.headers.get("X-CSRF-Token",""),
            current=data["current"],replacement=data["replacement"],at=now(),
        )
        return jsonify(changed=True)

    @app.get("/control/api/candidates")
    def candidates():
        admin()
        return jsonify(candidates=ledger.candidates(),contains_pii=True)

    @app.post("/control/api/approve")
    def approve():
        user=admin(mutation=True)
        values=body("candidate_ids")
        return jsonify(approved=ledger.approve(
            ids=values["candidate_ids"],actor=user["email"],at=now()
        ),email_sent=False)

    @app.get("/control/api/overview")
    def overview():
        admin()
        with paired_db() as db:
            rows=db.execute(
                "SELECT p.learner_id,p.grp,p.status,ls.session_no,ls.step,"
                "ls.updated_at,c.email FROM participants p "
                "JOIN learner_state ls USING(learner_id) "
                "LEFT JOIN pii.contacts c USING(learner_id) "
                "ORDER BY p.learner_id"
            ).fetchall()
        applicants=ledger.candidates()
        by_email={row["email"]:row for row in applicants}
        participants=[]
        for row in rows:
            value=dict(row)
            applicant=by_email.get((value["email"] or "").casefold(),{})
            value["first_name"]=applicant.get("first_name")
            value["last_name"]=applicant.get("last_name")
            participants.append(value)
        return jsonify(participants=participants,
                       candidates=applicants,contains_pii=True)

    @app.get("/control/api/reminder-policy")
    def policy():
        admin()
        return jsonify(automatic_reminders_enabled=ledger.reminder_enabled(),
                       messages_sent=False)

    @app.post("/control/api/reminder-policy")
    def set_policy():
        user=admin(mutation=True)
        data=body("enabled")
        ledger.set_reminder_enabled(
            enabled=data["enabled"],actor=user["email"],at=now()
        )
        return jsonify(automatic_reminders_enabled=ledger.reminder_enabled(),
                       messages_sent=False)

    @app.get("/interest/<kind>")
    def questionnaire(kind):
        if not public_intake_enabled or kind not in ("school","external"):
            return "",404
        return send_file(STATIC/"supervisor_recruitment_interest.html")

    @app.get("/interest/app.js")
    def intake_js():
        if not public_intake_enabled:return "",404
        return send_file(STATIC/"supervisor_recruitment_interest.js",
                         mimetype="application/javascript")

    @app.get("/interest/app.css")
    def intake_css():
        if not public_intake_enabled:return "",404
        return send_file(STATIC/"supervisor_recruitment_admin.css",
                         mimetype="text/css")

    @app.post("/interest/api/apply")
    def apply():
        if not public_intake_enabled:
            return "",404
        data=body("email","first_name","last_name","questionnaire",
                  "language","privacy_accepted")
        ledger.apply(
            email=data["email"],first_name=data["first_name"],
            last_name=data["last_name"],questionnaire=data["questionnaire"],
            language=data["language"],privacy_accepted=data["privacy_accepted"],
            at=now(),
        )
        return jsonify(received=True,no_enrollment=True),202

    return app
