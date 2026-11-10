"""Full offline integration of synthetic admission + actual A/B/C learning.

Deliberately disconnected from Flask, VPS, human RCT, public networks and
identity stores. The two SQLite stores live only under TemporaryDirectory.
Separate SQLite transactions are NOT production-grade cross-DB atomicity.
Staff and clock are offline fixtures, not authenticated human supervisors.

Run from agent2_realdata_benchmark:
    python -m scripts.pilot_integrated_synthetic_journey --participants 9
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory
import uuid

from src.prototype.pilot_admission_controls_draft import SyntheticAdmissionStore
from src.prototype.pilot_three_arm_store_draft import SyntheticThreeArmPilotStore
from src.prototype.study_v2 import RECOVERY_ACTIONS

CONTENT = Path(__file__).resolve().parents[1] / "docs" / "rct_candidate_v1"
CONSENT_SHA256 = sha256(b"FIXTIONAL_INFORMATION_NOT_APPROVED").hexdigest()
SCREENING = "DISPOSABLE_SYNTHETIC_SCREENING_V1"
REHEARSAL_START = datetime(2026, 11, 20, 9, tzinfo=timezone.utc)
STAFF_FLAGS = {
    "offline_staff_authorized": True,
    "synthetic_release_authorized": True,
}


class VirtualClock:
    def __init__(self):
        self.value = REHEARSAL_START

    def __call__(self):
        return self.value


def _response(action: dict) -> dict:
    kind = action["action"]
    if kind in ("QUESTION", "DROP_2"):
        q = action["question"]
        if "answer_id" in q or "correct" in q:
            raise AssertionError("public item leaked its private answer")
        return {"choice_id": q["options"][0][0]}
    if kind == "MVAS":
        return {"rating": 30 if action["stage"] == "mvas_pre" else 45}
    if kind in RECOVERY_ACTIONS:
        return {"status": "completed"}
    raise AssertionError("unexpected synthetic policy action")


def run_integrated(*, participants: int = 9, simulations: int = 41) -> dict:
    """Run and delete two unrelated private fictional SQLite stores.

    The bridge is explicitly staff-side only. The public status API
    exposes no arm; the actual learning policy comes from the hidden,
    staff-only persisted randomized slot, never from the candidate.
    """
    if type(participants) is not int or not 9 <= participants <= 90:
        raise ValueError("participants must be 9..90 fictional records")
    if type(simulations) is not int or not 41 <= simulations <= 240:
        raise ValueError("simulation count must be 41..240")
    clock = VirtualClock()
    operator_key, auditor_key = secrets.token_bytes(32), secrets.token_bytes(32)
    with TemporaryDirectory(prefix="ijcai-disconnected-admission-learning-") as temp:
        root = Path(temp)
        config = dict(
            consent_sha256=CONSENT_SHA256,
            screening_version=SCREENING,
            operator_key=operator_key,
            auditor_key=auditor_key,
            clock=clock,
        )
        admission = SyntheticAdmissionStore(
            root / "fictional_admission.sqlite3", **config,
        )
        learning = SyntheticThreeArmPilotStore(
            root / "fictional_learning.sqlite3",
            items_path=CONTENT / "items.csv",
            resources_path=CONTENT / "resources.csv",
            simulations=simulations,
        )
        # Internal synthetic roster only; never returned or persisted in a
        # web-accessible artifact.
        roster = []
        allocation = Counter()
        for _ in range(participants):
            invite = admission.issue_invitation(operator_key)
            pid = invite["synthetic_pid"]
            admission.screen(
                operator_key, pid, eligible=True, screening_version=SCREENING,
            )
            response = admission.consent(
                invite["private_invitation"], agreed=True,
                information_sha256=CONSENT_SHA256,
            )
            if not response["created"]:
                raise AssertionError("missing synthetic consent")
            public = admission.participant_status(invite["private_invitation"])
            if "arm" in public or "assignment" in public or public["status"] != "active":
                raise AssertionError("treatment leaked into participant status")
            arm = admission.operator_assignment(operator_key, pid)
            learning_pid = learning.new_synthetic_participant(arm=arm, at=clock.value)
            allocation[arm] += 1
            roster.append((pid, learning_pid, arm, invite["private_invitation"]))

        if set(allocation) != {"A", "B", "C"}:
            raise AssertionError("all arms must appear in the integration rehearsal")
        per_arm_actions = Counter()
        replay_count = 0
        for visit in (1, 2, 3):
            # Four 24-hour days between visit starts; no browser may set the
            # staff clock. Each journey completes within the 65-minute window.
            start = REHEARSAL_START + timedelta(days=4 * (visit - 1))
            clock.value = start
            for pid, learning_pid, arm, _ in roster:
                admission.start_visit(operator_key, pid, visit)
                learning.start_supervised_visit(
                    learning_pid, visit=visit, at=start, **STAFF_FLAGS,
                )

            for pid, learning_pid, arm, _ in roster:
                for step in range(60):
                    snapshot = learning.snapshot(learning_pid)
                    if snapshot["stage"] in ("awaiting_visit", "complete"):
                        break
                    at = start + timedelta(minutes=step + 1)
                    offered = learning.next_action(learning_pid, at=at)
                    if (not offered.get("synthetic_only") or
                            not offered.get("draft_content_not_approved")):
                        raise AssertionError("nonfictional learning action")
                    if step % 17 == 0:
                        assert learning.next_action(learning_pid, at=at) == offered
                    acknowledged = learning.mark_rendered(
                        learning_pid, offered["action_id"], at=at,
                    )
                    if not acknowledged["accepted"]:
                        raise AssertionError("synthetic action render failed")
                    result_id = uuid.uuid4().hex
                    answer = _response(offered)
                    accepted = learning.submit(
                        learning_pid, offered["action_id"], result_id,
                        answer, at=at,
                    )
                    if not accepted["accepted"] or accepted["replayed"]:
                        raise AssertionError("synthetic action was not applied exactly once")
                    if step % 17 == 0:
                        replay = learning.submit(
                            learning_pid, offered["action_id"], result_id,
                            answer, at=at,
                        )
                        if not replay["accepted"] or not replay["replayed"]:
                            raise AssertionError("synthetic replay was not idempotent")
                        replay_count += 1
                    per_arm_actions[(arm, offered["action"])] += 1
                else:
                    raise AssertionError("synthetic learning visit did not terminate")
                finished = learning.snapshot(learning_pid)
                if (finished["visits_finished"] != visit or
                        finished["stage"] != ("complete" if visit == 3 else "awaiting_visit")):
                    raise AssertionError("learning visit incomplete")

            # Attendance cannot be completed before the fictional learning
            # actions; this is a model-only, NOT a real session clock.
            clock.value = start + timedelta(minutes=65)
            for pid, _, _, _ in roster:
                admission.finish_visit(operator_key, pid, visit)

        for pid, learning_pid, arm, token in roster:
            status = admission.participant_status(token)
            state = learning.snapshot(learning_pid)
            scores = learning.scores(learning_pid)
            if (status["visits_finished"] != 3
                    or state["visits_finished"] != 3
                    or state["arm"] != arm
                    or admission.operator_assignment(operator_key, pid) != arm
                    or state["unique_practice_used"] != 55
                    or state["fatigue_deltas"] != (15, 15, 15)
                    or any(scores[form]["answered"] != count for form, count in
                           (("pretest", 16), ("practice", 55), ("posttest", 16)))):
                raise AssertionError("synthetic admission-learning outcome mismatch")

        admission_audit = admission.audit(auditor_key)
        learning_audit = learning.audit_arms()
        if (admission_audit["result"] != "PASS_SYNTHETIC_ONLY"
                or admission_audit["allocated"] != participants
                or learning_audit["allocated"] != dict(allocation)):
            raise AssertionError("synthetic two-engine allocation audit mismatch")
        for arm in ("B", "C"):
            if any(per_arm_actions[(arm, kind)] for kind in RECOVERY_ACTIONS):
                raise AssertionError("control arm received Arm A-only recovery")
        # No response tokens, PID mappings, raw questions, arm-level
        # participant identifiers, or approval booleans are leaked.
        return {
            "kind": "DISPOSABLE_SYNTHETIC_ADMISSION_LEARNING_CROSSCHECK",
            "result": "PASS_SYNTHETIC_ONLY",
            "fictional_participants": participants,
            "fictional_completed_visits": participants * 3,
            "fictional_questions": sum(per_arm_actions[(arm, "QUESTION")]
                                      for arm in ("A", "B", "C")),
            "fictional_mvas_records": sum(per_arm_actions[(arm, "MVAS")]
                                         for arm in ("A", "B", "C")),
            "fictional_replay_checks": replay_count,
            "allocated_by_arm": dict(sorted(allocation.items())),
            "admission_audit": admission_audit["result"],
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participants", type=int, default=9)
    parser.add_argument("--simulations", type=int, default=41)
    options = parser.parse_args()
    try:
        report = run_integrated(
            participants=options.participants, simulations=options.simulations,
        )
    except Exception as error:
        # Fail closed. No identifier, external file path, token, or response.
        print(json.dumps({
            "kind": "DISPOSABLE_SYNTHETIC_ADMISSION_LEARNING_CROSSCHECK",
            "result": "FAIL", "error_type": type(error).__name__,
            "human_enrollment_authorized": False,
        }))
        raise SystemExit(2) from None
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
