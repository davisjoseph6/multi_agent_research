"""Private, unified fictional three-arm browser (NEVER for real students).

Binds 127.0.0.1 only. Use an SSH tunnel for private remote viewing;
do not expose through Caddy/Nginx/DNS/public firewall. No human enrollment,
verified staff identity, student consent or approved measurements.

Run from agent2_realdata_benchmark:
    python -m scripts.pilot_unified_fictional_browser --port 8767
    python -m scripts.pilot_unified_fictional_browser --advance-fixture F1
    python -m scripts.pilot_unified_fictional_browser --finish-fixture F1
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path
import secrets

from werkzeug.serving import make_server

from src.prototype.pilot_unified_sqlite_synthetic import UnifiedSyntheticStudyStore
from src.prototype.pilot_unified_fictional_browser import (
    FixtureClock, advance_unified_fictional_visit,
    create_unified_fictional_browser_app, ensure_unified_fictional_roster,
)

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "docs" / "rct_candidate_v1"
DEFAULT_DB = (
    Path.home() / ".cache" / "ijcai2027_unified_fictional_browser"
    / "fictional_admission.sqlite3"
)
SCREENING_VERSION = "UNIFIED_BROWSER_SYNTHETIC_SCREENING_V1"
CONSENT_HASH = sha256(b"UNAPPROVED_SYNTHETIC_BROWSER_INFORMATION").hexdigest()


def open_synthetic_study(path: Path, *,
                         question_anchored_recovery: bool = False):
    """Create isolated test-only capabilities for the current process."""
    clock = FixtureClock()
    operator = secrets.token_bytes(32)
    auditor = secrets.token_bytes(32)
    store = UnifiedSyntheticStudyStore(
        path, consent_sha256=CONSENT_HASH,
        screening_version=SCREENING_VERSION,
        operator_key=operator, auditor_key=auditor, clock=clock,
        items_path=CONTENT / "items.csv",
        resources_path=CONTENT / "resources.csv",
        simulations=41,
        question_anchored_recovery=question_anchored_recovery,
    )
    roster = ensure_unified_fictional_roster(
        store, operator, screening_version=SCREENING_VERSION,
        information_sha256=CONSENT_HASH,
    )
    return store, roster, operator, clock


def main() -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        raise SystemExit("Refusing to run fictional browser as root")
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB,
        help="an isolated fictional_admission.sqlite3, never real study data",
    )
    parser.add_argument(
        "--question-anchored-recovery", action="store_true",
        help="unapproved last-incorrect-question targeting; requires a fresh fictional DB",
    )
    offline = parser.add_mutually_exclusive_group()
    offline.add_argument("--advance-fixture", choices=("F1", "F2", "F3"))
    offline.add_argument("--finish-fixture", choices=("F1", "F2", "F3"))
    args = parser.parse_args()
    if args.db.name != "fictional_admission.sqlite3" or args.db.is_symlink():
        parser.error("only non-symlink fictional_admission.sqlite3 is supported")
    if type(args.port) is not int or not 1024 <= args.port <= 65535:
        parser.error("unprivileged preview port 1024..65535 required")
    if args.advance_fixture or args.finish_fixture:
        if not args.db.is_file():
            parser.error("an existing fictional database is required for offline visit actions")
    study, roster, operator, clock = open_synthetic_study(
        args.db, question_anchored_recovery=args.question_anchored_recovery,
    )
    if args.advance_fixture or args.finish_fixture:
        fixture = args.advance_fixture or args.finish_fixture
        report = advance_unified_fictional_visit(
            study, operator, fixture, roster, clock,
            finish_final=bool(args.finish_fixture),
        )
        print("Synthetic-only offline visit:", report)
        return

    app = create_unified_fictional_browser_app(
        study, operator, roster, port=args.port,
    )
    print("UNIFIED FICTIONAL STUDY / NOT FOR HUMAN ENROLLMENT")
    print("Private loopback browser: http://127.0.0.1:" + str(args.port) + "/")
    print("No recruitment, consent, external auth or real student data.")
    server = make_server("127.0.0.1", args.port, app, threaded=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
