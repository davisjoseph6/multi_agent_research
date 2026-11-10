"""Run complete 3-visit A/B/C journey across separate fictional processes.

LOCAL DISPOSABLE SQLITE ONLY. NO REAL STUDENTS, NO LIVE VPS OR HTTPS.
This checks persistence of real study state transitions and idempotent responses
across *independently constructed* store instances; no cross-process FIFO.

From agent2_realdata_benchmark:
  python -m scripts.pilot_multiprocess_full_journey_rehearsal \
      --participants 6 --processes 2 --threads 2 --simulations 41 --mode fifo
"""
from __future__ import annotations

import argparse
import json

from src.prototype.pilot_multiprocess_full_journey_rehearsal import (
    run_multiprocess_full_journey,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participants", type=int, default=6)
    parser.add_argument("--processes", type=int, default=2)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--simulations", type=int, default=41)
    parser.add_argument("--mode", choices=("native", "fifo"), default="native")
    args = parser.parse_args()
    try:
        report = run_multiprocess_full_journey(
            participants=args.participants,
            processes=args.processes,
            threads_per_process=args.threads,
            simulations=args.simulations,
            writer_admission=args.mode,
        )
    except ValueError as error:
        parser.exit(2, "INVALID FICTIONAL TEST: " + str(error) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["result"] == "PASS" else 2)


if __name__ == "__main__":
    main()
