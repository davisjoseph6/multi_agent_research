"""End-to-end single-SQLite-file synthetic RCT rehearsal (no network/humans).

In contrast to the prior two-file admission-learning bridge, this rehearsal
uses ONE fictional SQLite DB, including transactional consent, assignment,
learner creation, supervised visit starts and attendance finishes.

It is NOT the human study application: staff capabilities, time and consent
are fictional, there is no authentication service or participant web UI,
and the 95 draft questions/instrument lack independent approval.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import timedelta
import json
from pathlib import Path
import secrets
import shutil
from tempfile import TemporaryDirectory
import uuid

from scripts.pilot_integrated_synthetic_journey import (
    CONTENT, CONSENT_SHA256, REHEARSAL_START, SCREENING, _response, VirtualClock,
)
from src.prototype.pilot_unified_sqlite_synthetic import UnifiedSyntheticStudyStore
from src.prototype.study_v2 import RECOVERY_ACTIONS


def run_unified(*, participants: int = 9, simulations: int = 41) -> dict:
    if type(participants) is not int or not 9 <= participants <= 90:
        raise ValueError("fictional participants must be 9..90")
    if type(simulations) is not int or not 41 <= simulations <= 240:
        raise ValueError("fictional POMCP simulations must be 41..240")
    clock = VirtualClock()
    operator, auditor = secrets.token_bytes(32), secrets.token_bytes(32)
    with TemporaryDirectory(prefix="ijcai-single-sqlite-fictional-") as directory:
        path = Path(directory) / "fictional_admission.sqlite3"
        config = dict(
            consent_sha256=CONSENT_SHA256, screening_version=SCREENING,
            operator_key=operator, auditor_key=auditor, clock=clock,
            items_path=CONTENT / "items.csv",
            resources_path=CONTENT / "resources.csv",
            simulations=simulations,
        )
        study = UnifiedSyntheticStudyStore(path, **config)
        roster = []
        allocations = Counter()
        for _ in range(participants):
            invite = study.issue_invitation(operator)
            pid = invite["synthetic_pid"]
            study.screen(operator, pid, eligible=True, screening_version=SCREENING)
            result = study.consent_and_create(
                invite["private_invitation"], agreed=True,
                information_sha256=CONSENT_SHA256,
            )
            if not result["created"] or result["human_enrollment_authorized"]:
                raise AssertionError("fictional consent/learner creation failed")
            learner, arm = study.operator_lookup(operator, pid)
            allocations[arm] += 1
            if "arm" in study.admission.participant_status(invite["private_invitation"]):
                raise AssertionError("synthetic arm exposed to participant")
            roster.append((pid, learner, arm))
        if set(allocations) != {"A", "B", "C"}:
            raise AssertionError("fictional study missing a treatment arm")
        replays = 0
        activity = Counter()
        for visit in (1, 2, 3):
            start = REHEARSAL_START + timedelta(days=4 * (visit - 1))
            clock.value = start
            for pid, _, _ in roster:
                study.start_visit(operator, pid, visit)
            for _, learner, arm in roster:
                for step in range(65):
                    before = study.learning.snapshot(learner)
                    if before["stage"] in ("awaiting_visit", "complete"):
                        break
                    at = start + timedelta(minutes=step + 1)
                    offered = study.learning.next_action(learner, at=at)
                    if not offered.get("synthetic_only") or not offered.get(
                        "draft_content_not_approved"
                    ):
                        raise AssertionError("nonfictional action offered")
                    if step % 17 == 0:
                        if study.learning.next_action(learner, at=at) != offered:
                            raise AssertionError("idempotent pending action mismatch")
                    study.learning.mark_rendered(learner, offered["action_id"], at=at)
                    request = uuid.uuid4().hex
                    answer = _response(offered)
                    done = study.learning.submit(
                        learner, offered["action_id"], request, answer, at=at,
                    )
                    if not done["accepted"] or done["replayed"]:
                        raise AssertionError("first submission rejected")
                    if step % 17 == 0:
                        replay = study.learning.submit(
                            learner, offered["action_id"], request, answer, at=at,
                        )
                        if not replay["accepted"] or not replay["replayed"]:
                            raise AssertionError("retry was not idempotent")
                        replays += 1
                    activity[(arm, offered["action"])] += 1
                else:
                    raise AssertionError("synthetic visit did not finish")
                after = study.learning.snapshot(learner)
                if after["visits_finished"] != visit:
                    raise AssertionError("fictional learning visit completion missing")
            clock.value = start + timedelta(minutes=70)
            for pid, _, _ in roster:
                study.finish_visit(operator, pid, visit)
            if study.audit(auditor)["result"] != "PASS_SYNTHETIC_ONLY":
                raise AssertionError("single-file synthetic integrity audit failed")
            # Test interruption/restart from the same database between visits.
            study = UnifiedSyntheticStudyStore(path, **config)
        for pid, learner, arm in roster:
            snapshot = study.learning.snapshot(learner)
            scores = study.learning.scores(learner)
            if (snapshot["visits_finished"] != 3
                    or snapshot["arm"] != arm
                    or study.operator_lookup(operator, pid) != (learner, arm)
                    or snapshot["unique_practice_used"] != 55
                    or any(scores[form]["answered"] != target for form, target in
                           (("pretest", 16), ("practice", 55), ("posttest", 16)))):
                raise AssertionError("fictional learning/admission state mismatch")
        if any(activity[(arm, kind)] for arm in "BC" for kind in RECOVERY_ACTIONS):
            raise AssertionError("recovery leaked into a control arm")
        report = study.audit(auditor)
        if report["result"] != "PASS_SYNTHETIC_ONLY":
            raise AssertionError("single-file synthetic final audit failed")

        # A complete SQLite backup must preserve both admission + learner
        # schemas and links. Restore in a *different* temporary directory.
        # This tests local integrity, NOT encrypted/offsite DR arrangements.
        backup_path = Path(directory) / "fictional_admission_backup.sqlite3"
        backup = study.admission.backup(auditor, backup_path)
        restored_root = Path(directory) / "restored"
        restored_root.mkdir()
        restored_path = restored_root / "fictional_admission.sqlite3"
        shutil.copyfile(backup_path, restored_path)
        recovered = UnifiedSyntheticStudyStore(restored_path, **config)
        restored_report = recovered.audit(auditor)
        if (backup["result"] != "PASS_SYNTHETIC_BACKUP_ONLY"
                or restored_report["result"] != "PASS_SYNTHETIC_ONLY"
                or restored_report["fictional_learning_links"] != participants
                or restored_report["sqlite_integrity"] != "ok"):
            raise AssertionError("unified fictional backup/restore reconciliation failed")
        return {
            "kind": "DISPOSABLE_SINGLE_SQLITE_SYNTHETIC_RCT",
            "result": "PASS_SYNTHETIC_ONLY",
            "fictional_participants": participants,
            "fictional_completed_visits": 3 * participants,
            "fictional_questions": sum(activity[(arm, "QUESTION")] for arm in "ABC"),
            "fictional_mvas_records": sum(activity[(arm, "MVAS")] for arm in "ABC"),
            "fictional_replay_checks": replays,
            "allocation_by_arm": dict(sorted(allocations.items())),
            "sqlite_integrity": report["sqlite_integrity"],
            "unified_audit": report["result"],
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participants", type=int, default=9)
    parser.add_argument("--simulations", type=int, default=41)
    args = parser.parse_args()
    try:
        report = run_unified(participants=args.participants,
                             simulations=args.simulations)
    except Exception as error:
        print(json.dumps({
            "result": "FAIL", "error_type": type(error).__name__,
            "human_enrollment_authorized": False,
        }))
        raise SystemExit(2) from None
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
