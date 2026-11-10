"""Create fresh Arm A/B/C invitations IN an existing fictional operator demo.

This registers a new randomized cohort in the SAME database used by the
running HTTPS operator demo. It never resets that database or rotates
old invitations, and it never prints bearer credentials to stdout.

IMPORTANT: operator_demo is NOT a human study and cannot recruit students.
Run only with verified --settings/--db for the ACTUAL deployed service.
The host must match --expected-host. Store outputs outside web roots.

Example, from the benchmark directory on a verified operator-demo VPS:

  python -m scripts.rct_operator_demo_new_arm_tokens \
    --settings /absolute/path/settings_operator_demo_LOCAL.json \
    --db /var/lib/ijcai-rct-demo/fictional.sqlite3 \
    --expected-host demo.selfhealing-edu.fr \
    --out /var/lib/ijcai-rct-demo/demo_arm_tokens_PRIVATE_001.json

Nine fictional participants are enrolled atomically so random-block
assignment naturally provides all arms. Three invitations (one per arm)
are selected for the demonstration; the other six are preserved only in
the private output as unused reserve credentials. The file is owner-only.
No credentials are displayed in logs, terminals, URLs, GitHub or chat.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import stat
import tempfile
import time
import uuid

from scripts.rct_candidate_cli import engine_from
from scripts.rct_operator_demo import validated_settings
from src.prototype.rct_candidate import stamp
from src.prototype.rct_candidate_content import canonical
from src.prototype.study_v2 import CONCEPTS, RecoveryStatus


def _location_checks(database: Path, output: Path) -> tuple[Path, Path]:
    """Reject nonexisting study DB, symlinks, public-ish output directories."""
    if not database.is_absolute() or not output.is_absolute():
        raise ValueError("absolute database and output paths are required")
    if (database.name != "fictional.sqlite3" or not database.is_file()
            or database.is_symlink()
            or output.exists() or output.is_symlink()
            or database.parent.resolve() != output.parent.resolve()
            or database.parent.is_symlink() or output.parent.is_symlink()
            or bool(output.parent.stat().st_mode & stat.S_IWOTH)):
        raise ValueError(
            "use the existing nonsymlink fictional.sqlite3 and a NEW "
            "private output in its non-world-writable parent directory"
        )
    return database, output


def issue_fresh_demo_arm_tokens(
    *,
    settings: str | Path,
    database: str | Path,
    output: str | Path,
    expected_host: str,
    lifetime_hours: int = 24,
) -> dict:
    """Atomic SQL registration; privately persisted exact A/B/C invitations.

    A private .pending file is fsynced BEFORE commit to avoid an unrecorded
    bearer credential if writing fails. Its final name is linked with
    exclusive-create semantics only AFTER commit; on rare publish failure
    the pending file is left private for operator recovery.
    """
    settings, config = validated_settings(settings)
    if (type(expected_host) is not str
            or expected_host != "demo.selfhealing-edu.fr"
            or config["allowed_hosts"] != [expected_host]):
        raise ValueError("verified operator-demo hostname mismatch")
    if type(lifetime_hours) is not int or not 1 <= lifetime_hours <= 720:
        raise ValueError("bounded fictional invitation lifetime of 1..720 hours required")
    database, output = _location_checks(Path(database), Path(output))
    engine = engine_from(settings, database)
    if engine.mode != "operator_demo":
        raise ValueError("refusing any nonfictional or non-operator-demo database")

    # A valid operator-demo database is pre-seeded with fictional records.
    # Never initialize a new DB here or operate on a human study.
    with engine._transaction() as conn:
        existing = conn.execute(
            "SELECT COUNT(*) AS n FROM rct_people"
        ).fetchone()["n"]
        nonsynthetic = conn.execute(
            "SELECT COUNT(*) AS n FROM rct_people WHERE pid NOT LIKE 'SYN_%'"
        ).fetchone()["n"]
        if existing < 9 or nonsynthetic:
            raise ValueError("existing seeded, exclusively synthetic demo DB required")

    old_umask = os.umask(0o077)
    try:
        fd, pending_name = tempfile.mkstemp(
            prefix=".pending_demo_arm_tokens_", suffix=".json",
            dir=output.parent,
        )
    finally:
        os.umask(old_umask)

    committed = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as private:
            os.fchmod(private.fileno(), 0o600)
            with engine._transaction() as conn:
                records = []
                now = time.time()
                for _ in range(9):
                    token = secrets.token_urlsafe(32)
                    pid = "SYN_" + uuid.uuid4().hex
                    conn.execute(
                        "INSERT INTO rct_people "
                        "(pid,token_hash,expires,status,state,consent_at,consent_version) "
                        "VALUES(?,?,?,'invited',NULL,NULL,NULL)",
                        (pid, sha256(token.encode("utf-8")).hexdigest(),
                         now + lifetime_hours * 3600),
                    )
                    engine._event(conn, pid, "invitation_issued", mode="operator_demo")
                    arm = engine._allocate(conn, pid)
                    state = {
                        "arm": arm, "stage": "pretest", "session": 0,
                        "index": 0, "mastery": {c: .2 for c in CONCEPTS},
                        "used": [], "recovery": asdict(RecoveryStatus()),
                        "pending": None,
                    }
                    conn.execute(
                        "UPDATE rct_people SET status='active',state=?,"
                        "consent_at=?,consent_version=? WHERE pid=?",
                        (canonical(state), stamp(),
                         engine.bundle.hashes["information"], pid),
                    )
                    engine._event(
                        conn, pid, "enrolled", arm=arm,
                        information_version=engine.bundle.hashes["information"],
                        candidate_sha256=engine.release["candidate_sha256"],
                    )
                    records.append({
                        "arm": arm, "participant_id": pid,
                        "invitation": token, "fictional": True,
                    })
                counts = Counter(record["arm"] for record in records)
                if set(counts) != {"A", "B", "C"} or min(counts.values()) < 1:
                    raise ValueError("expected all three randomized fictional arms")
                chosen = {arm: next(
                    record for record in records if record["arm"] == arm
                ) for arm in "ABC"}
                chosen_ids = {record["participant_id"] for record in chosen.values()}
                reserve = [
                    record for record in records
                    if record["participant_id"] not in chosen_ids
                ]
                json.dump({
                    "purpose": "PRIVATE_FICTIONAL_OPERATOR_DEMO_NEW_ARM_TOKENS",
                    "host": expected_host,
                    "mode": "operator_demo",
                    "human_enrollment_authorized": False,
                    "created_at": stamp(),
                    "lifetime_hours": lifetime_hours,
                    "candidate_sha256": engine.release["candidate_sha256"],
                    "tokens_by_arm": chosen,
                    "reserve_fictional_invitations": reserve,
                }, private, indent=2)
                private.write("\n")
                private.flush()
                os.fsync(private.fileno())
                # SQLite commits only after this output is safely written.
            committed = True
        # os.link fails instead of overwriting an existing output created
        # in a race. The temporary private file can be recovered if needed.
        os.link(pending_name, output)
        os.unlink(pending_name)
        output.chmod(0o600)
    except BaseException:
        if not committed and os.path.exists(pending_name):
            os.unlink(pending_name)
        raise

    return {
        "result": "NEW_FICTIONAL_ARM_TOKENS_REGISTERED",
        "host": expected_host,
        "created_fictional_records": 9,
        "new_arm_counts": {arm: counts[arm] for arm in "ABC"},
        "selected_demo_arms": ["A", "B", "C"],
        "private_file": str(output),
        "tokens_printed": False,
        "existing_tokens_rotated": False,
        "existing_database_reset": False,
        "human_enrollment_authorized": False,
    }


def main() -> None:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--lifetime-hours", type=int, default=24)
    args = parser.parse_args()
    report = issue_fresh_demo_arm_tokens(
        settings=args.settings, database=args.db, output=args.out,
        expected_host=args.expected_host,
        lifetime_hours=args.lifetime_hours,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
