"""Content and release evidence for the additive RCT candidate.

Mechanical validation is not independent content, ethics, or deployment approval.
"""
from __future__ import annotations

import csv
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path

from .study_v2 import CONCEPTS, RECOVERY_ACTIONS, Item, validate_bank


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def file_digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("invalid CSV headers")
        rows = list(reader)
    if not rows or any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError("empty or malformed content CSV")
    return rows


def reviewed(row):
    if row.get("review_decision") != "approved" or not row.get("reviewer_record", "").strip():
        return False
    try:
        value = datetime.fromisoformat(row.get("review_date", ""))
        return value.date() <= datetime.now(timezone.utc).date()
    except (TypeError, ValueError):
        return False


class ContentBundle:
    def __init__(self, items_path, resources_path, fatigue_path, information_path):
        paths = dict(items=Path(items_path), resources=Path(resources_path),
                     fatigue=Path(fatigue_path), information=Path(information_path))
        self.hashes = {name: file_digest(path) for name, path in paths.items()}
        item_rows = read_csv(items_path)
        resource_rows = read_csv(resources_path)
        if Counter(row["form"] for row in item_rows) != {
                "pretest": 16, "posttest": 16, "practice": 55, "recovery_drop2": 8}:
            raise ValueError("expected 16 pretest, 55 practice, 16 posttest and 8 DROP_2 items")
        self.items = []
        for row in item_rows:
            difficulty = float(row["difficulty_estimate"])
            if not math.isfinite(difficulty):
                raise ValueError("nonfinite item difficulty")
            self.items.append(Item(
                item_id=row["item_id"], form=row["form"], concept=row["concept"],
                bloom=row["bloom"], prompt=row["prompt"],
                options=tuple((key, row["option_" + key]) for key in "ABCD"
                              if row["option_" + key].strip()),
                answer_id=row["correct_option_id"], difficulty=difficulty,
                status="expert_reviewed" if reviewed(row) else "draft"))
        validate_bank(self.items, full=True)
        self.resources = {}
        ids = set()
        for row in resource_rows:
            key = row["concept"], row["action"]
            if key in self.resources or not row["resource_id"] or row["resource_id"] in ids:
                raise ValueError("duplicate or empty resource identity")
            if not row["resource_text"].strip():
                raise ValueError("empty resource text")
            ids.add(row["resource_id"])
            self.resources[key] = dict(
                resource_id=row["resource_id"], text=row["resource_text"],
                source=row.get("source_citation", ""), version_sha256=digest(row))
        if set(self.resources) != {(c, a) for c in CONCEPTS for a in RECOVERY_ACTIONS}:
            raise ValueError("expected exactly eight concepts by four recovery resources")
        self.fatigue = json.loads(paths["fatigue"].read_text(encoding="utf-8"))
        scale = self.fatigue.get("scale", {"minimum": 1, "maximum": 5, "step": 1})
        if (not isinstance(scale, dict) or
                set(scale) != {"minimum", "maximum", "step"} or
                any(type(scale[key]) is not int for key in scale) or
                scale["minimum"] < 0 or scale["maximum"] > 100 or
                scale["step"] < 1 or
                scale["minimum"] >= scale["maximum"] or
                (scale["maximum"] - scale["minimum"]) % scale["step"] != 0):
            raise ValueError("invalid questionnaire response scale")
        valid_values = range(scale["minimum"], scale["maximum"] + 1, scale["step"])
        if (len(self.fatigue.get("items", [])) != 6 or
                any(not isinstance(item, str) or not item.strip()
                    for item in self.fatigue["items"]) or
                set(self.fatigue.get("labels", {})) != {str(i) for i in valid_values} or
                any(not isinstance(label, str) or not label.strip()
                    for label in self.fatigue["labels"].values()) or
                not isinstance(self.fatigue.get("version"), str) or
                not self.fatigue["version"].strip()):
            raise ValueError("six questionnaire prompts, version and complete scale labels required")
        self.fatigue["scale"] = scale
        self.information = paths["information"].read_text(encoding="utf-8").strip()
        if not self.information:
            raise ValueError("participant information is empty")
        self.unreviewed_items = sum(not reviewed(r) for r in item_rows)
        self.unreviewed_resources = sum(not reviewed(r) for r in resource_rows)
        self.fatigue_reviewed = reviewed(self.fatigue)
        self.fingerprint = digest(self.hashes)


def source_fingerprint():
    """Bind the runtime, selector, browser and content/gate implementation."""
    root = Path(__file__).resolve().parent
    relative = ["study_v2.py", "study_v2_runtime.py", "study_v3_runtime.py",
                "study_v3_pomcp.py", "rct_candidate_content.py", "rct_candidate.py",
                "rct_candidate_api.py", "templates/rct_candidate.html",
                "static/rct_candidate.js", "static/rct_candidate.css"]
    files = {name: file_digest(root / name) for name in relative}
    files["scripts/rct_candidate_cli.py"] = file_digest(root.parent.parent / "scripts/rct_candidate_cli.py")
    return files


REVIEW_DOMAINS = ("protocol_and_analysis", "content_and_measurement",
                  "ethics_pathway", "privacy", "deployment_and_independent_qa")


def release_report(bundle, policy, release_path=None):
    candidate = dict(content=bundle.hashes, policy=policy, source=source_fingerprint())
    fingerprint = digest(candidate)
    blockers = []
    if bundle.unreviewed_items:
        blockers.append(f"{bundle.unreviewed_items} item reviews missing")
    if bundle.unreviewed_resources:
        blockers.append(f"{bundle.unreviewed_resources} resource reviews missing")
    if not bundle.fatigue_reviewed:
        blockers.append("fatigue instrument review missing")
    record = {}
    if release_path:
        record = json.loads(Path(release_path).read_text(encoding="utf-8"))
    if record.get("candidate_sha256") != fingerprint:
        blockers.append("release evidence does not bind this exact candidate")
    if record.get("decision") != "authorized_for_enrollment":
        blockers.append("institutional enrollment authorization not recorded")
    if not record.get("study_id") or not record.get("responsible_institution"):
        blockers.append("study ID or responsible institution missing")
    for domain in REVIEW_DOMAINS:
        entry = record.get("reviews", {}).get(domain, {})
        ok = entry.get("decision") == "approved" and reviewed({
            "review_decision": "approved", "reviewer_record": entry.get("reviewer", ""),
            "review_date": entry.get("date", "")})
        evidence_path = entry.get("evidence_file")
        try:
            path = Path(release_path).resolve().parent / evidence_path if evidence_path else None
            ok = ok and path is not None and path.is_file() and file_digest(path) == entry.get("sha256")
        except (OSError, TypeError):
            ok = False
        if not ok:
            blockers.append(f"verified evidence file and signed decision missing: {domain}")
    return dict(candidate_sha256=fingerprint, candidate=candidate, blockers=blockers,
                mechanical_gate_passed=not blockers,
                limitation="Files and hashes cannot authenticate a reviewer or grant institutional approval.")
