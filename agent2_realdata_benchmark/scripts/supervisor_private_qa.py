"""Isolated, loopback-only self-acceptance rehearsal for the IJCAI study.

Exercises the REAL participant and researcher Flask applications, not a mock
of their scoring or authentication. This is deliberately NOT a LIVE release:
there is no institutional approval bypass, no public Caddy route, no mail,
and no data import into staging or production. Stop the process to erase
this entire temporary research/contacts/admin sandbox.

Two explicitly allowlisted addresses can be entered in the passwordless
school/external interest questionnaire. The protected researcher can approve
them in /control/, then issue a QA-only token in /control/qa/. A learner uses
that token in /study/ while a different browser context monitors mastery.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import fcntl
from datetime import datetime, timezone
import hmac
from html import escape
import json
import os
from pathlib import Path
import secrets
import signal
import stat
from tempfile import TemporaryDirectory

from flask import Flask, jsonify, request, Response, send_file
from werkzeug.serving import make_server

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_operational_intake import OperationalIntake
from src.prototype.supervisor_recruitment import (
    ADMIN_EMAILS, RecruitmentLedger, RecruitmentError, canonical_email,
)
from src.prototype.supervisor_recruitment_web import make_recruitment_app
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore
from src.prototype.supervisor_vps_web import make_supervisor_vps_app

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "data" / "supervisor_20261111"
FORBIDDEN_PORTS = {8077, 8788, 8790, 8791, 8888, 8889, 8890}
QA_TITLE = "IJCAI PRIVATE SELF-ACCEPTANCE REHEARSAL — NOT A REAL STUDY"
QA_STATIC = ROOT / "src" / "prototype" / "static"


def new_private_suite(directory: Path, allowed_emails: tuple[str, str], *,
                      port: int, persistent: bool = False):
    """Create solely disposable QA state and applications; no sockets or mail."""
    directory = Path(directory)
    if type(persistent) is not bool:
        raise ValueError("explicit boolean required for persistent QA")
    if persistent and (directory != directory.resolve(strict=True)):
        raise ValueError("persistent QA directory must not use symbolic links")
    if (not directory.is_absolute() or directory.is_symlink()
            or not directory.is_dir()
            or stat.S_IMODE(directory.stat().st_mode) != 0o700):
        raise ValueError("QA requires a distinct existing mode-0700 private directory")
    if any(part in str(directory) for part in
           ("/ijcai-supervisor-live", "/ijcai-supervisor-staging")):
        raise ValueError("QA must not use study or staging state")
    if (port < 1024 or port > 65535 or port in FORBIDDEN_PORTS
            or type(port) is not int):
        raise ValueError("a separate unprivileged QA-only port is required")
    if len(allowed_emails) != 2:
        raise ValueError("two distinct, explicitly permitted QA addresses required")
    school, external = tuple(canonical_email(x) for x in allowed_emails)
    if (school == external or not school.endswith("@aivancity.education")
            or external.endswith("@aivancity.education")):
        raise ValueError("one institutional and one external QA address required")
    permitted = frozenset((school, external))
    store = SupervisorSyntheticStore(directory, bank=SupervisorBank(BANK),
                                     operational=True,
                                     qa_early_preview_emails=permitted)
    intake = OperationalIntake(store, programs=("Private QA only",))
    ledger = RecruitmentLedger(directory)
    credential_dir = directory / "qa-admin-secrets"
    if credential_dir.exists() or credential_dir.is_symlink():
        if (not persistent or credential_dir.is_symlink()
                or not credential_dir.is_dir()
                or stat.S_IMODE(credential_dir.stat().st_mode) != 0o700):
            raise ValueError("existing QA secret directory is not safe")
    else:
        credential_dir.mkdir(mode=0o700)
    with ledger._tx() as db:
        existing = {record["email"] for record in
                    db.execute("SELECT email FROM administrators")}
    if existing and not persistent:
        raise ValueError("disposable QA cannot reuse persistent staff credentials")
    if any(email not in ADMIN_EMAILS for email in existing):
        raise ValueError("unexpected researcher in protected QA database")
    passwords = {}
    for email in ADMIN_EMAILS:
        if email in existing:
            continue  # Never rotate or overwrite existing changed passwords.
        password = secrets.token_urlsafe(32)
        path = credential_dir / (email.replace("@", "_at_") + ".txt")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write("QA ONLY (not your LIVE password)\n"
                         f"Account: {email}\nTemporary password: {password}\n")
        try:
            ledger.provision(email=email, temporary_password=password,
                             at=datetime.now(timezone.utc))
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        passwords[email] = password

    study = make_supervisor_vps_app(
        intake, hostname="qa.localhost", proxy_mode=False,
        release_mode="staging", release_authorized=False,
    )
    control = make_recruitment_app(
        ledger, hostname="localhost", proxy_mode=False,
        public_intake_enabled=False, research_db=store.research,
        contacts_db=store.contacts, dispatcher=None, live_verified=False,
    )
    interest = Flask("ijcai_private_qa_interest", static_folder=None)
    interest.config.update(DEBUG=False, MAX_CONTENT_LENGTH=4096)

    @interest.before_request
    def local_only():
        if request.remote_addr not in ("127.0.0.1", "::1"):
            return jsonify(error="loopback only"), 403
        if request.host.split(":")[0] not in ("127.0.0.1", "localhost"):
            return jsonify(error="invalid QA host"), 403
        if request.method == "POST":
            if (request.mimetype != "application/json"
                    or request.headers.get("Origin") != request.host_url.rstrip("/")
                    or request.headers.get("X-Study-Request") != "1"):
                return jsonify(error="same-origin request required"), 403

    @interest.after_request
    def headers(response):
        response.headers.update({
            "Cache-Control": "private, no-store, max-age=0",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-Robots-Tag": "noindex,nofollow",
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; form-action 'self'; frame-ancestors 'none';"
            ),
        })
        return response

    @interest.get("/interest/<kind>")
    def interest_form(kind):
        if kind not in ("school", "external"):
            return "", 404
        return send_file(QA_STATIC / "supervisor_private_qa_interest.html")

    @interest.get("/interest/qa.js")
    def interest_js():
        return send_file(QA_STATIC / "supervisor_private_qa_interest.js",
                         mimetype="application/javascript")

    @interest.get("/interest/qa.css")
    def interest_css():
        return send_file(QA_STATIC / "supervisor_private_qa_interest.css",
                         mimetype="text/css")

    @interest.post("/interest/api/apply")
    def apply():
        obj = request.get_json(silent=True)
        if (type(obj) is not dict or set(obj) != {
            "email", "first_name", "last_name", "language", "questionnaire",
            "qa_acknowledged"
        } or obj.get("qa_acknowledged") is not True):
            return jsonify(error="test acknowledgment required"), 409
        try:
            email = canonical_email(obj["email"])
            if email not in permitted:
                raise RecruitmentError("not an allowlisted test identity")
            ledger.apply(
                email=email, first_name=obj["first_name"],
                last_name=obj["last_name"], language=obj["language"],
                questionnaire=obj["questionnaire"],
                privacy_accepted=True, privacy_sha256="UNAPPROVED",
                at=datetime.now(timezone.utc),
            )
        except (RecruitmentError, ValueError, TypeError):
            return jsonify(error="QA application rejected"), 409
        return jsonify(qa_only=True, application_received=True,
                       actual_enrollment=False, mail_sent=False), 202

    @control.get("/control/qa/")
    def qa_issue_page():
        return send_file(QA_STATIC / "supervisor_private_qa_issue.html")

    @control.get("/control/qa.js")
    def qa_issue_js():
        return send_file(QA_STATIC / "supervisor_private_qa_issue.js",
                         mimetype="application/javascript")

    def qa_actor():
        actor = ledger.authenticate(
            cookie=request.cookies.get("recruitment_admin_session", ""),
            at=datetime.now(timezone.utc),
            mutation=True, csrf=request.headers.get("X-CSRF-Token"),
        )
        if actor["must_change_password"]:
            raise RecruitmentError("temporary password must be changed")
        return actor["email"]

    def issue_qa_candidate(candidate: dict, actor_email: str) -> dict:
        if (not candidate["approved_for_invitation"]
                or candidate["email"] not in permitted
                or candidate["invitation_status"] != "potential"):
            raise RecruitmentError("not a new approved QA candidate")
        address = candidate["email"]
        cid = candidate["candidate_id"]
        now = datetime.now(timezone.utc)
        token = intake.issue(address, at=now,
                             allow_example=address.endswith(".example"))
        ledger.mark_prepared(candidate_id=cid, actor=actor_email, at=now)
        return {"candidate_id": cid, "email": address,
                "test_link": f"http://127.0.0.1:{port}/study/#invite={token}"}

    @control.post("/control/api/qa-issue")
    def qa_issue():
        actor_email = qa_actor()
        data = request.get_json(silent=True)
        if (type(data) is not dict or set(data) != {"candidate_id"}
                or type(data["candidate_id"]) is not int
                or data["candidate_id"] < 1):
            raise RecruitmentError("invalid candidate")
        candidates = ledger.selected_for_invitation(ids=[data["candidate_id"]])
        if len(candidates) != 1:
            raise RecruitmentError("unknown QA candidate")
        return jsonify(qa_only=True, mail_sent=False,
                       **issue_qa_candidate(candidates[0], actor_email))

    @control.post("/control/api/qa-issue-all")
    def qa_issue_all():
        actor_email = qa_actor()
        data = request.get_json(silent=True)
        if type(data) is not dict or data != {"confirm": True}:
            raise RecruitmentError("explicit QA bulk issuance confirmation required")
        # A deliberately tiny, owner-controlled QA cohort. Do not enable
        # arbitrary PII bulk export or mail in this test-only route.
        candidates = ledger.selected_for_invitation(all_approved=True)
        if len(candidates) > len(permitted):
            raise RecruitmentError("unexpected QA candidate cohort")
        links = []
        for candidate in candidates:
            if candidate["email"] not in permitted:
                raise RecruitmentError("unexpected QA recipient")
            if candidate["invitation_status"] == "potential":
                links.append(issue_qa_candidate(candidate, actor_email))
        return jsonify(qa_only=True, mail_sent=False, issued=len(links),
                       links=links)

    def dispatch(environ, start_response):
        path = environ.get("PATH_INFO", "")
        # Permanent *path names* inside the private, SSH-only QA origin.
        # No DNS, public LIVE Caddy route or special QA action is enabled.
        aliases = {
            "/questionnaire/student": "/interest/school",
            "/questionnaire/external": "/interest/external",
            "/researcher": "/control/",
            "/researcher/invitations": "/control/qa/",
            "/participate": "/study/",
        }
        if path in aliases and environ.get("REQUEST_METHOD") == "GET":
            response = Response("",status=302,headers={
                "Location":aliases[path],
                "Cache-Control":"private, no-store, max-age=0",
                "Referrer-Policy":"no-referrer",
                "X-Robots-Tag":"noindex,nofollow",
            })
            return response(environ,start_response)
        if path.startswith("/study/"):
            app = study
        elif path.startswith("/control/"):
            app = control
        elif path.startswith("/interest/"):
            app = interest
        else:
            app = interest
        if not path.startswith(("/study/", "/control/", "/interest/")):
            response = Response("Private QA only: /interest/school, /interest/external, /control/, /study/",
                                status=404)
            return response(environ, start_response)
        return app.wsgi_app(environ, start_response)

    return {"app": dispatch, "interest": interest, "control": control,
            "study": study, "ledger": ledger, "store": store,
            "intake": intake, "credential_dir": credential_dir,
            "passwords": passwords}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8897)
    parser.add_argument("--school-email", required=True)
    parser.add_argument("--external-email", required=True)
    parser.add_argument("--persistent-state-dir",type=Path,
                        help="separate existing 0700 QA-only state; never the LIVE directory")
    parser.add_argument("--acknowledge-private-qa-only",action="store_true",
                        help="explicitly confirm that persistent rehearsal is NOT enrollment")
    args = parser.parse_args()
    if bool(args.persistent_state_dir) != args.acknowledge_private_qa_only:
        parser.error("persistent rehearsal requires both state directory and QA-only acknowledgment")
    if args.port in FORBIDDEN_PORTS:
        parser.error("would conflict with production or staging")
    # Graceful SIGTERM (including browser CI shutdown) must not strand a
    # temporary file containing the tester's real school/Gmail address.
    def shutdown_on_signal(_signal_number, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, shutdown_on_signal)
    context=(nullcontext(args.persistent_state_dir)
             if args.persistent_state_dir else
             TemporaryDirectory(prefix="ijcai-qa-self-acceptance-"))
    with context as tmp:
        directory=Path(tmp)
        if args.persistent_state_dir and (
                not directory.is_absolute() or not directory.is_dir() or
                directory.is_symlink() or
                stat.S_IMODE(directory.stat().st_mode)!=0o700):
            parser.error("persistent QA requires a separate existing mode-0700 directory")
        # A second persistent instance may never write the same SQLite
        # database concurrently or silently regenerate bootstrap secrets.
        lock = os.open(directory/".private-qa.lock",
                       os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            try:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                parser.error("another private QA server already owns this state")
            sandbox=new_private_suite(
                directory,(args.school_email,args.external_email),
                port=args.port,persistent=bool(args.persistent_state_dir))
            print(QA_TITLE, flush=True)
            print("Private QA account secrets at:",sandbox["credential_dir"],flush=True)
            print("QA researcher bootstrap file, if still retained securely:",flush=True)
            print("  "+str(sandbox["credential_dir"] /
                  "davis.joseph_at_aivancity.education.txt"),flush=True)
            print("Do not post passwords or copy LIVE administrator secrets into chat.",flush=True)
            if args.persistent_state_dir:
                print("PERSISTENT PRIVATE QA: accounts and test student data survive restarts.",flush=True)
                print("The original passwords (including changed ones) are preserved.",flush=True)
            else:
                print("Ephemeral QA: state and passwords are deleted on exit.",flush=True)
            print("Student school form: http://127.0.0.1:%d/questionnaire/student" % args.port,flush=True)
            print("Student external form: http://127.0.0.1:%d/questionnaire/external" % args.port,flush=True)
            print("Private researcher: http://127.0.0.1:%d/researcher" % args.port,flush=True)
            print("Invitation console: http://127.0.0.1:%d/researcher/invitations" % args.port,flush=True)
            print("No authentic enrollment, public routing, LIVE permissions or mail.",flush=True)
            print("TEST ONLY: approved QA students may advance session 2/3 early.",flush=True)
            server=make_server("127.0.0.1",args.port,sandbox["app"],
                               threaded=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
        finally:
            os.close(lock)


if __name__ == "__main__":
    main()
