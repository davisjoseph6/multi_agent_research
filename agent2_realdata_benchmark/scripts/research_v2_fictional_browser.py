"""Run isolated Research V2 fictional browser at http://127.0.0.1:8774.

The demo creates six invented learner records in a temporary SQLite DB.
Closing the process removes the demo state. No public binding, human
enrollment, real email, or approved research content exists here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from werkzeug.serving import make_server

from src.prototype.research_v2_crossover_fixture import FictionalCrossoverStore
from src.prototype.research_v2_fictional_browser import (
    FIXTURES, FictionalV2Runtime, make_fictional_v2_app,
)
from src.prototype.research_v2_proposal import all_sequences


def new_fictional_runtime(directory: Path, *, clock=None) -> FictionalV2Runtime:
    """Operator-only seeded roster: one fictional learner per arm permutation."""
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError("existing isolated directory required")
    study = FictionalCrossoverStore(directory / "fictional_crossover.sqlite3")
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    fixtures = {}
    for label, order in zip(FIXTURES, all_sequences()):
        ref = f"SYN_CROSSOVER_{label}"
        study.enroll_fictional(ref, order)
        token = study.issue_token(ref, now)
        fixtures[label] = (ref, token)
    return FictionalV2Runtime(study, fixtures, clock=clock)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PRIVATE synthetic-only V2 three-period browser rehearsal")
    parser.add_argument("--port", type=int, default=8774)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("unprivileged loopback port required")
    with TemporaryDirectory(prefix="ijcai_v2_fictional_browser_") as temp:
        runtime = new_fictional_runtime(Path(temp))
        app = make_fictional_v2_app(runtime, port=args.port)
        with make_server("127.0.0.1", args.port, app, threaded=True) as server:
            print(
                f"FICTIONAL ONLY: http://127.0.0.1:{args.port} "
                "(no human enrollment or real email)", flush=True,
            )
            print(
                "Six pre-enrolled fake learners; DB deleted on process exit.",
                flush=True,
            )
            server.serve_forever()


if __name__ == "__main__":
    main()
