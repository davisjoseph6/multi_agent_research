"""Create a persistent 3-arm fictional study ledger, then audit it READ-ONLY.

No subjects, no outcome validity, no production identities, no RCT.
Run from project root: python -m scripts.step123_v4_audited_mock --database PATH
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.prototype.study_v2 import synthetic_bank
from src.prototype.study_v3_pomcp import EightConceptPOMCP
from src.prototype.study_v3_runtime import SyntheticPOMCPProtocolEngine
from .step123_v4_independent_audit import audit_database


def make_mock(path: str | Path, *, simulations: int = 24) -> dict:
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing database: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = SyntheticPOMCPProtocolEngine(
        path, synthetic_bank(), planner=EightConceptPOMCP(simulations=simulations)
    )
    for arm in ("A", "B", "C"):
        pid = "SYN_V4_AUDIT_" + arm
        engine.enroll(pid, arm)
        for step in range(140):
            action = engine.next_action(pid)
            kind = action["action"]
            if kind == "COMPLETE":
                break
            if kind in {"QUESTION", "DROP_2"}:
                payload = {"item_id": action["item_id"], "choice_id": "A"}
            elif kind == "FATIGUE":
                payload = {"values": [3, 3, 3, 3, 3, 3]}
            else:
                payload = {"acknowledged": True}
            response = engine.act(pid, f"{pid}_response_{step:03}", payload)
            if response.get("accepted") is not True or response.get("replayed") is not False:
                raise AssertionError("synthetic protocol rejected or replayed a fresh response")
        else:
            raise AssertionError(f"synthetic participant {pid} did not finish")
    return audit_database(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--simulations", type=int, default=24)
    args = parser.parse_args()
    result = make_mock(args.database, simulations=args.simulations)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
