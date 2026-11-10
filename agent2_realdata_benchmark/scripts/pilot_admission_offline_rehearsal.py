"""Run a disposable synthetic admission and three-visit staff-control rehearsal.

Exercises isolated admission/screening/consent/secret assignment/attendance and
backup/restore controls. Does NOT present learning activities, collect real
people, open a web server, authorize staff, or approve a research study.

From agent2_realdata_benchmark:
    python -m scripts.pilot_admission_offline_rehearsal --participants 30
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import secrets
import shutil
from tempfile import TemporaryDirectory

from src.prototype.pilot_admission_controls_draft import SyntheticAdmissionStore

SCREENING_VERSION = "SYNTHETIC_SCREENING_DRAFT_V1"
CONSENT_HASH = sha256(b"FICTIONAL_UNAPPROVED_INFORMATION").hexdigest()


class FixtureClock:
    def __init__(self):
        self.current = datetime(2026, 11, 20, 9, tzinfo=timezone.utc)

    def __call__(self):
        return self.current

    def advance(self, **kwargs):
        self.current += timedelta(**kwargs)


def run_rehearsal(*, participants: int = 30) -> dict:
    if type(participants) is not int or not 3 <= participants <= 90:
        raise ValueError("participants must be 3..90 synthetic fixtures")
    clock = FixtureClock()
    operator_key, auditor_key = secrets.token_bytes(32), secrets.token_bytes(32)
    with TemporaryDirectory(prefix="ijcai-synthetic-admission-") as directory:
        root = Path(directory)
        config = dict(
            consent_sha256=CONSENT_HASH,
            screening_version=SCREENING_VERSION,
            operator_key=operator_key,
            auditor_key=auditor_key,
            clock=clock,
        )
        store = SyntheticAdmissionStore(
            root / "fictional_admission.sqlite3", **config,
        )
        fixtures = []
        for _ in range(participants):
            invite = store.issue_invitation(operator_key)
            store.screen(
                operator_key, invite["synthetic_pid"],
                eligible=True, screening_version=SCREENING_VERSION,
            )
            result = store.consent(
                invite["private_invitation"], agreed=True,
                information_sha256=CONSENT_HASH,
            )
            if not result["accepted"] or not result["created"]:
                raise AssertionError("fictional enrollment not created")
            fixtures.append(invite)

        for visit in (1, 2, 3):
            if visit > 1:
                clock.advance(days=4)
            for fixture in fixtures:
                store.start_visit(operator_key, fixture["synthetic_pid"], visit)
            clock.advance(minutes=30)
            for fixture in fixtures:
                store.finish_visit(operator_key, fixture["synthetic_pid"], visit)

        report = store.audit(auditor_key)
        if (report["result"] != "PASS_SYNTHETIC_ONLY"
                or report["allocated"] != participants):
            raise AssertionError("synthetic admission audit failed")
        for fixture in fixtures:
            status = store.participant_status(fixture["private_invitation"])
            if (status["visits_finished"] != 3 or status["visits_started"] != 3
                    or status["status"] != "active" or "arm" in status):
                raise AssertionError("synthetic journey incomplete or arm disclosed")

        backup_path = root / "fictional_admission_backup.sqlite3"
        copied = store.backup(auditor_key, backup_path)
        restored_dir = root / "restored"
        restored_dir.mkdir()
        restored_path = restored_dir / "fictional_admission.sqlite3"
        shutil.copyfile(backup_path, restored_path)
        restored = SyntheticAdmissionStore(restored_path, **config)
        after = restored.audit(auditor_key)
        if after["result"] != "PASS_SYNTHETIC_ONLY" or after["allocated"] != participants:
            raise AssertionError("synthetic backup restore did not preserve state")
        return {
            "kind": "DISPOSABLE_SYNTHETIC_ADMISSION_THREE_VISIT_REHEARSAL",
            "result": "PASS_SYNTHETIC_ONLY",
            "fictional_participants": participants,
            "fictional_started_visits": participants * 3,
            "fictional_completed_visits": participants * 3,
            "concealed_assignment_records": report["allocated"],
            "randomized_block_count": report["block_count"],
            "audit": report["result"],
            "backup": copied["result"],
            "restore_audit": after["result"],
            "sqlite_integrity": after["sqlite_integrity"],
            "temporary_files_deleted_on_exit": True,
            "human_enrollment_authorized": False,
            "staff_identity_verified": False,
            "external_review_or_approval": False,
            "no_network_requests": True,
            "no_real_participant_data": True,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participants", type=int, default=30)
    args = parser.parse_args()
    try:
        result = run_rehearsal(participants=args.participants)
    except Exception as error:
        print(json.dumps({
            "kind": "DISPOSABLE_SYNTHETIC_ADMISSION_THREE_VISIT_REHEARSAL",
            "result": "FAIL",
            "error_type": type(error).__name__,
            "human_enrollment_authorized": False,
        }))
        raise SystemExit(2) from None
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
