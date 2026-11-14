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

from flask import Flask, jsonify, request, Response
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
INTEREST_HTML = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>IJCAI QA — Interest questionnaire</title>
</head><body>
<h1>Private QA questionnaire — NOT real research enrollment</h1>
<p>This is a software test using draft information only. No institutionally
approved study participation or consent is recorded. Records are destroyed
when the isolated QA process ends.</p>
<form id="interest-form">
<label>Email (the one explicitly permitted for this rehearsal)
<input id="email" type="email" required autocomplete="email"></label>
<label>First name (optional)<input id="first-name" maxlength="100"></label>
<label>Last name (optional)<input id="last-name" maxlength="100"></label>
<label>Language <select id="language"><option value="en">English</option>
<option value="fr">Français</option></select></label>
<label><input type="checkbox" id="ack" required>
I understand this is ONLY a private software rehearsal, not a real RCT.</label>
<button type="submit">Submit rehearsal application</button>
</form><p id="status" role="status"></p>
<script src="/interest/qa.js"></script></body></html>"""
INTEREST_JS = """'use strict';
(()=>{
 const el=id=>document.getElementById(id);
 el('interest-form').addEventListener('submit',async e=>{
  e.preventDefault();
  el('status').textContent='';
  const questionnaire=location.pathname.endsWith('/school')?'school':'external';
  const payload={email:el('email').value,first_name:el('first-name').value,
    last_name:el('last-name').value,language:el('language').value,
    questionnaire,qa_acknowledged:el('ack').checked};
  try{
   const r=await fetch('/interest/api/apply',{method:'POST',
    credentials:'same-origin',cache:'no-store',
    headers:{'Content-Type':'application/json','X-Study-Request':'1'},
    body:JSON.stringify(payload)});
   if(!r.ok)throw Error('rejected');
   el('status').textContent='QA application saved. Sign into the private researcher page to approve it.';
  }catch(_){el('status').textContent='QA application rejected; verify your allowlisted address.'}
 });
})();"""
ISSUE_HTML = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Private QA link issuance</title></head><body>
<h1>Test-only private invitation</h1>
<p>First sign in at <a href="/control/">Researcher dashboard</a>,
change the temporary QA password, and approve a test applicant.
This does NOT send mail or enroll a participant in the released study.</p>
<form id="issue-form"><label>Approved candidate ID
<input id="candidate" type="number" min="1" required></label>
<button type="submit">Issue one QA link</button></form>
<p id="status" role="status"></p><a id="qa-link" href="#" hidden>Open private test invitation</a>
<script src="/control/qa.js"></script></body></html>"""
ISSUE_JS = """'use strict';(()=>{
 const el=id=>document.getElementById(id);
 const csrf=()=>{const a=document.cookie.split('; ').find(s=>s.startsWith('recruitment_csrf='));
  return a?decodeURIComponent(a.slice(a.indexOf('=')+1)):''};
 el('issue-form').addEventListener('submit',async e=>{
  e.preventDefault();el('qa-link').hidden=true;
  try{
   const r=await fetch('/control/api/qa-issue',{
    method:'POST',credentials:'same-origin',cache:'no-store',
    headers:{'Content-Type':'application/json','X-Study-Request':'1','X-CSRF-Token':csrf()},
    body:JSON.stringify({candidate_id:Number(el('candidate').value)})});
   if(!r.ok)throw Error('denied');
   const d=await r.json();el('qa-link').href=d.test_link;
   el('qa-link').hidden=false;
   el('status').textContent='QA-only private link created; no mail was sent.';
  }catch(_){el('status').textContent='Denied. Log in, change password, approve the candidate, then use a new ID.'}
 });
})();"""


def new_private_suite(directory: Path, allowed_emails: tuple[str, str], *,
                      port: int):
    """Create solely disposable QA state and applications; no sockets or mail."""
    directory = Path(directory)
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
                                     operational=True)
    intake = OperationalIntake(store, programs=("Private QA only",))
    ledger = RecruitmentLedger(directory)
    credential_dir = directory / "qa-admin-secrets"
    credential_dir.mkdir(mode=0o700)
    passwords = {}
    for email in ADMIN_EMAILS:
        password = secrets.token_urlsafe(32)
        ledger.provision(email=email, temporary_password=password,
                         at=datetime.now(timezone.utc))
        passwords[email] = password
        path = credential_dir / (email.replace("@", "_at_") + ".txt")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write("QA ONLY (not your LIVE password)\n"
                         f"Account: {email}\nTemporary password: {password}\n")

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
        return Response(INTEREST_HTML, mimetype="text/html")

    @interest.get("/interest/qa.js")
    def interest_js():
        return Response(INTEREST_JS, mimetype="application/javascript")

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
        return Response(ISSUE_HTML, mimetype="text/html")

    @control.get("/control/qa.js")
    def qa_issue_js():
        return Response(ISSUE_JS, mimetype="application/javascript")

    @control.post("/control/api/qa-issue")
    def qa_issue():
        actor = ledger.authenticate(
            cookie=request.cookies.get("recruitment_admin_session", ""),
            at=datetime.now(timezone.utc),
            mutation=True, csrf=request.headers.get("X-CSRF-Token"),
        )
        if actor["must_change_password"]:
            raise RecruitmentError("temporary password must be changed")
        data = request.get_json(silent=True)
        if (type(data) is not dict or set(data) != {"candidate_id"}
                or type(data["candidate_id"]) is not int
                or data["candidate_id"] < 1):
            raise RecruitmentError("invalid candidate")
        cid = data["candidate_id"]
        candidates = ledger.selected_for_invitation(ids=[cid])
        if (len(candidates) != 1
                or not candidates[0]["approved_for_invitation"]
                or candidates[0]["email"] not in permitted
                or candidates[0]["invitation_status"] != "potential"):
            raise RecruitmentError("not a new approved QA candidate")
        address = candidates[0]["email"]
        now = datetime.now(timezone.utc)
        token = intake.issue(address, at=now,
                             allow_example=address.endswith(".example"))
        ledger.mark_prepared(candidate_id=cid, actor=actor["email"], at=now)
        return jsonify(qa_only=True, mail_sent=False,
                       test_link=f"http://127.0.0.1:{port}/study/#invite={token}")

    def dispatch(environ, start_response):
        path = environ.get("PATH_INFO", "")
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
    args = parser.parse_args()
    if args.port in FORBIDDEN_PORTS:
        parser.error("would conflict with production or staging")
    # Graceful SIGTERM (including browser CI shutdown) must not strand a
    # temporary file containing the tester's real school/Gmail address.
    def shutdown_on_signal(_signal_number, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, shutdown_on_signal)
    with TemporaryDirectory(prefix="ijcai-qa-self-acceptance-") as tmp:
        sandbox = new_private_suite(Path(tmp),
            (args.school_email, args.external_email), port=args.port)
        print(QA_TITLE, flush=True)
        print("Private QA account secrets at:", sandbox["credential_dir"], flush=True)
        print("QA school form: http://127.0.0.1:%d/interest/school" % args.port, flush=True)
        print("QA external form: http://127.0.0.1:%d/interest/external" % args.port, flush=True)
        print("QA researcher sign-in: http://127.0.0.1:%d/control/" % args.port, flush=True)
        print("QA researcher link tool: http://127.0.0.1:%d/control/qa/" % args.port, flush=True)
        print("No real study enrollment, approved consent, mail or public routing.", flush=True)
        print("Temporary QA state is deleted on exit; keep no important data here.", flush=True)
        server = make_server("127.0.0.1", args.port, sandbox["app"],
                             threaded=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
