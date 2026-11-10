"""Mechanical validator for a *fictional* 30-person single-SQLite VPS run.

No HTTP services, no credentials, and no human enrollment are authorized.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CONTRACT = {
    "kind": "DISPOSABLE_SINGLE_SQLITE_SYNTHETIC_RCT",
    "result": "PASS_SYNTHETIC_ONLY",
    "fictional_participants": 30,
    "fictional_completed_visits": 90,
    "fictional_questions": 2610,
    "fictional_mvas_records": 180,
    "sqlite_integrity": "ok",
    "unified_audit": "PASS_SYNTHETIC_ONLY",
    "single_sqlite_file": True,
    "atomic_provisioning_and_visit_boundaries": True,
    "crash_restart_reopen_checks": 3,
    "unified_backup_restore": "PASS_SYNTHETIC_ONLY",
    "offsite_encrypted_recovery_verified": False,
    "data_deleted_on_exit": True,
    "no_network_requests": True,
    "human_enrollment_authorized": False,
    "staff_authentication_real": False,
    "consent_or_instrument_reviewed": False,
    "independent_security_review": False,
}


def validate(data: object) -> dict:
    if type(data) is not dict:
        raise ValueError("fictional report must be an object")
    for key, value in CONTRACT.items():
        if type(data.get(key)) is not type(value) or data[key] != value:
            raise ValueError("fictional acceptance mismatch: " + key)
    arms = data.get("allocation_by_arm")
    if (type(arms) is not dict or set(arms) != {"A", "B", "C"}
            or any(type(n) is not int or n < 1 for n in arms.values())
            or sum(arms.values()) != 30
            or max(arms.values()) - min(arms.values()) > 3):
        raise ValueError("fictional randomized block count out of bounds")
    replay = data.get("fictional_replay_checks")
    if type(replay) is not int or replay < 30:
        raise ValueError("fictional idempotency coverage incomplete")
    return {
        "result": "PASS_SYNTHETIC_ONLY",
        "checked": len(CONTRACT) + 2,
        "human_enrollment_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, required=True)
    args = parser.parse_args()
    if args.path.is_symlink() or not args.path.is_file():
        parser.exit(2, "non-symlink synthetic report required\n")
    try:
        report = json.loads(args.path.read_text(encoding="utf-8"))
        result = validate(report)
    except (ValueError, OSError) as error:
        parser.exit(2, f"synthetic acceptance rejected: {error}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
