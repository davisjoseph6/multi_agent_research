"""Restricted real-POMCP fictional operator demo; NEVER a live RCT release."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path

from scripts.rct_candidate_cli import engine_from, load_settings
from src.prototype.rct_candidate_api import create_app


def validated_settings(settings):
    settings = Path(settings).resolve()
    cfg, bundle, release = load_settings(settings)
    hosts = cfg.get("allowed_hosts", [])
    if cfg.get("mode") != "operator_demo" or release is not None:
        raise ValueError("operator demo requires separate operator_demo settings and no release evidence")
    if cfg.get("behind_one_local_tls_proxy") is not True:
        raise ValueError("operator demo requires a same-host trusted TLS reverse proxy")
    if len(hosts) != 1 or hosts[0] in ("localhost", "127.0.0.1", "::1") or hosts[0].endswith(".invalid"):
        raise ValueError("set the real, single demonstration hostname first")
    return settings, cfg


def seed(*, settings, database, output):
    settings, _ = validated_settings(settings)
    database = Path(database).resolve()
    output = Path(output).resolve()
    if database == output or database.exists() or output.exists():
        raise FileExistsError("fresh database and private invitation output required; never overwrite")
    if database.parent == output.parent:
        # Permitted: both must be in a private operational directory.
        pass
    database.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    engine = engine_from(settings, database)
    invitations = [engine.issue_invitation(lifetime_hours=24) for _ in range(9)]
    for invite in invitations:
        answer = engine.enroll(
            invite["invitation"], agreed=True,
            information_version=engine.bundle.hashes["information"]
        )
        if not answer["accepted"]:
            raise AssertionError("fictional enrollment failed")
    outcomes = engine.export_private()["outcomes"]
    arm_by_pid = {person["pid"]: person["assigned_arm"] for person in outcomes}
    counts = Counter(arm_by_pid[invite["participant_id"]] for invite in invitations)
    if set(counts) != {"A", "B", "C"} or min(counts.values()) < 2:
        raise AssertionError("unexpected demonstration allocation")
    records = [
        {"arm": arm_by_pid[invite["participant_id"]],
         "invitation": invite["invitation"], "fictional": True}
        for invite in invitations
    ]
    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"purpose": "PRIVATE_FICTIONAL_OPERATOR_DEMO_NOT_RECRUITMENT",
                   "candidate_sha256": engine.release["candidate_sha256"],
                   "invitations": records}, f, indent=2)
        f.write("\n")
    output.chmod(0o600)
    return {
        "status": "PRIVATE_FICTIONAL_DEMO_PREPARED",
        "fictional_enrolled": len(invitations),
        "arm_counts": {arm: counts[arm] for arm in "ABC"},
        "invitation_tokens_printed": False,
        "human_enrollment_authorized": False,
        "database_reused": False,
    }


def make_demo_app():
    """Gunicorn factory; bind ONLY to 127.0.0.1 behind one reviewed TLS proxy."""
    settings = os.environ["RCT_DEMO_SETTINGS"]
    database = Path(os.environ["RCT_DEMO_DATABASE"]).resolve()
    settings, _ = validated_settings(settings)
    if not database.is_file():
        raise FileNotFoundError("seed the fictional database offline before starting Gunicorn")
    engine = engine_from(settings, database)
    if engine.mode != "operator_demo":
        raise ValueError("refusing to expose any non-demo engine")
    return create_app(engine)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(seed(settings=args.settings, database=args.db, output=args.out), indent=2))


if __name__ == "__main__":
    main()
