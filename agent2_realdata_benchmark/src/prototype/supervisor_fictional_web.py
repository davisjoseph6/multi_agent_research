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
import time
from typing import Callable

from flask import Flask, jsonify, render_template, request, send_file, redirect

from .supervisor_content import SupervisorBank
from .supervisor_consent_flow import SyntheticConsentFlow
from .supervisor_consent_texts import CONSENT_VERSION, required, STOP_PAGE
from .supervisor_synthetic_store import (
    SupervisorSyntheticStore, SyntheticStudyError,
)

ROOT = Path(__file__).resolve().parent
FIXTURES = ("F1", "F2", "F3")
DEFAULT_EPOCH = datetime(2026,11,11,12,tzinfo=timezone.utc)


class FictionalSupervisorClock:
    def __init__(self, start=DEFAULT_EPOCH):
        self.epoch = start
        self.started_monotonic = time.monotonic()
        self.day_offset = 0

    def __call__(self):
        # Keep the synthetic Day0/Day4/Day8 clock while accurately
        # measuring wall-clock interaction elapsed time.
        return (self.epoch + timedelta(days=self.day_offset)
                + timedelta(seconds=time.monotonic()-self.started_monotonic))

    def advance(self):
        self.day_offset += 4


class FictionalSupervisorRuntime:
    def __init__(self, store: SupervisorSyntheticStore, *,
                 clock: Callable[[], datetime] | None = None):
        if not isinstance(store, SupervisorSyntheticStore):
            raise TypeError("isolated supervisor synthetic store required")
        self.store = store
        self.clock = clock or FictionalSupervisorClock()
        self.roster = {}
        self.consent = SyntheticConsentFlow(store)
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

    @app.get("/supervisor/consent")
    def consent_form_page():
        return redirect("/?consent=1",code=302)

    @app.get("/supervisor/stop")
    def stop_page():
        return redirect("/?stop=1",code=302)

    @app.get("/supervisor-fake.js")
    def script():
        return send_file(ROOT/"static/supervisor_fictional_web.js",
                         mimetype="text/javascript")

    @app.get("/supervisor-fake.css")
    def stylesheet():
        return send_file(ROOT/"static/supervisor_fictional_web.css",
                         mimetype="text/css")

    @app.get("/content/consent/<lang>/info")
    def information(lang):
        if lang not in ("en", "fr"):
            raise SyntheticStudyError("unsupported information sheet language")
        filename="info_sheet_"+lang+"_v1.0.html"
        return send_file(ROOT.parents[1]/"content"/"consent"/filename,
                         mimetype="text/html")

    @app.get("/content/consent/<lang>/pdf")
    def information_pdf(lang):
        if lang not in ("en","fr"):
            raise SyntheticStudyError("unsupported information sheet language")
        filename="info_sheet_"+lang+"_v1.0.pdf"
        pdf=ROOT.parents[1]/"content"/"consent"/filename
        if not pdf.exists():
            raise SyntheticStudyError("versioned PDF must be built before deployment")
        return send_file(pdf,mimetype="application/pdf")

    @app.post("/supervisor/api/consent/copy")
    def consent_copy():
        v=payload({"fixture","language"})
        required_text,optional_text=required(v["language"])
        return jsonify(version=CONSENT_VERSION,required=required_text,
                       optional=optional_text,
                       synthetic_only=True)

    @app.post("/supervisor/api/consent/start")
    def consent_start():
        v=payload({"fixture","checks","optional","language"})
        with runtime.lock:
            return jsonify(runtime.consent.start_consent(
                v["fixture"],checks=v["checks"],optional=v["optional"],
                language=v["language"],at=runtime.clock(),
            ))

    @app.post("/supervisor/api/consent/economics")
    def consent_economics():
        v=payload({"fixture"})
        with runtime.lock:
            return jsonify(runtime.consent.declare_economics_course(v["fixture"]))

    @app.post("/supervisor/api/consent/screen")
    def consent_screen():
        v=payload({"fixture","answers"})
        with runtime.lock:
            return jsonify(runtime.consent.screen(
                v["fixture"],answers=v["answers"],at=runtime.clock(),
            ))

    @app.post("/supervisor/api/consent/register")
    def consent_register():
        v=payload({"fixture","email","age","program"})
        with runtime.lock:
            result=runtime.consent.register(
                v["fixture"],email=v["email"],age=v["age"],
                program=v["program"],at=runtime.clock(),
            )
            runtime.roster[v["fixture"]]=runtime.consent.identities[v["fixture"]]
            return jsonify(result)

    @app.post("/supervisor/api/consent/withdraw")
    def consent_withdraw():
        v=payload({"fixture","delete","confirmed"})
        if v["confirmed"] is not True:
            raise SyntheticStudyError("explicit withdrawal confirmation required")
        with runtime.lock:
            outcome=runtime.consent.withdraw(
                v["fixture"],delete=v["delete"],at=runtime.clock(),
            )
            runtime.roster.pop(v["fixture"],None)
            runtime.pending.pop(v["fixture"],None)
            return jsonify(outcome)

    @app.post("/supervisor/api/consent/debrief")
    def consent_debrief():
        v=payload({"fixture"})
        with runtime.lock:
            return jsonify(runtime.consent.completed_debrief(v["fixture"]))

    @app.post("/supervisor/api/demo/prime-recovery")
    def demo_prime_recovery():
        """Synthetic-only, one-click setup for the actual Group A recovery path.

        Uses the normal consent, screening, registration, pretest and quiz
        engine methods. Never creates real identities, sends email or permits
        arbitrary starting states. Only a brand-new local F1 fixture may use it.
        """
        v = payload({"fixture"})
        with runtime.lock:
            if v["fixture"] != "F1":
                raise SyntheticStudyError("quick recovery requires fictional F1")
            with runtime.store._tx() as db:
                already_used = (
                    db.execute("SELECT COUNT(*) FROM participants").fetchone()[0]
                    + db.execute("SELECT COUNT(*) FROM deletion_log").fetchone()[0]
                )
            if (already_used or runtime.roster or runtime.consent.drafts
                    or runtime.consent.closed or runtime.consent.identities):
                raise SyntheticStudyError(
                    "quick recovery requires a fresh fictional preview; "
                    "restart the local browser server"
                )

            bank = runtime.store.bank
            def wrong(item):
                return next(letter for letter in "ABCD"
                            if letter != item.correct_answer)

            # These are explicit TEST-FIXTURE declarations, not consent from
            # a person. All contact addresses use the reserved .test TLD.
            runtime.consent.start_consent(
                "F1", checks=[True] * 6, optional=False, language="en",
                at=runtime.clock(),
            )
            screening_answers = {
                q.question_id: (q.correct_answer if i < 4 else wrong(q))
                for i, q in enumerate(bank.forms["screening"])
            }
            screened = runtime.consent.screen(
                "F1", answers=screening_answers, at=runtime.clock(),
            )
            if not screened["eligible"]:
                raise SyntheticStudyError("fictional screening unexpectedly excluded")
            runtime.consent.register(
                "F1", email="quick-recovery-f1@example.test", age=23,
                program="Synthetic classroom demonstration", at=runtime.clock(),
            )
            runtime.roster["F1"] = runtime.consent.identities["F1"]
            ref, token = runtime.verified("F1")

            # The supplied supervisor Case 1 starts C2 at mastery 0.20:
            # one correct assessment item for C1,C3,C4,C8, none for others.
            for i, q in enumerate(bank.forms["pretest"]):
                preview = runtime.store.next_item(ref, token)
                if preview.get("question_id") != q.question_id:
                    raise SyntheticStudyError("pretest fixture order mismatch")
                good = q.concept in {"C1", "C3", "C4", "C8"} and q.level == 2
                instant = runtime.clock()
                runtime.store.answer_assessment(
                    ref, token, request_id=f"quick_pretest_{i:02d}",
                    item_id=q.question_id,
                    choice=q.correct_answer if good else wrong(q),
                    shown_at=instant,
                    answered_at=instant + timedelta(milliseconds=1),
                )

            # Case 1, Session 1, first three real engine questions; all wrong.
            for i in range(1, 4):
                item = runtime.store.next_item(ref, token)
                expected_id = f"QZ_C2_L1_{i:02d}"
                if item.get("question_id") != expected_id:
                    raise SyntheticStudyError(
                        "real engine did not reproduce supervisor Case 1"
                    )
                source = bank.get(expected_id, form="practice")
                instant = runtime.clock()
                runtime.store.answer_quiz(
                    ref, token, request_id=f"quick_wrong_{i:02d}",
                    item_id=expected_id, choice=wrong(source),
                    shown_at=instant,
                    answered_at=instant + timedelta(milliseconds=1),
                )

            next_step = runtime.store.next_item(ref, token)
            if (next_step.get("kind") != "recovery"
                    or next_step.get("action") != "CONCEPT_SUMMARY"):
                raise SyntheticStudyError("expected Rule 5b recovery not triggered")
            return jsonify(
                prepared=True, group="A", session=1,
                regular_questions_answered=3,
                recovery_trigger="Rule 5b: three wrong on C2",
                next_action="CONCEPT_SUMMARY",
                synthetic_only=True, real_email_sent=False,
                human_enrollment_authorized=False,
            )

    @app.post("/supervisor/api/screening")
    def screening():
        v=payload({"fixture"})
        with runtime.lock:
            if runtime.fake(v["fixture"]):
                raise SyntheticStudyError("already registered fake fixture")
            if not app.config["TESTING"] and (
                v["fixture"] not in runtime.consent.drafts
                or runtime.consent.drafts[v["fixture"]]["screening_answers"] is not None
            ):
                raise SyntheticStudyError("six-checkbox consent required before screening")
            return jsonify(
                kind="fictional_registration",
                questions=[q.public() for q in runtime.store.bank.forms["screening"]],
                synthetic_only=True,human_enrollment_authorized=False,
            )

    @app.post("/supervisor/api/register")
    def register():
        v=payload({"fixture","consent","econ_course","screening_answers"})
        with runtime.lock:
            if not app.config["TESTING"]:
                raise SyntheticStudyError(
                    "single-checkbox legacy fictional API disabled; use staged consent"
                )
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
                fixture=v["fixture"]
                if fixture in runtime.consent.closed:
                    stage="excluded"
                elif fixture in runtime.consent.drafts:
                    draft=runtime.consent.drafts[fixture]
                    stage=("registration" if draft["screening_answers"] is not None
                           else "screening")
                else:
                    stage="information"
                return jsonify(registered=False,consent_stage=stage,
                               synthetic_only=True)
            ref,token=pair
            state=runtime.store.progress(ref,token)
            with runtime.store._tx() as db:
                consent=db.execute(
                    "SELECT consent_lang,consent_version FROM participants "
                    "WHERE learner_id=?",(ref,),
                ).fetchone()
            return jsonify(registered=True,phase=state["phase"],
                           session=state["session"],index=state["index"],
                           consent_lang=consent["consent_lang"],
                           consent_version=consent["consent_version"],
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
        expected={"fixture","question_id","choice","request_id"}
        raw=request.get_json(silent=True)
        if type(raw) is dict and "reflection" in raw:
            v=payload(expected | {"reflection"})
        else:
            v=payload(expected)
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
                if "reflection" in v:
                    raise SyntheticStudyError("assessment responses contain no recovery reflections")
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
                if (current.get("action") == "SOCRATIC_HINT"
                        and fixture in runtime.consent.identities
                        and "reflection" not in v):
                    raise SyntheticStudyError(
                        "complete both Socratic reflections before the re-attempt"
                    )
                result=runtime.store.answer_quiz(
                    ref,token,request_id=v["request_id"],
                    item_id=v["question_id"],choice=v["choice"],
                    shown_at=prior[1],answered_at=at,
                    free_text=v.get("reflection"),
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
            at=runtime.clock()
            survey_elapsed_ms=max(0,int(
                (at-prior[1]).total_seconds()*1000,
            ))
            result=runtime.store.submit_survey(
                ref,token,values=tuple(v["values"]),
                time_ms=survey_elapsed_ms,
                request_id=v["request_id"],at=at,
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

    # Legacy API compatibility names from Experimentation.pdf, but with
    # safe server-side fictional identity and one-step assessment flow. These
    # are restricted aliases, NOT a route for clients to choose their arm,
    # import untrusted pretest outcomes, or self-register real participants.
    @app.post("/initialize_learner")
    def legacy_initialize():
        data=payload({"fixture"})
        with runtime.lock:
            ref,token=runtime.verified(data["fixture"])
            state=runtime.store.progress(ref,token)
            if state["phase"]=="PRETEST":
                raise SyntheticStudyError("complete 16 independent pretest items first")
            return jsonify(initialized=True,synthetic_only=True,
                           human_enrollment_authorized=False)

    app.add_url_rule("/get_next_action",endpoint="legacy_get_next_action",
                     view_func=item,methods=["POST"])
    app.add_url_rule("/update_after_response",endpoint="legacy_update_after_response",
                     view_func=answer,methods=["POST"])

    return app
