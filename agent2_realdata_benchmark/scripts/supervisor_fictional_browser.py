"""Launch the isolated supervisor 3-arm parallel fictional RCT browser.

Binds exclusively to 127.0.0.1. Every database contains invented identities
and .test email addresses. This process has NO real student recruitment,
SMTP, actual consent, real credentials or network release.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from werkzeug.serving import make_server

from src.prototype.supervisor_content import SupervisorBank
from scripts.supervisor_consent_pdf import build_pdfs
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore
from src.prototype.supervisor_fictional_web import (
    FictionalSupervisorRuntime, FictionalSupervisorClock,
    make_supervisor_fictional_app,
)

BANK = Path(__file__).resolve().parents[1] / "data" / "supervisor_20261111"


def new_supervisor_fictional_runtime(folder: Path, *, clock=None):
    bank = SupervisorBank(BANK)
    study = SupervisorSyntheticStore(folder,bank=bank)
    return FictionalSupervisorRuntime(
        study,clock=clock or FictionalSupervisorClock(),
    )


def main() -> None:
    parser=argparse.ArgumentParser(
        description="PRIVATE supervisor parallel-group fictional RCT preview")
    parser.add_argument("--port",type=int,default=8783)
    args=parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("unprivileged loopback port required")
    # PDFs are generated locally from the versioned, unmodified Annex HTML
    # before the preview accepts requests. Missing PDF tooling fails closed.
    content=Path(__file__).resolve().parents[1]/"content"/"consent"
    build_pdfs(content)
    with TemporaryDirectory(prefix="ijcai_supervisor_fictional_") as root:
        runtime=new_supervisor_fictional_runtime(Path(root))
        app=make_supervisor_fictional_app(runtime,port=args.port)
        with make_server("127.0.0.1",args.port,app,threaded=True) as server:
            print(
                "SUPERVISOR FICTIONAL THREE-ARM PREVIEW ONLY: "
                f"http://127.0.0.1:{args.port}",
                flush=True,
            )
            print(
                "Synthetic F1/F2/F3 only; no live email or student enrollment. "
                "Temporary DB removed on exit.",
                flush=True,
            )
            server.serve_forever()


if __name__=="__main__":
    main()
