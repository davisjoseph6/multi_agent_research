"""Local-only three-arm synthetic first-visit concurrency probe.

Run from agent2_realdata_benchmark:
    python -m scripts.pilot_concurrency_rehearsal --participants 30 --workers 5

Creates an isolated disposable SQLite file under the OS temp directory.
No HTTP requests, real identities, network exposure, human enrollment,
approved power/effect estimates or production-capacity guarantees.
A passing result means ONLY that this synthetic workload completed.
"""
from __future__ import annotations

import argparse
import json

from src.prototype.pilot_concurrency_rehearsal import (
    run_synthetic_parallel_rehearsal,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participants", type=int, default=9)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--simulations", type=int, default=41)
    args = parser.parse_args()
    try:
        report = run_synthetic_parallel_rehearsal(
            participants=args.participants,
            workers=args.workers,
            simulations=args.simulations,
        )
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + "\n")
    print(json.dumps(report, sort_keys=True, indent=2))
    raise SystemExit(0 if report["result"] == "PASS" else 2)


if __name__ == "__main__":
    main()
