"""Read-only structural audit of the local fictional three-arm browser rehearsal.

Not a human-study authorization, ethics approval, security certification, or
scientific assessment. No database changes or network requests are made.

From agent2_realdata_benchmark:
    python -m scripts.pilot_fictional_acceptance_audit
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.prototype.pilot_fictional_acceptance_audit import (
    FictionalAuditError, audit_fictional_database,
)

DEFAULT_DB = (
    Path.home() / ".cache" / "ijcai2027_fictional_browser_preview"
    / "fictional_browser_preview.sqlite3"
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB,
        help="existing fictional_browser_preview.sqlite3; read-only",
    )
    args = parser.parse_args()
    try:
        result = audit_fictional_database(args.db)
    except FictionalAuditError as error:
        parser.exit(2, f"FICTIONAL AUDIT ERROR: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["result"] == "PASS_SYNTHETIC_ONLY" else 2)


if __name__ == "__main__":
    main()
