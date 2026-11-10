"""OFFLINE synthetic-only pilot feasibility reporting (no human data).

From agent2_realdata_benchmark:
  python -m scripts.pilot_feasibility_report

Default input is a clearly marked fictional 90-person aggregate example.
For a different local fictional aggregate, supply --input /path/to/file.json
with the exact schema and fictional_only=true. This does NOT calculate
causal effects, approve sample size, or authorize human enrollment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.prototype.pilot_feasibility_reporting_draft import (
    summarize_synthetic_feasibility,
)

EXAMPLE = (
    Path(__file__).resolve().parents[2]
    / "docs" / "rct_candidate_v1"
    / "EXAMPLE_FICTIONAL_FEASIBILITY_COUNTS.json"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=EXAMPLE)
    args = parser.parse_args()
    try:
        # Read-only with no networking, enrollment, credentials or data exports.
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        report = summarize_synthetic_feasibility(payload)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, "REJECTED FICTIONAL AGGREGATE: " +
                    type(error).__name__ + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
