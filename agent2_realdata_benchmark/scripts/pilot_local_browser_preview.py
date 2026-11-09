"""LOCAL-ONLY fictional IJCAI three-arm browser preview. NEVER use with humans.

Run from agent2_realdata_benchmark (inside WSL):
    python -m scripts.pilot_local_browser_preview
    # Then open http://localhost:8765/ in the Windows browser.

After completing Visit 1 for a selected fictional arm, run in a SEPARATE
WSL shell:
    python -m scripts.pilot_local_browser_preview --advance-arm A

This uses virtual study time, draft unapproved content and a wholly separate
synthetic SQLite file. It is NOT a live RCT service or authorization gateway.
Never reverse proxy / expose this demonstration on a public interface.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from werkzeug.serving import make_server

from src.prototype.pilot_local_browser_preview import (
    advance_fictional_visit, create_fictional_preview_app,
    ensure_three_fictional_records,
)
from src.prototype.pilot_three_arm_store_draft import SyntheticThreeArmPilotStore

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "docs" / "rct_candidate_v1"
DEFAULT_DB = (
    Path.home() / ".cache" / "ijcai2027_fictional_browser_preview"
    / "fictional_browser_preview.sqlite3"
)


def main():
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        raise SystemExit("Refusing to run the fictional browser preview as root")
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help="fictional-only SQLite path, never a real study database")
    parser.add_argument("--advance-arm", choices=("A", "B", "C"),
                        help="offline-only: start next fictional visit then exit")
    options = parser.parse_args()
    if options.db.name != "fictional_browser_preview.sqlite3":
        parser.error("refuse database not explicitly named fictional_browser_preview.sqlite3")
    if not 1024 <= options.port <= 65535:
        parser.error("port must be unprivileged (1024..65535)")
    store = SyntheticThreeArmPilotStore(
        options.db, items_path=CONTENT / "items.csv",
        resources_path=CONTENT / "resources.csv",
        simulations=41,  # fast fictional preview; NOT the 240-simulation RCT config
    )
    ensure_three_fictional_records(store)
    if options.advance_arm:
        outcome = advance_fictional_visit(store, options.advance_arm)
        print("Offline fictional visit advanced:", options.advance_arm, outcome)
        return
    app = create_fictional_preview_app(store, port=options.port)
    print("FICTIONAL / UNAPPROVED / LOCAL-ONLY — NO REAL STUDENT DATA")
    print("Windows/WSL browser:", "http://localhost:" + str(options.port) + "/")
    print("Press Ctrl+C to stop. NEVER expose this service through a reverse proxy.")
    server = make_server("127.0.0.1", options.port, app, threaded=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
