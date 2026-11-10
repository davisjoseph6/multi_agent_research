"""Read-only, non-authorizing audit of 95/32 draft content review register.

Run from agent2_realdata_benchmark:
  python -m scripts.pilot_content_review_audit

A blocked result and exit 2 are EXPECTED until independent reviewers approve
content and one appropriate validated mental-fatigue instrument. This does
not check signatures or give student-enrollment permission.
"""
from __future__ import annotations

import json

from src.prototype.pilot_content_review_audit_draft import audit_content_review


def main():
    report = audit_content_review()
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(2 if report["result"] == "BLOCKED" else 0)


if __name__ == "__main__":
    main()
