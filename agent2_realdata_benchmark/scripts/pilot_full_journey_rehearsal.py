"""OFFLINE three-visit fictional A/B/C parallel journey; no human studies.

Run from agent2_realdata_benchmark:
  python -m scripts.pilot_full_journey_rehearsal --participants 9 --workers 3
  python -m scripts.pilot_full_journey_rehearsal --participants 30 --workers 5 --simulations 240

This uses disposable temporary SQLite, virtual 4-day session spacing,
fake answers, proposal-only M-VAS, no networking and no real identities.
It is NOT a production HTTPS capacity test or research authorization.
"""
from __future__ import annotations

import argparse
import json

from src.prototype.pilot_full_journey_rehearsal import run_full_journey_rehearsal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participants", type=int, default=3)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--simulations", type=int, default=41)
    args = parser.parse_args()
    try:
        report = run_full_journey_rehearsal(
            participants=args.participants,
            workers=args.workers,
            simulations=args.simulations,
        )
    except ValueError as err:
        parser.exit(2, "INVALID SYNTHETIC TEST SCENARIO: " + str(err) + "\n")
    print(json.dumps(report, sort_keys=True, indent=2))
    raise SystemExit(0 if report["result"] == "PASS" else 2)


if __name__ == "__main__":
    main()
