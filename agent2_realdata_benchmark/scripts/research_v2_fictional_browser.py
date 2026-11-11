"""Run isolated Research V2 fictional browser at http://127.0.0.1:8774.

The default demo uses an automatically deleted temporary SQLite directory.
An explicitly selected restricted local --state-dir retains ONLY fictional
data for resumability exercises. No public binding, human enrollment,
real email, or approved research content exists here.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from werkzeug.serving import make_server

from src.prototype.research_v2_crossover_fixture import FictionalCrossoverStore
from src.prototype.research_v2_reminder_outbox import SyntheticReminderOutbox
from src.prototype.research_v2_fictional_browser import (
    FIXTURES, FictionalV2Runtime, make_fictional_v2_app,
)
from src.prototype.research_v2_proposal import all_sequences


def new_fictional_runtime(directory: Path, *, clock=None,
                          resume_existing: bool = False) -> FictionalV2Runtime:
    """Offline-only fictional roster; never authenticate genuine students.

    A restart rotates each active invented credential using a hard-coded
    fictional operator authority. Real identity verification is absent.
    """
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("existing nonsymlink isolated directory required")
    study_path = directory / "fictional_crossover.sqlite3"
    contact_path = directory / "fictional_contact_outbox.sqlite3"
    exists_study, exists_contact = study_path.is_file(), contact_path.is_file()
    if exists_study != exists_contact:
        raise ValueError("partial fictional database pair; stop and inspect")
    if bool(resume_existing) != exists_study:
        raise ValueError(
            "explicit resume_existing must match existing fictional state")
    study = FictionalCrossoverStore(study_path)
    contacts = SyntheticReminderOutbox(contact_path)
    if resume_existing:
        # Do not attach a fictional preview to foreign or mixed-identity DBs.
        expected = {
            f"SYN_CROSSOVER_{label}": "".join(order)
            for label, order in zip(FIXTURES, all_sequences())
        }
        with study._transaction() as db:
            actual = {
                row["ref"]: row["sequence"]
                for row in db.execute("SELECT ref,sequence FROM fictional_learners")
            }
        with contacts._tx() as db:
            contact_rows = db.execute("SELECT ref,email FROM contacts").fetchall()
        if actual != expected or len(contact_rows) != len(FIXTURES) or any(
            row["ref"] not in {f"SYN_CONTACT_{label}" for label in FIXTURES}
            or not row["email"].lower().endswith(".test")
            for row in contact_rows
        ):
            raise ValueError("foreign or incomplete fictional roster rejected")
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    fixtures = {}
    for label, order in zip(FIXTURES, all_sequences()):
        ref = f"SYN_CROSSOVER_{label}"
        if not resume_existing:
            study.enroll_fictional(ref, order)
            token = study.issue_token(ref, now)
            contacts.register(
                f"SYN_CONTACT_{label}", f"fictional-{label.lower()}@example.test",
                locale=("en" if label in FIXTURES[:3] else "fr"),
                opted_in=True,
            )
        else:
            progress = study.redacted_progress(ref)
            contacts.inspect_redacted(f"SYN_CONTACT_{label}")
            if progress["finished"] or not progress["period_token_active"]:
                token = None
            else:
                token = study.rotate_token(
                    ref, now, contact_identity_verified=True,
                )
        fixtures[label] = (ref, token)
    return FictionalV2Runtime(study, fixtures, clock=clock, contacts=contacts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PRIVATE synthetic-only V2 three-period browser rehearsal")
    parser.add_argument("--port", type=int, default=8774)
    parser.add_argument(
        "--state-dir", type=Path,
        help="existing 0700 local directory for invented data only; "
             "otherwise use an automatically deleted temporary directory",
    )
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("unprivileged loopback port required")
    with ExitStack() as stack:
        if args.state_dir is None:
            root = Path(stack.enter_context(
                TemporaryDirectory(prefix="ijcai_v2_fictional_browser_")))
            persistent = False
        else:
            root = args.state_dir.expanduser()
            if (not root.is_dir() or root.is_symlink()
                    or root.stat().st_mode & 0o077):
                parser.error("state-dir must exist, not be a symlink, and be mode 0700")
            persistent = True
        existing = (root / "fictional_crossover.sqlite3").exists()
        runtime = new_fictional_runtime(
            root, resume_existing=existing,
        )
        app = make_fictional_v2_app(runtime, port=args.port)
        with make_server("127.0.0.1", args.port, app, threaded=True) as server:
            print(
                f"FICTIONAL ONLY: http://127.0.0.1:{args.port} "
                "(no human enrollment or real email)", flush=True,
            )
            print(
                "Fictional state persists in 0700 local directory."
                if persistent else
                "Six fictional learners; DB deleted on process exit.",
                flush=True,
            )
            server.serve_forever()


if __name__ == "__main__":
    main()
