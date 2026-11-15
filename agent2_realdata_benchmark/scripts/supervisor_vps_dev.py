"""Ephemeral localhost harness for real Chromium operational UI acceptance.

Not a hosting option, not production, and never accepts a real email. The
same Flask API as the VPS app is exercised with reserved .example identities.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from werkzeug.serving import make_server

from src.prototype.supervisor_content import SupervisorBank
from src.prototype.supervisor_operational_intake import OperationalIntake
from src.prototype.supervisor_synthetic_store import SupervisorSyntheticStore
from src.prototype.supervisor_vps_web import make_supervisor_vps_app


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=8792)
    a=parser.parse_args()
    if not 1024<=a.port<=65535:
        parser.error("private unprivileged port required")
    bank=SupervisorBank(Path(__file__).resolve().parents[1]/
                        "data"/"supervisor_20261111")
    with TemporaryDirectory(prefix="supervisor_vps_test_") as root:
        store=SupervisorSyntheticStore(Path(root),bank=bank,operational=True)
        intake=OperationalIntake(store,programs=("Test student program",))
        tokens={}
        for fixture in ("F1","F2","F3"):
            tokens[fixture]=intake.issue(
                f"private-{fixture.lower()}@example.example",
                at=datetime.now(timezone.utc),allow_example=True,
            )
        app=make_supervisor_vps_app(
            intake,hostname="demo.selfhealing-edu.fr",
            proxy_mode=False,release_mode="staging",
        )
        with make_server("127.0.0.1",a.port,app,threaded=True) as server:
            print("TEST_INVITES="+json.dumps(tokens),flush=True)
            print(f"TEST_ONLY_LOOPBACK=http://127.0.0.1:{a.port}/study/",
                  flush=True)
            server.serve_forever()


if __name__=="__main__":
    main()
