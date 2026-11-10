"""Run a strictly disposable multi-process SQLite writer-admission probe.

From agent2_realdata_benchmark:
  python -m scripts.pilot_multiprocess_writer_probe --mode fifo
  python -m scripts.pilot_multiprocess_writer_probe --mode native

This tests two or more independent Python processes and their own in-process
FIFO queues sharing one synthetic SQLite file. No student data, HTTP, VPS or
production enrollment is involved. Results never certify production capacity.
"""
from __future__ import annotations

import argparse
import json

from src.prototype.pilot_multiprocess_writer_probe import run_multiprocess_probe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fifo", "native"), default="fifo")
    parser.add_argument("--processes", type=int, default=2)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--operations", type=int, default=3)
    parser.add_argument("--hold-ms", type=int, default=8)
    args = parser.parse_args()
    try:
        result = run_multiprocess_probe(
            writer_admission=args.mode,
            processes=args.processes,
            threads_per_process=args.threads,
            operations_per_thread=args.operations,
            hold_ms=args.hold_ms,
        )
    except ValueError as exc:
        parser.exit(2, "INVALID FICTIONAL PROBE: " + str(exc) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["result"] == "PASS" else 2)


if __name__ == "__main__":
    main()
