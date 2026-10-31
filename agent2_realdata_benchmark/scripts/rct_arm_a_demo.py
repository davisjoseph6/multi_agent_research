"""Create a distinctly labeled operator-selected Arm-A *fictional* browser demo.

This is NOT a random participant recruit, trial enrollment, or evidence of effect.
It draws a balanced randomized fictional block using the unchanged candidate
enrollment code, then picks an Arm-A invitation for *software illustration*.

Run from agent2_realdata_benchmark:
python -m scripts.rct_arm_a_demo --db /path/to/new-fictional.sqlite3 --out /path/to/private-arm-a-invite.json

Do not use this with actual participants, an existing database or live settings.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.rct_candidate_cli import DEFAULT_SETTINGS, engine_from, load_settings


def prepare(*, database, output, settings=DEFAULT_SETTINGS):
    database, output, settings = map(Path, (database, output, settings))
    if database.exists() or output.exists():
        raise FileExistsError("Use a fresh database and a new private output path")
    if database.resolve() == output.resolve():
        raise ValueError("Database path and invitation path must differ")
    cfg, bundle, release = load_settings(settings)
    if cfg.get("mode") != "rehearsal" or release is not None:
        raise ValueError("Fictional Arm-A demonstration refuses released or non-rehearsal settings")

    # A complete 9-person allocation necessarily includes every arm whether
    # the first random block contains 6 or 9 slots. Do not modify allocation.
    engine = engine_from(settings, database)
    created = [engine.issue_invitation() for _ in range(9)]
    assigned = []
    for invitation in created:
        answer = engine.enroll(
            invitation["invitation"], agreed=True,
            information_version=bundle.hashes["information"],
        )
        if not answer["accepted"]:
            raise AssertionError("Fictional invitation was not enrolled")
        assigned.append(invitation)
    # The operator is allowed to inspect assignments in this fictional
    # demonstration ONLY. Never do this for enrolling an RCT participant.
    outcomes = engine.export_private()["outcomes"]
    arms = {record["pid"]: record["assigned_arm"] for record in outcomes}
    counts = Counter(arms[invitation["participant_id"]] for invitation in assigned)
    chosen = next((i for i in assigned if arms[i["participant_id"]] == "A"), None)
    if chosen is None or not all(counts[arm] >= 2 for arm in "ABC"):
        raise AssertionError("Expected balanced arm allocations in nine fictional enrollments")
    payload = {
        "purpose": "FICTIONAL_OPERATOR_SELECTED_ARM_A_BROWSER_DEMO_ONLY",
        "not_randomly_selected_recruit": True,
        "selected_arm": "A",
        "invitation": chosen["invitation"],
        "participant_id": chosen["participant_id"],
        "candidate_sha256": engine.release["candidate_sha256"],
        "warning": "Keep this file private. Never publish the token or use these data as human RCT evidence.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")
    output.chmod(0o600)
    return {
        "status": "FICTIONAL_ARM_A_OPERATOR_DEMO_PREPARED",
        "fictional_enrolled": 9,
        "arm_counts": {arm: counts[arm] for arm in "ABC"},
        "operator_selected_demo_arm": "A",
        "demonstrates_random_participant_probability": False,
        "treatment_policy_modified": False,
        "all_nine_participants_fictional": True,
        "invitation_saved_privately": str(output),
        "invitation_printed": False,
        "human_RCT_evidence": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(database=args.db, output=args.out)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
