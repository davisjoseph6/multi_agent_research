"""LOCAL ONLY, no human enrollment: HTTP preview of supervisor parallel RCT.

Reuses the supervisor 192-item content validator, existing BKT and separate
SQLite state/contact vault. F1/F2/F3 are fake aliases; a page nonce is NOT
participant authentication; only reserved .test emails can be generated.
The supplied quizzes and recovery placeholders are for developer validation,
not a reviewed bilingual live study. No SMTP, provider or public endpoint.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from pathlib import Path
from threading import RLock
import re
import secrets
from typing import Callable

from flask import Flask, jsonify, render_template, request, send_file

from .supervisor_content import SupervisorBank
from .supervisor_synthetic_store import (
    SupervisorSyntheticStore, SyntheticStudyError,
)

ROOT = Path(__file__).resolve().parent
FIXTURES = ("F1", "F2", "F3")
DEFAULT_EPOCH = datetime(2026,11,11,12,tzinfo=timezone.utc)


class FictionalSupervisorClock:
    def __init__(self, start=DEFAULT_EPOCH):
        self.now = start
    def __call__(self):
        return self.now
    def advance(self):
        self.now += timedelta(days=4)


class FictionalSupervisorRuntime:
    def __init__(self, store: SupervisorSyntheticStore, *,
                 clock: Callable[[], datetime] | None = None):
        if not isinstance(store, SupervisorSyntheticStore):
            raise TypeError("isolated supervisor synthetic store required")
        self.store = store
        self.clock = clock or FictionalSupervisorClock()
        self.roster = {}
        self.pending = {}
        self.lock = RLock()

    def fake(self, fixture: str):
        if type(fixture) is not str or fixture not in FIXTURES:
            raise SyntheticStudyError("fictional F1/F2/F3 fixture required")
        return self.roster.get(fixture)

    def verified(self, fixture: str):
        pair = self.fake(fixture)
        if not pair:
            raise SyntheticStudyError("fictional fixture has not registered")
        return pair


def make_supervisor_fictional_app(
    runtime: FictionalSupervisorRuntime, *, port: int=8783,
) -> Flask:
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("unprivileged private loopback port required")
    nonce = secrets.token_urlsafe(32)
    app = Flask(
        "supervisor_parallel_fictional_preview",static_folder=None,
        template_folder=str(ROOT/"templates"),
    )
    app.config.update(DEBUG=False,TESTING=False,MAX_CONTENT_LENGTH=32768)

    @app.before_request
    def private_only():
        if request.remote_addr not in ("127.0.0.1","::1"):
            return jsonify(error="fictional loopback only"),403
        if request.host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            return jsonify(error="unexpected fictional host"),403
        if request.method=="POST":
            if request.headers.get("Origin") != request.host_url.rstrip("/"):
                return jsonify(error="same origin required"),403
            if not compare_digest(request.headers.get("X-Preview-Nonce",""),nonce):
                return jsonify(error="fictional demo nonce required"),403
            if request.mimetype != "application/json":
                return jsonify(error="JSON required"),415

    @app.after_request
    def protected(resp):
        resp.headers.update({
            "Cache-Control":"no-store",
            "X-Frame-Options":"DENY",
            "X-Content-Type-Options":"nosniff",
            "Referrer-Policy":"no-referrer",
            "X-Robots-Tag":"noindex, nofollow",
            "X-Synthetic-Only":"1",
            "Content-Security-Policy":(
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'none'; object-src 'none'; "
                "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
            ),
        })
        return resp

    @app.errorhandler(SyntheticStudyError)
    @app.errorhandler(ValueError)
    def conflict(err):
        return jsonify(error=str(err),synthetic_only=True),409

    def payload(expected: set[str]):
        v=request.get_json(silent=True)
        if type(v) is not dict or set(v)!=expected:
            raise SyntheticStudyError("invalid fictional HTTP request shape")
        runtime.fake(v.get("fixture"))
        return v

    @app.get("/")
    def index():
        return render_template("supervisor_fictional_web.html",
                               preview_nonce=nonce)

    @app.get("/supervisor-fake.js")
    def script():
        return send_file(ROOT/"static/supervisor_fictional_web.js",
                         mimetype="text/javascript")

    @app.get("/supervisor-fake.css")
    def stylesheet():
        return send_file(ROOT/"static/supervisor_fictional_web.css",
                         mimetype="text/css")

    @app.post("/supervisor/api/screening")
    def screening():
        v=payload({"fixture"})
        with runtime.lock:
            if runtime.fake(v["fixture"]):
                raise SyntheticStudyError("already registered fake fixture")
            return jsonify(
                kind="fictional_registration",
                questions=[q.public() for q in runtime.store.bank.forms["screening"]],
                synthetic_only=True,human_enrollment_authorized=False,
            )

    @app.post("/supervisor/api/register")
    def register():
        v=payload({"fixture","consent","econ_course","screening_answers"})
        with runtime.lock:
            fixture=v["fixture"]
            if runtime.fake(fixture):
                raise SyntheticStudyError("duplicate fictional registration")
            if type(v["consent"]) is not bool or not v["consent"]:
                raise SyntheticStudyError("consent required before screening")
            if type(v["econ_course"]) is not bool:
                raise SyntheticStudyError("economics course question required")
            if type(v["screening_answers"]) is not dict:
                raise SyntheticStudyError("screening answer map required")
            result=runtime.store.register(
                contact_email="fictional-"+fixture.lower()+"@example.test",
                econ_course=v["econ_course"],
                screening_answers=v["screening_answers"],
                consent_version="SUPERVISOR_FICTIONAL_CONSENT_V1",
                consent_given=True,age=23,
                program="Synthetic classroom demonstration",
                at=runtime.clock(),
            )
            if not result["eligible"]:
                return jsonify(eligible=False,
                               screen="not_eligible",
                               synthetic_only=True)
            runtime.roster[fixture]=(
                result["fictional_learner_id"],
                result["fictional_private_token"],
            )
            return jsonify(eligible=True,screen="pretest",
                           synthetic_only=True,
                           human_enrollment_authorized=False)

    @app.post("/supervisor/api/status")
    def status():
        v=payload({"fixture"})
        with runtime.lock:
            pair=runtime.fake(v["fixture"])
            if not pair:
                return jsonify(registered=False,synthetic_only=True)
            ref,token=pair
            state=runtime.store.progress(ref,token)
            return jsonify(registered=True,phase=state["phase"],
                           session=state["session"],index=state["index"],
                           synthetic_only=True,
                           human_enrollment_authorized=False)

    @app.post("/supervisor/api/item")
    def item():
        v=payload({"fixture"})
        with runtime.lock:
            ref,token=runtime.verified(v["fixture"])
            state=runtime.store.progress(ref,token)
            current=runtime.store.next_item(ref,token)
            if state["phase"]=="QUIZ" and current.get("kind") in ("question","recovery"):
                anchor=(current.get("action"),current.get("question_id"))
            else:
                anchor=(state["phase"],current.get("question_id"))
            runtime.pending[v["fixture"]]=(anchor,runtime.clock())
            if state["phase"]=="WAITING_NEXT_SESSION":
                with runtime.store._tx() as db:
                    scheduled=db.execute(
                        "SELECT scheduled_for FROM sessions WHERE learner_id=? "
                        "AND session_no=?",
                        (ref,state["session"]+1),
                    ).fetchone()
                current["scheduled_for"]=scheduled["scheduled_for"] if scheduled else None
            return jsonify(current)

    @app.post("/supervisor/api/answer")
    def answer():
        v=payload({"fixture","question_id","choice","request_id"})
        with runtime.lock:
            fixture=v["fixture"]
            ref,token=runtime.verified(fixture)
            state=runtime.store.progress(ref,token)
            current=runtime.store.next_item(ref,token)
            if state["phase"] in ("PRETEST","POSTTEST"):
                anchor=(state["phase"],current.get("question_id"))
            elif state["phase"]=="QUIZ":
                anchor=(current.get("action"),current.get("question_id"))
            else:
                raise SyntheticStudyError("question answer is not due")
            prior=runtime.pending.get(fixture)
            if not prior or prior[0]!=anchor:
                raise SyntheticStudyError("fictional item must first be displayed")
            if (type(v["request_id"]) is not str or
                    not re.fullmatch(r"[A-Za-z0-9_-]{8,100}",v["request_id"])):
                raise SyntheticStudyError("request ID required")
            at=runtime.clock()
            if state["phase"] in ("PRETEST","POSTTEST"):
                if v["question_id"]!=current["question_id"]:
                    raise SyntheticStudyError("wrong assessment question")
                result=runtime.store.answer_assessment(
                    ref,token,request_id=v["request_id"],
                    item_id=v["question_id"],choice=v["choice"],
                    shown_at=prior[1],answered_at=at,
                )
            else:
                if v["question_id"]!=current.get("question_id"):
                    raise SyntheticStudyError("wrong quiz or recovery question")
                result=runtime.store.answer_quiz(
                    ref,token,request_id=v["request_id"],
                    item_id=v["question_id"],choice=v["choice"],
                    shown_at=prior[1],answered_at=at,
                )
            runtime.pending.pop(fixture,None)
            return jsonify(result)

    @app.post("/supervisor/api/survey")
    def survey():
        v=payload({"fixture","values","request_id"})
        with runtime.lock:
            ref,token=runtime.verified(v["fixture"])
            state=runtime.store.progress(ref,token)
            if state["phase"]!="SURVEY":
                raise SyntheticStudyError("six-item fatigue survey not due")
            prior=runtime.pending.get(v["fixture"])
            if not prior or prior[0][0]!="SURVEY":
                raise SyntheticStudyError("survey must be shown first")
            if type(v["values"]) is not list or len(v["values"])!=6:
                raise SyntheticStudyError("six fatigue responses required")
            result=runtime.store.submit_survey(
                ref,token,values=tuple(v["values"]),time_ms=0,
                request_id=v["request_id"],at=runtime.clock(),
            )
            runtime.pending.pop(v["fixture"],None)
            return jsonify(result)

    @app.post("/supervisor/api/advance-fictional-clock")
    def advance_clock():
        v=payload({"fixture"})
        with runtime.lock:
            ref,token=runtime.verified(v["fixture"])
            state=runtime.store.progress(ref,token)
            if state["phase"]!="WAITING_NEXT_SESSION":
                raise SyntheticStudyError("clock advances only between finished sessions")
            if not isinstance(runtime.clock,FictionalSupervisorClock):
                raise SyntheticStudyError("only fake clock may be advanced")
            runtime.clock.advance()
            result=runtime.store.open_next_session(ref,token,at=runtime.clock())
            return jsonify(result)

    return app
