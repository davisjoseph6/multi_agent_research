"""Disposable real-HTTP, three-fixture, three-visit unified fictional acceptance.

Uses the actual Flask unified browser on an ephemeral 127.0.0.1 port, with
three hidden A/B/C synthetic assignments in a SINGLE temporary SQLite DB.
Drives all learning requests over real HTTP, and only operator-side
fictional visit transitions through the offline Python method. No real
browser, user, student identity, public ingress, production load or human
study approval. The active VPS 8766/8767 services are never contacted.

From agent2_realdata_benchmark:
    python -m scripts.pilot_unified_http_fulljourney
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import socket
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.request import Request, urlopen
import uuid

from werkzeug.serving import make_server

from scripts.pilot_integrated_synthetic_journey import _response
from scripts.pilot_unified_browser_audit import audit_fictional_browser
from scripts.pilot_unified_fictional_browser import open_synthetic_study
from scripts.pilot_unified_private_smoke import run_smoke
from src.prototype.pilot_unified_fictional_browser import (
    FIXTURE_IDS, advance_unified_fictional_visit,
)
from src.prototype.study_v2 import RECOVERY_ACTIONS


def _unused_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _fetch(base: str, path: str) -> bytes:
    with urlopen(base + path, timeout=5) as response:
        if (response.status != 200
                or response.headers.get("X-Synthetic-Only") != "1"):
            raise AssertionError("fictional HTTP GET guard failed")
        return response.read(100_000)


def _post(base: str, nonce: str, action: str, body: dict) -> dict:
    data = json.dumps(body, sort_keys=True).encode("utf-8")
    req = Request(
        base + "/unified/api/" + action,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Origin": base,
            "X-Preview-Nonce": nonce,
        },
        method="POST",
    )
    with urlopen(req, timeout=10) as response:
        if response.status != 200 or response.headers.get("X-Synthetic-Only") != "1":
            raise AssertionError("fictional HTTP POST guard failed")
        result = json.loads(response.read(100_000))
    if type(result) is not dict:
        raise AssertionError("fictional HTTP response was not an object")
    return result


def run_fulljourney() -> dict:
    """A complete three-alias HTTP test; no input DB path or remote hostname."""
    with TemporaryDirectory(prefix="ijcai-unified-http-fictional-") as directory:
        db = Path(directory) / "fictional_admission.sqlite3"
        study, roster, operator, clock = open_synthetic_study(db)
        private_arms = {
            study.operator_lookup(operator, pid)[1] for pid in roster.values()
        }
        if private_arms != {"A", "B", "C"}:
            raise AssertionError("fictional three-arm coverage missing")
        port = _unused_loopback_port()
        from src.prototype.pilot_unified_fictional_browser import (
            create_unified_fictional_browser_app,
        )
        app = create_unified_fictional_browser_app(
            study, operator, roster, port=port,
        )
        service = make_server("127.0.0.1", port, app, threaded=True)
        worker = Thread(target=service.serve_forever, daemon=True)
        worker.start()
        try:
            base = f"http://127.0.0.1:{port}"
            smoke = run_smoke(base)
            if smoke["result"] != "PASS" or smoke["checked"] != 18:
                raise AssertionError("fictional HTTP smoke did not pass")
            html = _fetch(base, "/").decode("utf-8")
            found = re.search(
                r'<meta name="preview-nonce" content="([A-Za-z0-9_-]{32,128})">',
                html,
            )
            if found is None:
                raise AssertionError("fictional browser nonce missing")
            nonce = found.group(1)

            questions = 0
            mvas = 0
            replays = 0
            per_fixture = {}
            for fixture in FIXTURE_IDS:
                actions = 0
                for visit in (1, 2, 3):
                    if visit > 1:
                        advance_unified_fictional_visit(
                            study, operator, fixture, roster, clock,
                        )
                    for step in range(70):
                        status = _post(base, nonce, "status",
                                       {"fixture": fixture})
                        if (status.get("fixture") != fixture
                                or not status.get("synthetic_only")
                                or status.get("human_enrollment_authorized") is not False
                                or any(k in status for k in (
                                    "arm", "pid", "token", "assignment"
                                ))):
                            raise AssertionError("fictional HTTP status leaked assignment")
                        if status["stage"] in ("awaiting_visit", "complete"):
                            break
                        offered = _post(base, nonce, "next",
                                        {"fixture": fixture})
                        if not offered.get("synthetic_only") or not offered.get(
                            "draft_content_not_approved"
                        ):
                            raise AssertionError("nonfictional action response")
                        if step % 13 == 0:
                            same = _post(base, nonce, "next",
                                         {"fixture": fixture})
                            if same != offered:
                                raise AssertionError("fictional pending action changed")
                        confirmed = _post(
                            base, nonce, "rendered",
                            {"fixture": fixture, "action_id": offered["action_id"]},
                        )
                        if not confirmed.get("accepted"):
                            raise AssertionError("fictional render acknowledgment failed")
                        submission = {
                            "fixture": fixture,
                            "action_id": offered["action_id"],
                            "request_id": uuid.uuid4().hex,
                            "response": _response(offered),
                        }
                        accepted = _post(base, nonce, "act", submission)
                        if not accepted.get("accepted") or accepted.get("replayed") is not False:
                            raise AssertionError("fictional new submission failed")
                        if step % 13 == 0:
                            replay = _post(base, nonce, "act", submission)
                            if not replay.get("accepted") or replay.get("replayed") is not True:
                                raise AssertionError("fictional HTTP duplicate was not replay-safe")
                            replays += 1
                        if offered["action"] == "QUESTION":
                            questions += 1
                        if offered["action"] == "MVAS":
                            mvas += 1
                        if (offered["action"] not in (
                                "QUESTION", "DROP_2", "MVAS"
                            ) and offered["action"] not in RECOVERY_ACTIONS):
                            raise AssertionError("unrecognized fictional action kind")
                        actions += 1
                    else:
                        raise AssertionError("fictional HTTP visit did not terminate")
                    at_end = _post(base, nonce, "status", {"fixture": fixture})
                    expected = "complete" if visit == 3 else "awaiting_visit"
                    if at_end["stage"] != expected or at_end["visits_finished"] != visit:
                        raise AssertionError("fictional learning visit incomplete")
                advance_unified_fictional_visit(
                    study, operator, fixture, roster, clock, finish_final=True,
                )
                per_fixture[fixture] = actions

            report = audit_fictional_browser(db)
            if (report["result"] != "PASS_SYNTHETIC_ONLY"
                    or not report["all_three_complete"]
                    or report["total_questions_completed"] != 261
                    or report["total_mvas_completed"] != 18
                    or questions != 261 or mvas != 18):
                raise AssertionError("fictional unified HTTP audit did not pass")
            return {
                "kind": "DISPOSABLE_UNIFIED_FICTIONAL_HTTP_FULLJOURNEY",
                "result": "PASS_SYNTHETIC_ONLY",
                "fictional_displayed_participants": 3,
                "fictional_cohort_records": 9,
                "completed_fictional_visits": 9,
                "completed_questions": questions,
                "proposed_mvas_responses": mvas,
                "retry_replays": replays,
                "http_smoke_checks": smoke["checked"],
                "read_only_completion_audit": report["result"],
                "all_three_finished": report["all_three_complete"],
                "temporary_sqlite_removed_on_exit": True,
                "single_sqlite_file": True,
                "network_scope": "EPHEMERAL_LOOPBACK_HTTP_ONLY",
                "human_enrollment_authorized": False,
                "real_browser_accessibility_test": False,
                "production_security_certification": False,
            }
        finally:
            service.shutdown()
            worker.join(timeout=5)
            service.server_close()


def main() -> None:
    try:
        report = run_fulljourney()
    except Exception as error:
        print(json.dumps({
            "kind": "DISPOSABLE_UNIFIED_FICTIONAL_HTTP_FULLJOURNEY",
            "result": "FAIL",
            "error_type": type(error).__name__,
            "human_enrollment_authorized": False,
        }, sort_keys=True))
        raise SystemExit(2) from None
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
