"""Read-only mechanical validator for the isolated VPS synthetic batch report.

Accepts *only* the known 30-fictional-participant, 41-simulation report
contract. This cannot certify an institutional human-study application.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


CONTRACT = {
    "kind": "DISPOSABLE_SYNTHETIC_ADMISSION_LEARNING_CROSSCHECK",
    "result": "PASS_SYNTHETIC_ONLY",
    "fictional_participants": 30,
    "fictional_completed_visits": 90,
    "fictional_questions": 2610,
    "fictional_mvas_records": 180,
    "admission_audit": "PASS_SYNTHETIC_ONLY",
    "learning_audit": "PASS_SYNTHETIC_ONLY",
    "no_client_supplied_arm": True,
    "no_network_requests": True,
    "temporary_stores_deleted": True,
    "human_enrollment_authorized": False,
    "staff_authentication_real": False,
    "consent_or_measurement_validated": False,
    "cross_database_atomicity": False,
    "independent_security_or_ethics_approval": False,
}


class SyntheticReportError(ValueError):
    """A report does not satisfy the private fictional acceptance contract."""


def check_report(data: object) -> dict:
    if type(data) is not dict:
        raise SyntheticReportError("synthetic report must be an object")
    for key, value in CONTRACT.items():
        if type(data.get(key)) is not type(value) or data.get(key) != value:
            raise SyntheticReportError("unexpected synthetic report invariant: " + key)
    counts = data.get("allocated_by_arm")
    if (type(counts) is not dict or set(counts) != {"A", "B", "C"}
            or any(type(n) is not int or n < 1 for n in counts.values())
            or sum(counts.values()) != 30
            or max(counts.values()) - min(counts.values()) > 3):
        # A 30-person sample can stop partway through blocks of six or nine.
        raise SyntheticReportError("invalid fictional randomized-block allocation")
    replays = data.get("fictional_replay_checks")
    if type(replays) is not int or replays < 30:
        raise SyntheticReportError("fictional retry coverage is insufficient")
    return {"result": "PASS_SYNTHETIC_ONLY", "checked": len(CONTRACT) + 2,
            "human_enrollment_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True, type=Path)
    args = parser.parse_args()
    if args.path.is_symlink() or not args.path.is_file():
        parser.exit(2, "synthetic report file must exist and not be a symlink\n")
    try:
        data = json.loads(args.path.read_text(encoding="utf-8"))
        result = check_report(data)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"synthetic report rejected: {error}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
