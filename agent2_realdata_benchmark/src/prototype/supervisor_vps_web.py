"""Supervisor parallel-group RCT operational HTTPS API (invitation-only).

Public HTTPS deployment must be behind a trusted same-host reverse proxy, with
a private institutional release configuration. Unlike the fictional browser,
this service persists SQLite state across restarts, authenticates bearer
capabilities via Secure/HttpOnly/SameSite cookies, and never exposes arms or
answer keys. It intentionally does not authorize real enrollment itself.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import secrets

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.middleware.proxy_fix import ProxyFix

from .supervisor_consent_texts import (CONSENT_VERSION, required, STOP_PAGE, DEBRIEF,
                                       NONREWARD_DEBRIEF_EN, NONREWARD_DEBRIEF_FR)
from .supervisor_i18n import localize_public
from .supervisor_operational_intake import OperationalIntake
from .supervisor_synthetic_store import SyntheticStudyError, iso

ROOT=Path(__file__).resolve().parent
COOKIE="supervisor_study_session"
ID_PATTERN=re.compile(r"[A-Za-z0-9_-]{8,100}\Z")


def make_supervisor_vps_app(intake: OperationalIntake, *,
                            hostname: str, proxy_mode: bool,
                            release_mode: str = "staging",
                            release_authorized: bool = False) -> Flask:
    if release_mode == "live" and release_authorized is not True:
        raise ValueError("live enrollment requires independently verified release")
    if release_mode not in ("staging","live"):
        raise ValueError("release mode must be staging or live")
    if not isinstance(intake,OperationalIntake):
        raise TypeError("operational intake required")
    if type(proxy_mode) is not bool:
        raise ValueError("proxy_mode must be boolean")
    if not hostname or "/" in hostname or ":" in hostname or hostname.count(".")<1:
        raise ValueError("explicit canonical domain required")
    app=Flask("supervisor_vps",static_folder=None,
              template_folder=str(ROOT/"templates"))
    app.config.update(DEBUG=False,MAX_CONTENT_LENGTH=32768,
                      MAX_FORM_MEMORY_SIZE=32768,SESSION_COOKIE_HTTPONLY=True)
    if proxy_mode:
        app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1)
    store=intake.store

    def now():
        return datetime.now(timezone.utc)

    @app.before_request
    def protect():
        # Only the same-host reverse proxy may present a forwarded HTTPS
        # assertion. A remote client cannot directly claim proxy headers.
        if proxy_mode:
            original=request.environ.get("werkzeug.proxy_fix.orig",{})
            if original.get("REMOTE_ADDR") not in ("127.0.0.1","::1"):
                return jsonify(error="trusted local reverse proxy required"),403
            if not request.is_secure or request.host!=hostname:
                return jsonify(error="canonical HTTPS host required"),403
        else:
            if request.remote_addr not in ("127.0.0.1","::1"):
                return jsonify(error="private developer transport only"),403
            if request.host.split(":")[0] not in ("localhost","127.0.0.1"):
                return jsonify(error="unexpected test host"),403
        if request.method=="POST":
            if (request.mimetype!="application/json" or
                    request.headers.get("Origin")!=request.host_url.rstrip("/")):
                return jsonify(error="same-origin JSON request required"),403
            if request.headers.get("X-Study-Request")!="1":
                return jsonify(error="study CSRF header required"),403

    @app.after_request
    def protected(response):
        response.headers.update({
            "Cache-Control":"no-store",
            "Pragma":"no-cache",
            "X-Frame-Options":"DENY",
            "X-Content-Type-Options":"nosniff",
            "Referrer-Policy":"no-referrer",
            "X-Robots-Tag":"noindex, nofollow",
            "Permissions-Policy":"camera=(),microphone=(),geolocation=()",
            "Content-Security-Policy":(
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'none'; object-src 'none'; "
                "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
            ),
        })
        if proxy_mode:
            response.headers["Strict-Transport-Security"]="max-age=31536000"
        return response

    @app.errorhandler(SyntheticStudyError)
    @app.errorhandler(ValueError)
    def invalid(ex):
        # Avoid reflecting PII or contact addresses in error messages.
        message=str(ex)
        if any(term in message.casefold() for term in ("email","contact","recipient")):
            message="This request cannot be completed"
        return jsonify(error=message),409

    @app.errorhandler(413)
    def too_big(_):
        return jsonify(error="payload too large"),413

    def data(*keys):
        body=request.get_json(silent=True)
        if type(body) is not dict or set(body)!=set(keys):
            raise SyntheticStudyError("invalid request fields")
        return body

    def credential():
        token=request.cookies.get(COOKIE)
        if not token:
            raise SyntheticStudyError("verified invitation session required")
        return token

    def enrolled():
        token=credential()
        learner=intake.learner(token,at=now())
        return learner,token

    @app.get("/study/")
    def index():
        return render_template("supervisor_vps.html",release_mode=release_mode)

    @app.get("/study/app.js")
    def js():
        return send_file(ROOT/"static"/"supervisor_vps.js",
                         mimetype="text/javascript")

    @app.get("/study/app.css")
    def css():
        return send_file(ROOT/"static"/"supervisor_vps.css",
                         mimetype="text/css")

    @app.get("/study/health")
    def health():
        return jsonify(service="supervisor_parallel_three_arm",
                       deployment=release_mode,ready=True,
                       enrollment_authorized=(release_mode=="live"))

    @app.get("/study/info/<language>")
    def info(language):
        if language not in ("en","fr"):
            raise SyntheticStudyError("unsupported information language")
        # Consent information is invitation-dependent: never imply that a
        # personal-email invite is eligible for aivancity-only AI points.
        eligible=intake.reward_eligible(credential(),at=now())
        filename=(f"info_sheet_{language}_v1.0.html" if eligible else
                  f"info_sheet_{language}_v1.1_nonreward.html")
        path=ROOT.parents[1]/"content"/"consent"/filename
        return send_file(path,mimetype="text/html")

    @app.post("/study/api/exchange")
    def exchange():
        value=data("token")
        token=value["token"]
        status=intake.status(token,at=now())
        response=jsonify(status)
        response.set_cookie(
            COOKIE,token,
            path="/study/",
            httponly=True,secure=proxy_mode,
            samesite="Strict",max_age=60*60*24*14,
        )
        return response

    @app.post("/study/api/status")
    def status():
        data()
        return jsonify(intake.status(credential(),at=now()))

    @app.post("/study/api/consent-copy")
    def copy():
        value=data("language")
        if value["language"] not in ("en","fr"):
            raise SyntheticStudyError("unsupported consent language")
        # The invitation's private contact email is the sole authority for
        # reward eligibility. The browser cannot send an email or a flag.
        return jsonify(intake.consent_requirements(
            credential(),language=value["language"],at=now(),
        ))

    @app.post("/study/api/consent")
    def consent():
        value=data("checks","optional","language")
        return jsonify(intake.consent(credential(),checks=value["checks"],
                                      optional=value["optional"],
                                      language=value["language"],at=now()))

    @app.post("/study/api/course-exclusion")
    def course_exclusion():
        data()
        intake.exclude_prior_course(credential(),at=now())
        response=jsonify(stage="excluded")
        response.delete_cookie(COOKIE,path="/study/")
        return response

    @app.post("/study/api/screening")
    def screening():
        data()
        status=intake.status(credential(),at=now())
        if status["stage"]!="consented":
            raise SyntheticStudyError("consent required before screening")
        language=status["language"]
        return jsonify(questions=[
            localize_public(q.public(),language=language)
            for q in store.bank.forms["screening"]
        ],language=language)

    @app.post("/study/api/screen")
    def screen():
        value=data("answers")
        result=intake.screening(credential(),answers=value["answers"],at=now())
        response=jsonify(result)
        if not result["eligible"]:
            response.delete_cookie(COOKIE,path="/study/")
        return response

    @app.post("/study/api/programs")
    def programs():
        data()
        status=intake.status(credential(),at=now())
        if status["stage"] not in ("screened","participant"):
            raise SyntheticStudyError("registration has not been authorized")
        return jsonify(programs=list(intake.programs))

    @app.post("/study/api/register")
    def register():
        value=data("age","program")
        return jsonify(intake.register(credential(),age=value["age"],
                                       program=value["program"],at=now()))

    @app.post("/study/api/language")
    def set_language():
        value=data("language")
        ref,token=enrolled()
        store.set_study_language(ref,token,value["language"])
        return jsonify(language=value["language"])

    @app.post("/study/api/item")
    def item():
        data()
        ref,token=enrolled()
        state=store.progress(ref,token)
        current=store.next_item(ref,token)
        out={k:v for k,v in current.items() if k!="synthetic_only"}
        if state["phase"] in ("PRETEST","POSTTEST","QUIZ","SURVEY"):
            render_id=secrets.token_urlsafe(24)
            with store._tx() as db:
                store._authenticated(db,ref,token)
                db.execute(
                    "INSERT INTO operational_rendered("
                    "learner_id,render_id,phase,action,question_id,rendered_at)"
                    " VALUES(?,?,?,?,?,?) ON CONFLICT(learner_id) DO UPDATE SET "
                    "render_id=excluded.render_id,phase=excluded.phase,"
                    "action=excluded.action,question_id=excluded.question_id,"
                    "rendered_at=excluded.rendered_at",
                    (ref,render_id,state["phase"],current.get("action"),
                     current.get("question_id"),iso(now())),
                )
            out["render_id"]=render_id
        if state["phase"]=="WAITING_NEXT_SESSION":
            with store._tx() as db:
                row=db.execute(
                    "SELECT scheduled_for FROM sessions WHERE learner_id=? "
                    "AND session_no=?",(ref,state["session"]+1),
                ).fetchone()
            out["scheduled_for"]=row["scheduled_for"] if row else None
        return jsonify(out)

    def shown(ref,token,render_id,phase,action,item_id):
        with store._tx() as db:
            store._authenticated(db,ref,token)
            row=db.execute(
                "SELECT * FROM operational_rendered WHERE learner_id=?",
                (ref,),
            ).fetchone()
            if not row or not secrets.compare_digest(row["render_id"],render_id):
                raise SyntheticStudyError("question must be displayed before answering")
            if (row["phase"]!=phase or row["action"]!=action
                    or row["question_id"]!=item_id):
                raise SyntheticStudyError("displayed item is no longer current")
            return datetime.fromisoformat(row["rendered_at"])

    def clear_render(ref,render_id):
        with store._tx() as db:
            db.execute("DELETE FROM operational_rendered "
                       "WHERE learner_id=? AND render_id=?",
                       (ref,render_id))

    @app.post("/study/api/answer")
    def answer():
        value=data("render_id","request_id","question_id","choice","reflection")
        if (type(value["request_id"]) is not str or
                not ID_PATTERN.fullmatch(value["request_id"])):
            raise SyntheticStudyError("request identifier required")
        ref,token=enrolled()
        state=store.progress(ref,token)
        current=store.next_item(ref,token)
        phase=state["phase"]
        if phase not in ("PRETEST","POSTTEST","QUIZ"):
            raise SyntheticStudyError("answer is not due")
        if value["question_id"]!=current.get("question_id"):
            raise SyntheticStudyError("question mismatch")
        action=current.get("action")
        started=shown(ref,token,value["render_id"],phase,action,
                      current.get("question_id"))
        at=now()
        if phase in ("PRETEST","POSTTEST"):
            if value["reflection"] is not None:
                raise SyntheticStudyError("no reflection in independent assessments")
            result=store.answer_assessment(
                ref,token,request_id=value["request_id"],
                item_id=value["question_id"],choice=value["choice"],
                shown_at=started,answered_at=at,
            )
        else:
            if action=="SOCRATIC_HINT" and (
                    type(value["reflection"]) is not list or
                    len(value["reflection"])!=2):
                raise SyntheticStudyError("two guiding reflections are required")
            if action!="SOCRATIC_HINT" and value["reflection"] is not None:
                raise SyntheticStudyError("reflections only for Socratic prompts")
            result=store.answer_quiz(
                ref,token,request_id=value["request_id"],
                item_id=value["question_id"],choice=value["choice"],
                shown_at=started,answered_at=at,
                free_text=value["reflection"],
            )
        clear_render(ref,value["render_id"])
        return jsonify({k:v for k,v in result.items() if k!="synthetic_only"})

    @app.post("/study/api/survey")
    def survey():
        value=data("render_id","request_id","values")
        ref,token=enrolled()
        state=store.progress(ref,token)
        if state["phase"]!="SURVEY":
            raise SyntheticStudyError("survey is not due")
        started=shown(ref,token,value["render_id"],"SURVEY",None,None)
        elapsed=round((now()-started).total_seconds()*1000)
        result=store.submit_survey(
            ref,token,values=tuple(value["values"]),
            time_ms=elapsed,request_id=value["request_id"],at=now(),
        )
        clear_render(ref,value["render_id"])
        return jsonify({k:v for k,v in result.items() if k!="synthetic_only"})

    @app.post("/study/api/next-session")
    def next_session():
        data()
        ref,token=enrolled()
        return jsonify(store.open_next_session(ref,token,at=now()))

    @app.post("/study/api/withdraw")
    def withdraw():
        value=data("delete")
        ref,token=enrolled()
        result=store.withdraw(ref,token,delete=value["delete"],
                              at=now(),channel="website")
        response=jsonify(
            withdrawn=bool(result["withdrawn"]),
            data_deleted=bool(result["data_deleted"]),
        )
        response.delete_cookie(COOKIE,path="/study/")
        return response

    @app.post("/study/api/debrief")
    def debrief():
        data()
        ref,token=enrolled()
        progress=store.progress(ref,token)
        if progress["phase"]!="DONE":
            raise SyntheticStudyError("all sessions must be finished first")
        rewarded=intake.reward_eligible(token,at=now())
        if progress["study_language"]=="fr":
            if rewarded:
                text=("Merci d'avoir participé à cette étude. Trois parcours ont "
                      "été comparés, sans révéler votre affectation pendant les "
                      "séances. Vos 150 AI points nécessitent l'achèvement des "
                      "trois séances. Pour vos droits et les résultats, consultez "
                      "la notice d'information.")
            else:
                text=NONREWARD_DEBRIEF_FR
        else:
            text=DEBRIEF if rewarded else NONREWARD_DEBRIEF_EN
        return jsonify(text=text)

    return app
