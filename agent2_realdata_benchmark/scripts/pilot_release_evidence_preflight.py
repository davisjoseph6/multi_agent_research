"""OFFLINE, READ-ONLY pilot evidence completeness inspection.

This never authorizes enrollment, even when all evidence is indexed. It never
contacts the real server, imports participant stores or verifies signatures.
Use a PRIVATE manifest outside the Git repository for actual documents.

From agent2_realdata_benchmark:
    python -m scripts.pilot_release_evidence_preflight --manifest /private/evidence/manifest.json

Without --manifest, only the public UNAPPROVED TEMPLATE is inspected; it
MUST fail closed (exit status 2). This is the expected default result.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.prototype.pilot_release_evidence_gate import inspect_evidence_index

TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "docs" / "pilot_release_evidence"
    / "MANIFEST_TEMPLATE.json"
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=TEMPLATE)
    args = parser.parse_args()
    try:
        report = inspect_evidence_index(args.manifest)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        parser.exit(2, "INVALID PRIVATE EVIDENCE INDEX: " + str(error) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    # Index completeness never makes the study legally authorized. Exit zero
    # only means file metadata/hashes are structurally complete and need
    # independent signatory/authenticity and live-release review.
    raise SystemExit(0 if report["gates_complete"] == report["gates_required"]
                     and not report["issues"] else 2)


if __name__ == "__main__":
    main()
