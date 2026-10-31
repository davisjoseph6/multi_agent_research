"""Export review worklists without approving or mutating any trial content.

The two source CSV files remain untouched. Output files are private working
copies for a qualified reviewer, not evidence of actual review or authorization.
"""
from __future__ import annotations
import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path

from scripts.rct_candidate_cli import DEFAULT_SETTINGS, load_settings

ITEM_CRITERIA = (
    "factual_correctness_checked",
    "correct_answer_and_rationale_checked",
    "concept_and_bloom_alignment_checked",
    "distractors_and_ambiguity_checked",
    "language_and_accessibility_checked",
    "independence_and_leakage_checked",
    "difficulty_and_fairness_checked",
)
RESOURCE_CRITERIA = (
    "factual_correctness_checked",
    "action_semantics_checked",
    "safety_and_clarity_checked",
    "pedagogical_suitability_checked",
    "sources_and_accessibility_checked",
)
REVIEW_COLUMNS = ("reviewer_notes", "recommendation_pending_expert_decision")


def _read(path):
    with path.open(encoding="utf-8-sig",newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path, rows, criteria):
    if not rows:
        raise ValueError("Empty source rows")
    columns=list(rows[0])+list(criteria)+list(REVIEW_COLUMNS)
    with path.open("x",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row,**{c:"" for c in (*criteria,*REVIEW_COLUMNS)}})


def prepare(out_dir,settings=DEFAULT_SETTINGS):
    settings=Path(settings)
    cfg,bundle,_=load_settings(settings)
    if cfg["mode"]!="rehearsal":
        raise ValueError("Review packet must be produced using rehearsal settings")
    root=settings.parent
    items=root/cfg["content"]["items"]
    resources=root/cfg["content"]["resources"]
    out_dir=Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError("Output directory is not empty")
    out_dir.mkdir(parents=True,exist_ok=True)
    item_rows=_read(items)
    resource_rows=_read(resources)
    assert len(item_rows)==95 and len(resource_rows)==32
    _write(out_dir/"item_review_worklist.csv",item_rows,ITEM_CRITERIA)
    _write(out_dir/"resource_review_worklist.csv",resource_rows,RESOURCE_CRITERIA)
    report={
        "purpose":"DRAFT_CONTENT_REVIEW_PREPARATION_ONLY",
        "content_fingerprint":bundle.fingerprint,
        "items_sha256":sha256(items.read_bytes()).hexdigest(),
        "resources_sha256":sha256(resources.read_bytes()).hexdigest(),
        "items":len(item_rows),
        "resources":len(resource_rows),
        "reviewed_or_approved_by_tool":False,
        "review_decisions_are_genuine":False,
        "changes_to_source_csv":False,
        "fatigue_instrument":"UNVALIDATED_REHEARSAL_ONLY__INSTRUMENT_DECISION_REQUIRED",
        "warning":"Worklists contain copyrighted/educational content; share only with authorized reviewers. Separate qualified review and institutional sign-off required.",
    }
    (out_dir/"MANIFEST.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out-dir",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.out_dir),indent=2))


if __name__=="__main__":
    main()
