"""Offline-only fictional V2 three-period browser. NEVER use for human enrollment.

Only a trusted local launcher may construct the six pre-enrolled fixtures and
supply session tokens to this process. API never returns tokens, arm assignments
or real identities. A process-local nonce is NOT participant authentication.
The arithmetic item generator is explicitly fake, NOT the expert-reviewed
bilingual behavioral-economics bank. No SMTP, real email, or public routes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hmac import compare_digest
from pathlib import Path
from threading import RLock
import re
import secrets
from typing import Callable, Mapping

from flask import Flask, jsonify, render_template, request, send_file

from .research_v2_crossover_fixture import FictionalCrossoverStore
from .research_v2_proposal import ProposedStudyError, QUESTIONS_PER_ARM, all_sequences, utc
from .study_v2 import CONCEPTS


FIXTURES = tuple(f"F{i}" for i in range(1, 7))
FORM_ORDER = ("pretest", "practice", "posttest")
BASE_DIR = Path(__file__).resolve().parent


def fictional_item(period: int, form: str, index: int, language: str) -> dict:
    """A predictable basic-arithmetic fixture; synthetic labels ≠ constructs."""
    if type(period) is not int or period not in (0, 1, 2):
        raise ProposedStudyError("fictional period index required")
    if form not in QUESTIONS_PER_ARM or type(index) is not int or not (
        0 <= index < QUESTIONS_PER_ARM[form]
    ):
        raise ProposedStudyError("fictional question index invalid")
    if language not in ("en", "fr"):
        raise ProposedStudyError("language must be English or French")
    a, b = 3 + index % 11, 2 + (period % 3)
    correct_value = a + b
    correct_index = (index + period * 2 + FORM_ORDER.index(form)) % 4
    decoys = iter((correct_value - 2, correct_value - 1, correct_value + 1))
    values = [correct_value if i == correct_index else next(decoys)
              for i in range(4)]
    return {
        "item_id": f"SYN_P{period}_{form}_{index:03d}",
        "form": form,
        "concept": CONCEPTS[(index + period) % len(CONCEPTS)],
        "prompt": (
            f"FICTIONAL ARITHMETIC ITEM (not research material): What is {a} + {b}?"
            if language == "en" else
            f"EXERCICE FICTIF (pas une question scientifique) : combien font {a} + {b} ?"
        ),
        "options": [str(v) for v in values],
        "correct_index": correct_index,
        "a": a, "b": b,
    }


def current_form_and_index(progress: dict) -> tuple[str, int] | None:
    for form in FORM_ORDER:
        if progress["counts"][form] < QUESTIONS_PER_ARM[form]:
            return form, progress["counts"][form]
    return None


def resource_for_pending(pending: dict, period: int, language: str) -> dict:
    action, item_id = pending["action"], pending["target_item_id"]
    match = re.fullmatch(r"SYN_P([012])_practice_(\d{3})", item_id or "")
    if not match or int(match.group(1)) != period:
        raise ProposedStudyError("unverifiable fictional recovery anchor")
    item = fictional_item(period, "practice", int(match.group(2)), language)
    wrong_index = pending["wrong_selected_index"]
    if type(wrong_index) is not int or not 0 <= wrong_index <= 3:
        raise ProposedStudyError("missing original selected wrong choice")
    if wrong_index == item["correct_index"]:
        raise ProposedStudyError("recovery anchor is not an incorrect choice")
    a, b = item["a"], item["b"]
    if action == "DROP_2":
        choices = [
            {"choice_index": i, "text": item["options"][i]}
            for i in (wrong_index, item["correct_index"])
        ]
        return {"kind": "recovery", "action": action, "item_id": item_id,
                "prompt": item["prompt"], "options": choices,
                "synthetic_only": True}
    if action == "CONCEPT_SUMMARY":
        text = (f"Synthetic explanation: adding {a} and {b} means counting both groups."
                if language == "en" else
                f"Explication fictive : ajouter {a} et {b}, c'est compter les deux groupes.")
    elif action == "SOCRATIC_HINT":
        text = (f"If you start at {a} and count {b} further steps, where do you end?"
                if language == "en" else
                f"En partant de {a}, où arrive-t-on après {b} pas supplémentaires ?")
    elif action == "WORKED_EXAMPLE":
        text = (f"Similar example: {a + 1} + {b + 1} = {a + b + 2}. "
                f"Now return to the original {a} + {b}."
                if language == "en" else
                f"Exemple similaire : {a + 1} + {b + 1} = {a + b + 2}. "
                f"Revenez ensuite à {a} + {b}.")
    else:
        raise ProposedStudyError("unknown pending recovery resource")
    return {"kind": "recovery", "action": action, "item_id": item_id,
            "prompt": text, "options": [], "synthetic_only": True}


class FictionalV2Runtime:
    """One process-local operator controller; no human credentials or PII."""

    def __init__(self, store: FictionalCrossoverStore,
                 fixtures: Mapping[str, tuple[str, str | None]],
                 *, clock: Callable[[], datetime] | None = None):
        if not isinstance(store, FictionalCrossoverStore):
            raise TypeError("fictional crossover store required")
        if set(fixtures) != set(FIXTURES):
            raise ProposedStudyError("six fictional fixture mappings required")
        self.store = store
        self.identities = {label: record[0] for label, record in fixtures.items()}
        self.tokens = {label: record[1] for label, record in fixtures.items()}
        if len(set(self.identities.values())) != 6 or any(
            not re.fullmatch(r"SYN_CROSSOVER_[A-Za-z0-9_-]{1,64}", ref)
            for ref in self.identities.values()
        ):
            raise ProposedStudyError("six distinct fictional learners required")
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.lock = RLock()

    def at(self) -> datetime:
        return utc(self.clock())

    def get(self, fixture: str) -> tuple[str, str | None]:
        if type(fixture) is not str or fixture not in self.identities:
            raise ProposedStudyError("fictional F1 through F6 required")
        return self.identities[fixture], self.tokens[fixture]

    def require_token(self, fixture: str) -> tuple[str, str]:
        ref, token = self.get(fixture)
        if not token:
            raise ProposedStudyError("offline operator has not started this period")
        return ref, token


def make_fictional_v2_app(runtime: FictionalV2Runtime, *, port: int = 8774) -> Flask:
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("unprivileged private port required")
    nonce = secrets.token_urlsafe(32)
    app = Flask("research_v2_fictional_browser", static_folder=None,
                template_folder=str(BASE_DIR / "templates"))
    app.config.update(DEBUG=False, TESTING=False, MAX_CONTENT_LENGTH=4096)

    @app.before_request
    def private_only():
        if request.remote_addr not in ("127.0.0.1", "::1"):
            return jsonify(error="fictional loopback only"), 403
        if request.host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            return jsonify(error="unexpected fictional host"), 403
        if request.method == "POST":
            if request.headers.get("Origin") != request.host_url.rstrip("/"):
                return jsonify(error="same origin required"), 403
            if not compare_digest(request.headers.get("X-Preview-Nonce", ""), nonce):
                return jsonify(error="fictional browser nonce required"), 403
            if request.mimetype != "application/json":
                return jsonify(error="JSON required"), 415

    @app.after_request
    def headers(response):
        response.headers.update({
            "Cache-Control": "no-store",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "X-Robots-Tag": "noindex, nofollow",
            "Referrer-Policy": "no-referrer",
            "X-Synthetic-Only": "1",
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'none'; object-src 'none'; "
                "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
            ),
        })
        return response

    @app.errorhandler(ProposedStudyError)
    def rejected(error):
        return jsonify(error=str(error), synthetic_only=True), 409

    def parameters(keys: set[str]) -> dict:
        body = request.get_json(silent=True)
        if type(body) is not dict or set(body) != keys:
            raise ProposedStudyError("invalid fictional request fields")
        runtime.get(body.get("fixture"))
        return body

    def selected(body: dict) -> int:
        value = body.get("selected_index")
        if type(value) is not int or value not in range(4):
            raise ProposedStudyError("selected answer index 0..3 required")
        return value

    def status_for(fixture: str) -> dict:
        ref, token = runtime.get(fixture)
        progress = runtime.store.redacted_progress(ref)
        return {
            "fixture": fixture, "period": progress["period_index"] + 1,
            "counts": progress["counts"], "paused": progress["paused"],
            "recovery_due": progress["recovery_due"],
            "awaiting_continue": progress["awaiting_continue"],
            "between_periods": token is None and not progress["finished"],
            "finished": progress["finished"],
            "synthetic_only": True, "human_enrollment_authorized": False,
            "real_email_sent": False,
        }

    @app.get("/")
    def index():
        return render_template("research_v2_fictional_browser.html",
                               preview_nonce=nonce)

    @app.get("/research-v2.js")
    def js():
        return send_file(BASE_DIR / "static/research_v2_fictional_browser.js",
                         mimetype="text/javascript")

    @app.get("/research-v2.css")
    def css():
        return send_file(BASE_DIR / "static/research_v2_fictional_browser.css",
                         mimetype="text/css")

    @app.post("/research-v2/api/status")
    def status():
        body = parameters({"fixture"})
        with runtime.lock:
            return jsonify(status_for(body["fixture"]))

    @app.post("/research-v2/api/item")
    def item():
        body = parameters({"fixture", "language"})
        fixture, lang = body["fixture"], body["language"]
        with runtime.lock:
            ref, token = runtime.get(fixture)
            progress = runtime.store.redacted_progress(ref)
            if progress["finished"]:
                return jsonify(kind="finished", synthetic_only=True)
            if token is None:
                return jsonify(kind="between_periods", synthetic_only=True)
            if progress["paused"]:
                return jsonify(kind="paused", synthetic_only=True)
            pending = runtime.store.pending_recovery(ref)
            if pending["action"]:
                return jsonify(resource_for_pending(
                    pending, progress["period_index"], lang))
            if pending["awaiting_continue"]:
                return jsonify(kind="awaiting_continue", synthetic_only=True)
            location = current_form_and_index(progress)
            if location is None:
                return jsonify(kind="period_complete", synthetic_only=True)
            form, index = location
            q = fictional_item(progress["period_index"], form, index, lang)
            return jsonify(
                kind="question", item_id=q["item_id"], form=form,
                concept=q["concept"], prompt=q["prompt"],
                options=q["options"], synthetic_only=True,
            )

    @app.post("/research-v2/api/answer")
    def answer():
        body = parameters({"fixture", "item_id", "selected_index", "request_id"})
        fixture = body["fixture"]
        choice = selected(body)
        with runtime.lock:
            ref, token = runtime.require_token(fixture)
            progress = runtime.store.redacted_progress(ref)
            if progress["finished"] or progress["paused"]:
                raise ProposedStudyError("period is not accepting answers")
            match = re.fullmatch(r"SYN_P([012])_(pretest|practice|posttest)_(\d{3})",
                                 body["item_id"] if type(body["item_id"]) is str else "")
            if not match or int(match.group(1)) != progress["period_index"]:
                raise ProposedStudyError("out-of-period fictional question")
            form, index = match.group(2), int(match.group(3))
            q = fictional_item(progress["period_index"], form, index, "en")
            # The storage layer enforces uniqueness. Accept previously submitted
            # IDs here only for exact request-ID replay after a lost HTTP response.
            if index > progress["counts"][form]:
                raise ProposedStudyError("question out of sequence")
            correct = choice == q["correct_index"]
            result = runtime.store.record(
                ref, token, request_id=body["request_id"],
                item_id=q["item_id"], form=form, correct=correct,
                selected_index=choice, concept=q["concept"], at=runtime.at(),
            )
            # Independent pre/post assessments return no per-item correctness.
            # Practice feedback is permitted in this illustrative demo only.
            if form == "practice":
                result = dict(result, correct=correct)
            return jsonify(result)

    @app.post("/research-v2/api/recovery/ack")
    def ack():
        body = parameters({"fixture", "request_id"})
        with runtime.lock:
            ref, token = runtime.require_token(body["fixture"])
            pending = runtime.store.pending_recovery(ref)
            if not pending["action"] or pending["action"] == "DROP_2":
                raise ProposedStudyError("non-DROP_2 recovery required")
            return jsonify(runtime.store.acknowledge_recovery(
                ref, token, request_id=body["request_id"],
                kind=pending["action"], at=runtime.at(),
            ))

    @app.post("/research-v2/api/recovery/drop2")
    def retry():
        body = parameters({"fixture", "item_id", "selected_index", "request_id"})
        choice = selected(body)
        with runtime.lock:
            ref, token = runtime.require_token(body["fixture"])
            progress = runtime.store.redacted_progress(ref)
            pending = runtime.store.pending_recovery(ref)
            if pending["action"] != "DROP_2" or pending["target_item_id"] != body["item_id"]:
                raise ProposedStudyError("no matching two-option recovery")
            resource = resource_for_pending(pending, progress["period_index"], "en")
            legal = {choice["choice_index"] for choice in resource["options"]}
            if choice not in legal:
                raise ProposedStudyError("only the two anchored choices are legal")
            match = re.fullmatch(r"SYN_P([012])_practice_(\d{3})", body["item_id"])
            q = fictional_item(progress["period_index"], "practice", int(match.group(2)), "en")
            if choice != q["correct_index"]:
                return jsonify(accepted=False, retry_required=True, synthetic_only=True)
            return jsonify(runtime.store.record(
                ref, token, request_id=body["request_id"],
                item_id=body["item_id"], form="practice", correct=True,
                selected_index=choice, kind="DROP_2", at=runtime.at(),
            ))

    @app.post("/research-v2/api/decision")
    def decision():
        body = parameters({"fixture", "decision"})
        with runtime.lock:
            ref, token = runtime.require_token(body["fixture"])
            return jsonify(runtime.store.decide_after_recovery(
                ref, token, decision=body["decision"], at=runtime.at(),
            ))

    @app.post("/research-v2/api/pause")
    def pause():
        body = parameters({"fixture"})
        with runtime.lock:
            ref, token = runtime.require_token(body["fixture"])
            runtime.store.pause(ref, token, runtime.at())
            return jsonify(paused=True, synthetic_only=True)

    @app.post("/research-v2/api/resume")
    def resume():
        body = parameters({"fixture"})
        with runtime.lock:
            ref, token = runtime.require_token(body["fixture"])
            runtime.store.resume(ref, token, runtime.at())
            return jsonify(paused=False, synthetic_only=True)

    @app.post("/research-v2/api/finish")
    def finish():
        body = parameters({"fixture"})
        with runtime.lock:
            ref, token = runtime.require_token(body["fixture"])
            period = runtime.store.finish_period(ref, token, runtime.at())
            runtime.tokens[body["fixture"]] = None
            return jsonify(periods_finished=period,
                           finished=period == 3, synthetic_only=True)

    @app.post("/research-v2/api/start-next")
    def start_next():
        body = parameters({"fixture"})
        with runtime.lock:
            ref, token = runtime.get(body["fixture"])
            progress = runtime.store.redacted_progress(ref)
            if token is not None or not progress["period_index"] in (1, 2):
                raise ProposedStudyError("next fictional period is not available")
            runtime.tokens[body["fixture"]] = runtime.store.issue_token(
                ref, runtime.at())
            return jsonify(period=progress["period_index"] + 1,
                           synthetic_only=True)

    @app.post("/research-v2/api/mastery")
    def mastery():
        body = parameters({"fixture"})
        with runtime.lock:
            ref, token = runtime.require_token(body["fixture"])
            progress = runtime.store.redacted_progress(ref)
            counts = progress["counts"]
            # Independent assessments must be performed without item-by-item
            # BKT feedback. Suppress the entire view until pretest completion
            # and during the incomplete posttest.
            if counts["pretest"] < QUESTIONS_PER_ARM["pretest"]:
                return jsonify(available=False, reason="pretest_in_progress",
                               synthetic_only=True)
            if 0 < counts["posttest"] < QUESTIONS_PER_ARM["posttest"]:
                return jsonify(available=False, reason="posttest_in_progress",
                               synthetic_only=True)
            result = runtime.store.mastery_trace(ref, token, runtime.at())
            # Pretest and posttest observed scores are independent outcomes;
            # do not expose them to the learning interface before full period end.
            if counts["posttest"] < QUESTIONS_PER_ARM["posttest"]:
                result["independent_scores"] = {"pretest": None, "posttest": None}
            result["available"] = True
            # No real participant identity or arm assignment is returned.
            return jsonify(result)

    return app
