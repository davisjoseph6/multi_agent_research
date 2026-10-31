"""Rehearsal-only recovery drill: backup with one pending action, restore and finish.

This does not test external backup storage, encryption, physical disasters, OS
reboots, TLS or actual real-user recovery.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import uuid

from scripts.rct_candidate_cli import DEFAULT_SETTINGS, load_settings
from src.prototype.rct_candidate import RCTCandidateEngine


def _respond(engine,token,action):
    engine.rendered(token,action["action_id"])
    if "question" in action:
        choice=action["question"]["options"][0][0]
        response={"choice_id":choice}
    elif action["action"]=="FATIGUE":
        response={"values":[3]*6}
    else:
        response={"status":"completed"}
    identity=uuid.uuid4().hex
    first=engine.act(token,identity,action["action_id"],response)
    retry=engine.act(token,identity,action["action_id"],response)
    assert not first["replayed"] and retry["replayed"]


def drill(settings=DEFAULT_SETTINGS):
    settings=Path(settings)
    cfg,bundle,release=load_settings(settings)
    if cfg["mode"]!="rehearsal" or release:
        raise ValueError("Recovery test only supports unreleased fictional rehearsal settings")
    with tempfile.TemporaryDirectory(prefix="rct_restore_drill_") as work:
        original=Path(work)/"original.sqlite3"
        restored=Path(work)/"restored.sqlite3"
        source=RCTCandidateEngine(original,bundle,mode="rehearsal",simulations=41)
        token=source.issue_invitation()["invitation"]
        source.enroll(token,agreed=True,information_version=source.bundle.hashes["information"])
        for _ in range(5):
            action=source.next_action(token)
            assert action["stage"]=="pretest"
            _respond(source,token,action)
        # Snapshot a pending sixth action, not just an idle database.
        pending=source.next_action(token)
        source.rendered(token,pending["action_id"])
        before=source.audit()
        assert before["pending_actions"]==1
        evidence=source.backup(restored)
        checksum=sha256(restored.read_bytes()).hexdigest()
        assert evidence["backup_sha256"]==checksum
        recover=RCTCandidateEngine(restored,bundle,mode="rehearsal",simulations=41)
        assert recover.next_action(token)==pending
        _respond(recover,token,pending)
        steps=1
        for _ in range(120):
            action=recover.next_action(token)
            if action["action"]=="COMPLETE":
                break
            _respond(recover,token,action)
            steps+=1
        else:
            raise AssertionError("Restored participant did not finish")
        after=recover.audit()
        assert after["people"].get("complete")==1
        assert after["pending_actions"]==0
        assert source.audit()["pending_actions"]==1  # backup is independent
        outcome=recover.export_private()["outcomes"][0]
        assert outcome["pretest_answered"]==16
        assert outcome["posttest_answered"]==16
        return {
            "status":"SYNTHETIC_SQLITE_BACKUP_RESTORE_REHEARSAL_ONLY",
            "passed":True,
            "backup_sha256":checksum,
            "pending_action_preserved":True,
            "previous_database_not_modified_by_restore":True,
            "remaining_actions_completed":steps,
            "outcome_pretest_answered":16,
            "outcome_posttest_answered":16,
            "pending_actions_after_restore":0,
            "production_disaster_recovery_verified":False,
            "actual_offhost_backup_tested":False,
            "live_data_used":False,
        }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Refusing to overwrite previous evidence")
    result=drill()
    args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
