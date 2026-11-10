"""Disposable, actual loopback-HTTP A/B/C three-visit fictional pilot acceptance.

Exercise the same Flask application source running on the private VPS, but
NEVER connect to its service or touch its database. Creates exactly three
SYN_PILOT_* fixtures in a TemporaryDirectory, serves on an ephemeral
127.0.0.1 port, and destroys the entire database at exit.

Run from agent2_realdata_benchmark on the VPS or WSL:
    python -m scripts.pilot_disposable_http_fulljourney

Not evidence for human enrollment, research efficacy, public HTTPS, browser
accessibility, penetration testing, or production concurrency capacity.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import socket
from tempfile import TemporaryDirectory
from threading import Thread
import uuid

from werkzeug.serving import make_server

from scripts.pilot_private_vps_smoke import _request, run_acceptance
from src.prototype.pilot_fictional_acceptance_audit import audit_fictional_database
from src.prototype.pilot_local_browser_preview import (
    advance_fictional_visit,
    create_fictional_preview_app,
    ensure_three_fictional_records,
)
from src.prototype.pilot_three_arm_store_draft import SyntheticThreeArmPilotStore
from src.prototype.study_v2 import RECOVERY_ACTIONS

CONTENT = Path(__file__).resolve().parents[1] / "docs" / "rct_candidate_v1"


def _unused_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _post(base: str, nonce: str, route: str, body: dict) -> dict:
    status, headers, raw = _request(
        base, "/preview/api/" + route, payload=body, nonce=nonce,
    )
    if status != 200 or headers.get("X-Synthetic-Only") != "1":
        raise AssertionError(
            "fictional HTTP " + route + " rejected: status " + str(status)
        )
    result = json.loads(raw)
    if type(result) is not dict:
        raise AssertionError("fictional HTTP endpoint returned non-object")
    return result


def _answer(action: dict) -> dict:
    kind = action["action"]
    if kind in ("QUESTION", "DROP_2"):
        question = action["question"]
        if "answer_id" in question or "correct" in question:
            raise AssertionError("question exposed private answer material")
        return {"choice_id": question["options"][0][0]}
    if kind == "MVAS":
        return {"rating": 30 if action["stage"] == "mvas_pre" else 45}
    if kind in RECOVERY_ACTIONS:
        return {"status": "completed"}
    raise AssertionError("unexpected fictional action category")


def run_disposable_http_fulljourney() -> dict:
    """Exercise 3 x 3 HTTP journeys plus independent read-only SQLite audit.

    No externally supplied hostname, study DB path, participant identifiers,
    policy selection or staff authorization can enter this function.
    """
    with TemporaryDirectory(prefix="ijcai-fictional-http-") as directory:
        db = Path(directory) / "fictional_browser_preview.sqlite3"
        store = SyntheticThreeArmPilotStore(
            db, items_path=CONTENT / "items.csv",
            resources_path=CONTENT / "resources.csv", simulations=41,
        )
        people = ensure_three_fictional_records(store)
        before_smoke = {arm: store.snapshot(pid) for arm, pid in people.items()}
        port = _unused_loopback_port()
        app = create_fictional_preview_app(store, port=port)
        server = make_server("127.0.0.1", port, app, threaded=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = "http://127.0.0.1:" + str(port)
            smoke = run_acceptance(base)
            if smoke["result"] != "PASS":
                raise AssertionError("read-only HTTP smoke acceptance failed")
            after_smoke = {
                arm: store.snapshot(pid) for arm, pid in people.items()
            }
            if before_smoke != after_smoke:
                raise AssertionError("read-only HTTP smoke changed study state")
            code, headers, html = _request(base, "/")
            if code != 200 or headers.get("X-Synthetic-Only") != "1":
                raise AssertionError("fictional page unavailable")
            match = re.search(
                r'<meta name="preview-nonce" content="([a-zA-Z0-9_-]{32,128})">',
                html.decode("utf-8"),
            )
            if match is None:
                raise AssertionError("fictional nonce missing")
            nonce = match.group(1)

            by_arm = {}
            replay_checks = 0
            for arm in ("A", "B", "C"):
                counts = Counter()
                for visit in (1, 2, 3):
                    if visit > 1:
                        advance_fictional_visit(store, arm)
                    for step in range(110):
                        state = _post(base, nonce, "status", {"arm": arm})
                        if state["session"] != visit:
                            raise AssertionError("HTTP status advanced wrong visit")
                        if state["stage"] in ("awaiting_visit", "complete"):
                            break
                        action = _post(base, nonce, "next", {"arm": arm})
                        if not action.get("synthetic_only") or not action.get(
                            "draft_content_not_approved"
                        ):
                            raise AssertionError("nonfictional public action")
                        if step % 17 == 0:
                            same = _post(base, nonce, "next", {"arm": arm})
                            if action != same:
                                raise AssertionError("pending HTTP action changed")
                        acknowledgement = _post(base, nonce, "rendered", {
                            "arm": arm, "action_id": action["action_id"],
                        })
                        if acknowledgement.get("accepted") is not True:
                            raise AssertionError("render acknowledgement rejected")
                        submission = {
                            "arm": arm, "action_id": action["action_id"],
                            "request_id": uuid.uuid4().hex,
                            "response": _answer(action),
                        }
                        completed = _post(base, nonce, "act", submission)
                        if (completed.get("accepted") is not True
                                or completed.get("replayed") is not False):
                            raise AssertionError("original HTTP action not accepted")
                        if step % 17 == 0:
                            again = _post(base, nonce, "act", submission)
                            if (again.get("accepted") is not True
                                    or again.get("replayed") is not True):
                                raise AssertionError("HTTP retry was not idempotent")
                            replay_checks += 1
                        counts[action["action"]] += 1
                    else:
                        raise AssertionError("fictional HTTP visit did not terminate")
                    end = _post(base, nonce, "status", {"arm": arm})
                    expected = "complete" if visit == 3 else "awaiting_visit"
                    if end["stage"] != expected or end["visits_finished"] != visit:
                        raise AssertionError("incorrect finished visit or stage")
                if counts["QUESTION"] != 87 or counts["MVAS"] != 6:
                    raise AssertionError("incomplete fictional assessment")
                recovery_count = sum(counts[k] for k in RECOVERY_ACTIONS)
                if recovery_count > 6 or (arm in ("B", "C") and recovery_count):
                    raise AssertionError("arm recovery allocation violated")
                by_arm[arm] = {
                    "visits": 3,
                    "questions": counts["QUESTION"],
                    "mvas": counts["MVAS"],
                    "recovery": recovery_count,
                }

            audit = audit_fictional_database(db)
            if audit["result"] != "PASS_SYNTHETIC_ONLY":
                raise AssertionError("independent fictional SQLite audit failed")
            return {
                "kind": "DISPOSABLE_LOOPBACK_HTTP_THREE_VISIT_ACCEPTANCE",
                "result": "PASS_SYNTHETIC_ONLY",
                "arms": by_arm,
                "completed_visits": 9,
                "replay_checks": replay_checks,
                "read_only_smoke": smoke["result"],
                "sqlite_audit": audit["result"],
                "sqlite_integrity": audit["sqlite_integrity"],
                "temporary_database_deleted_on_exit": True,
                "human_enrollment_authorized": False,
                "public_https_test": False,
                "real_browser_test": False,
                "production_concurrency_validation": False,
                "scientific_or_institutional_approval": False,
            }
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        result = run_disposable_http_fulljourney()
    except Exception as error:
        # Do not print internal paths, per-action contents or participant IDs.
        print(json.dumps({
            "kind": "DISPOSABLE_LOOPBACK_HTTP_THREE_VISIT_ACCEPTANCE",
            "result": "FAIL",
            "error_type": type(error).__name__,
            "human_enrollment_authorized": False,
        }, sort_keys=True))
        raise SystemExit(2) from None
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
