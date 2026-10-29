"""Run a fully synthetic three-arm study rehearsal; never enroll real students."""
from pathlib import Path
import argparse
import json
from src.prototype.study_v2 import mock_study, audit_mock_study, write_mock_result, SyntheticAuditSQLite


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--participants", type=int, default=9)
    parser.add_argument("--seed", type=int, default=71)
    parser.add_argument("--output", default="results/step123_mock_study_v2.json")
    args = parser.parse_args()
    result = mock_study(args.participants, args.seed)
    audit = audit_mock_study(result)
    write_mock_result(args.output, result)
    sqlite_file = Path(args.output).with_suffix(".sqlite3")
    if sqlite_file.exists():
        raise FileExistsError(f"refusing to overwrite {sqlite_file}")
    store = SyntheticAuditSQLite(sqlite_file)
    for participant in result["participants"]:
        sid = participant["synthetic_id"]
        store.append(sid, 0, "synthetic_pretest_complete", {"count": 16})
        for session in participant["sessions"]:
            store.append(sid, session["session"], "synthetic_session_complete",
                         {"answers": len(session["responses"]),
                          "recovery_events": len(session["recovery_events"])})
        store.append(sid, 3, "synthetic_posttest_complete", {"count": 16})
    audit["logged_synthetic_events"] = len(store.read_events())
    print(json.dumps(audit, indent=2, sort_keys=True))
    print("SYNTHETIC ONLY. NOT REAL LEARNER EVIDENCE.")


if __name__ == "__main__":
    main()
