"""Read-only Steps 72..123 closure and content audit: never grants completion.

Usage (from agent2_realdata_benchmark):
    python3 -m scripts.step72_123_weekend_triage --output /tmp/ijcai_weekend_triage.md

Outputs factual register snapshot and unchanged provisional points. A content
checker exit code of 1 is reported faithfully, not treated as success. The
script never modifies the register, drafts, content, git or study settings.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
import hashlib
import json
import subprocess
import sys

STATUS_CREDIT = {
    "SYNTHETIC-IMPLEMENTED": Decimal("1"),
    "PARTIAL": Decimal("0.5"),
    "EXTERNAL-REQUIRED": Decimal("0"),
    "NOT-PROVEN": Decimal("0"),
}

PRIORITY = {
    "SCIENTIFIC": set(range(72, 96)),
    "CONTENT": set(range(96, 107)),
    "TRIAL_ENGINE": set(range(107, 118)),
    "OPERATIONS": set(range(118, 124)),
}

# Design and evidence priorities, not automatic completion decisions.
P0 = {72, 73, 78, 79, 80, 83, 86, 88, 93, 94, 95, 103}
P1 = {96, 97, 99, 100, 104, 106, 117, 119, 120, 122}
EXTERNAL = {75, 76, 77, 81, 85, 98, 99, 100, 101, 102, 104, 105, 118, 121}


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_register(path: Path) -> tuple[list[dict], Decimal, Counter]:
    with path.open(newline="", encoding="utf-8-sig") as fp:
        rows = list(csv.DictReader(fp))
    if len(rows) != 52:
        raise ValueError(f"Require 52 steps, observed {len(rows)}")
    steps = [int(row["step"]) for row in rows]
    if sorted(steps) != list(range(72, 124)):
        raise ValueError("Step IDs must be exactly 72..123 with no duplicates")
    credit = Decimal(0)
    counts: Counter = Counter()
    for row in rows:
        status = row["evidence_status"].strip()
        if status not in STATUS_CREDIT:
            raise ValueError(f"Step {row['step']} has unknown status {status!r}")
        try:
            actual_credit = Decimal(row["evidence_credit"])
        except (InvalidOperation, KeyError):
            raise ValueError(f"Invalid evidence credit at step {row['step']}")
        if actual_credit != STATUS_CREDIT[status]:
            raise ValueError(f"Credit/status mismatch at step {row['step']}")
        credit += actual_credit
        counts[status] += 1
    return rows, credit, counts


def content_audit(root: Path) -> dict:
    script = root / "scripts/step96_106_content_audit.py"
    if not script.is_file():
        return {"executed": False, "reason": f"Not found: {script}"}
    result = subprocess.run([sys.executable, str(script)], cwd=root,
                            text=True, capture_output=True, check=False)
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        parsed = None
    return {
        "executed": True,
        "exit_code": result.returncode,
        "json": parsed,
        "stdout_excerpt": result.stdout[:1000] if parsed is None else None,
        "stderr_excerpt": result.stderr[:300],
        "note": "Nonzero is an expected fail-closed outcome; do not bypass validation",
    }


def git_state(root: Path) -> dict:
    git_root = root.parent
    values = {}
    for label, args in {
        "branch": ("branch", "--show-current"),
        "head": ("rev-parse", "HEAD"),
        "status": ("status", "--short"),
    }.items():
        res = subprocess.run(["git", *args], cwd=git_root, text=True,
                             capture_output=True, check=False)
        values[label] = res.stdout.strip() if res.returncode == 0 else None
    return values


def build_snapshot(root: Path, *, audit_content: bool = True) -> dict:
    register = root / "docs/steps72_123_closure_register.csv"
    rows, credit, counts = load_register(register)
    return {
        "scope": "52-step register snapshot, not external validation",
        "root": str(root),
        "register_sha256": source_hash(register),
        "score": {
            "provisional_points": float(credit), "denominator": 52,
            "provisional_percent": round(float(credit / 52 * 100), 1),
            "scientific_completion_certified": False,
            "synthetic_implementation_is_not_human_readiness": True,
        },
        "status_counts": dict(counts),
        "git": git_state(root),
        "content_audit": content_audit(root) if audit_content else {"executed": False, "reason": "Skipped by caller"},
        "steps": [dict(row) for row in rows],
        "unreceived_signoffs": [int(row["step"]) for row in rows if row.get("independent_signoff", "").strip() == "NOT RECEIVED"],
    }


def render_markdown(s: dict) -> str:
    score = s["score"]
    git = s["git"]
    audit = s["content_audit"]
    content = audit.get("json") or {}
    text = [
        "# Steps 72–123 — Read-only evidence triage",
        "",
        "> This document is a snapshot of the EXISTING evidence-credit register. It is not a change of status, certified study readiness or independent signoff.",
        "",
        f"- Register SHA-256: `{s['register_sha256']}`",
        f"- Git HEAD: `{git.get('head') or 'unavailable'}`",
        f"- Branch: `{git.get('branch') or 'unavailable'}`",
        f"- Provisional points: **{score['provisional_points']}/52 ({score['provisional_percent']}%)**",
        f"- Status counts: {json.dumps(s['status_counts'], sort_keys=True)}",
        f"- Signoffs explicitly marked NOT RECEIVED: **{len(s['unreceived_signoffs'])}**",
        f"- Working tree: **{'contains untracked/tracked status entries' if git.get('status') else 'no status entries reported'}**",
        "",
        "## Fail-closed content validation",
        "",
    ]
    if audit["executed"]:
        text += [f"- Checker exit code: **{audit['exit_code']}**",
                 f"- Structural validation passed: **{content.get('structural_check_passed', 'unknown')}**",
                 f"- Reported issue count: **{content.get('issue_count', 'unavailable')}**",
                 f"- Expert review verified: **{content.get('expert_review_verified', 'unknown')}**",
                 f"- Psychometrics verified: **{content.get('psychometric_validation_verified', 'unknown')}**",
                 f"- Human study authorized: **{content.get('authorized_for_human_study', 'unknown')}**",
                 "", "First issues reported by the checker (not an exhaustive count by category):", ""]
        for issue in content.get("first_issues", []):
            text.append(f"- {issue}")
    else:
        text.append(f"- Audit not run: {audit.get('reason')}")
    text += ["", "## Exit criteria and blocking evidence", "",
             "| Step | Group | Existing status | Priority | Outstanding exit criterion | Independent signoff |",
             "|---:|---|---|---|---|---|"]
    for row in sorted(s["steps"], key=lambda x: int(x["step"])):
        number = int(row["step"])
        group = next(name for name, members in PRIORITY.items() if number in members)
        status = row["evidence_status"]
        urgency = "P0" if number in P0 else "P1" if number in P1 else "external" if number in EXTERNAL else "preserve/audit"
        requirement = row["exit_criterion"].replace("|", "\\|").replace("\n", " ")
        signoff = row.get("independent_signoff", "").replace("|", "\\|")
        text.append(f"| {number} | {group} | {status} | {urgency} | {requirement} | {signoff} |")
    text += ["", "## Nonnegotiable next actions", "",
             "1. Do not recode an unmet external signoff as completed. Report 1,142 field issues as issues, not 1,142 independent items.",
             "2. Resolve policy and analysis definitions (72, 73, 78, 79, 80, 88, 93–95) against the actual shipped policy, not an idealized model.",
             "3. Create REAL authored content as DRAFT only, with no fabricated citation, review date, expertise or approval (96–106).",
             "4. Run safe adversarial leakage, restart, access, concurrency and restoration tests (103, 119, 120, 122).",
             "5. Send content, hypothesis, protocol and ethics materials to qualified signoff owners; keep human-study release blocked until authorized.",
             "6. Preserve development-versus-held-out boundaries. No held-out run until candidate/protocol are frozen and justified.",
             "7. On November 2 re-run full tests and independently inspect evidence before *any* register credit change.",
             "", "No files or credits were modified by the triage script.", ""]
    return "\n".join(text)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--output", type=Path)
    p.add_argument("--json-output", type=Path)
    p.add_argument("--skip-content-audit", action="store_true")
    a = p.parse_args(argv)
    try:
        snapshot = build_snapshot(a.root.resolve(), audit_content=not a.skip_content_audit)
    except (OSError, ValueError) as exc:
        print(f"Evidence triage cannot proceed: {exc}", file=sys.stderr)
        return 2
    markdown = render_markdown(snapshot)
    if a.output:
        a.output.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)
    if a.json_output:
        a.json_output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
