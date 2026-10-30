"""Author eight review-pending constructed-response CREATE practice tasks.

Do NOT replace the eight existing multiple-choice items or claim those
items' construct warnings are resolved. This creates a separate instrument
requiring human-scoring/UI integration, reliability testing and expert review.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path

from scripts.step96_106_authoring_drafts import CONCEPTS

EXPECTED_V2_SHA256 = "d7258353e90df6c25857f1abca13a86a1030cd2ab969ec03a469b67a30a8f3f8"
FIELDS = (
    "task_id", "linked_existing_item_id", "concept", "bloom", "response_format",
    "task_prompt", "required_output", "concept_specific_accuracy_anchor",
    "concept_specific_design_anchor", "source_citation", "review_decision",
    "reviewer_record", "review_date", "scoring_rubric_version",
)

# 8 genuinely productive writing/design requests. Students must CONSTRUCT
# a novel artifact; recognizing a preferred choice is not sufficient.
TASKS = {
    "Utility": (
        "Invent a two-option decision problem: one certain outcome and one lottery. State at least two outcome probabilities, define a coherent utility for each outcome, calculate both expected utilities and write an answer explaining which option a specified decision maker would select. Make the probabilities total one.",
        "A self-contained numerical scenario, probability and utility table, correct expected-utility calculation, and justified choice.",
        "Utility weights must apply to outcomes, not be mistaken for monetary averages; probability totals and calculations must be correct.",
        "The choice context is original, alternatives are distinguishable, and the conclusion follows the supplied utilities.",
    ),
    "Loss Aversion": (
        "Design an original experiment that could distinguish a reference-point loss-aversion explanation of an ownership valuation gap from at least one rival explanation. Specify randomization, outcomes, measurements, and a falsifying result.",
        "A comparison of randomized conditions, operationalized reference states, valuation outcomes, confounds and a falsification criterion.",
        "Distinguish reference-dependent loss aversion from general risk aversion or transaction costs; do not assert a universal loss-to-gain ratio.",
        "Manipulates reference state while keeping object, stakes, and elicitation conditions comparable.",
    ),
    "Anchoring": (
        "Construct a short randomized study of an irrelevant numeric anchor affecting a factual estimate. Write the exact two prompts, a neutral outcome question, an assignment rule, a pre-specified outcome comparison, and one limitation.",
        "Two randomized prompts, common estimate question, primary contrast and interpretation limit.",
        "Anchors must be plausibly irrelevant to the quantity and must not themselves carry accurate task information.",
        "Keeps target item and available factual evidence equivalent across treatment arms.",
    ),
    "Sunk Cost": (
        "Write a one-page decision memo for an original project with a past unrecoverable expenditure, two future options, future costs and benefits, and opportunity cost. Create a small numerical table, choose an option and justify the incremental analysis.",
        "New case, incremental future-value table, decision rule, justified option and one caveat.",
        "Do not include irrecoverable past expenditure in the incremental comparison; include relevant future and recoverable amounts.",
        "Provides two genuinely viable alternatives and makes a numerical or clearly justified qualitative choice.",
    ),
    "Framing": (
        "Compose two mathematically equivalent messages describing one binary-outcome decision: one gain-framed and one loss-framed. Create a randomized evaluation plan, specify an outcome and a safeguard against misleading communication.",
        "Two equivalent messages, denominator consistency check, randomized contrast and ethical safeguard.",
        "Positive and negative probability/count frames must be exact complements under a shared denominator.",
        "Holds choice outcomes constant and varies only presentation while preserving transparent risk disclosure.",
    ),
    "Heuristics": (
        "Build an original short diagnostic exercise with three distinct mini-scenarios designed to elicit availability, representativeness and anchoring. For each, specify the expected error, a discriminating follow-up question and one alternative explanation.",
        "Three novel mini-scenarios, mapped heuristic hypotheses, counterchecks and confounds.",
        "Distinguish recall accessibility, resemblance-to-prototype, and starting-number effects; avoid defining all errors as the same bias.",
        "Each vignette targets a distinct cue and supplies a testable alternative explanation.",
    ),
    "Prospect Theory": (
        "Create a pair of original choices that hold final monetary outcomes constant while changing the stated reference point. Predict, under an explicitly named prospect-theory assumption, how valuation could differ, and design a comparison that might falsify your prediction.",
        "Paired choice descriptions, explicit reference points, model assumptions, prediction and testable counterexample.",
        "Separate gains/losses from final wealth, and distinguish reference dependence from probability-weighting assumptions.",
        "The paired alternatives are objectively comparable while changing an interpretable reference point.",
    ),
    "Nudge Theory": (
        "Design an original, ethically defensible default or reminder intervention to help people make an informed choice. Draw or describe the complete choice interface, opt-out, evaluation outcome, randomization and adverse-effect monitoring plan.",
        "Original choice architecture, documented opt-out, randomized evaluation design and monitoring criteria.",
        "Preserves meaningful freedom of choice, recognizes transparency and possible welfare tradeoffs; does not equate click rate with benefit.",
        "Includes a usable, reversible choice interface and both benefit and unintended-consequence measures.",
    ),
}


def build(rows: list[dict]) -> list[dict]:
    """Prepare tasks only if the eight existing CREATE slots still match the blueprint."""
    if len(rows) != 95 or len({r.get("item_id") for r in rows}) != 95:
        raise ValueError("V2 bank must contain exactly 95 uniquely identified items")
    create_rows = [r for r in rows if r.get("bloom") == "create"]
    if len(create_rows) != 8 or {r.get("concept") for r in create_rows} != set(CONCEPTS):
        raise ValueError("Must find exactly one CREATE practice row per original concept")
    if any(r.get("form") != "practice" or r.get("review_decision") != "pending" or
           r.get("reviewer_record", "").strip() or r.get("review_date", "").strip()
           for r in create_rows):
        raise ValueError("Expected unreviewed practice CREATE items; refuse changed source")
    by_concept = {r["concept"]: r for r in create_rows}
    tasks = []
    for concept in CONCEPTS:
        item = by_concept[concept]
        task_prompt, required_output, correctness, design = TASKS[concept]
        tasks.append(dict(
            task_id="BE_CREATE_RESPONSE_" + item["item_id"].removeprefix("BE_"),
            linked_existing_item_id=item["item_id"], concept=concept,
            bloom="create", response_format="constructed_response_written_or_diagram",
            task_prompt=task_prompt, required_output=required_output,
            concept_specific_accuracy_anchor=correctness,
            concept_specific_design_anchor=design,
            source_citation=item["source_citation"], review_decision="pending",
            reviewer_record="", review_date="", scoring_rubric_version="DRAFT_v1",
        ))
    return tasks


def generate(items_path: Path, output_dir: Path, *, expected_sha256: str = EXPECTED_V2_SHA256) -> dict:
    raw = items_path.read_bytes()
    original_digest = sha256(raw).hexdigest()
    if original_digest != expected_sha256:
        raise ValueError(f"V2 bank hash changed: {original_digest}; refusing mismatched source")
    if output_dir.exists():
        raise FileExistsError("Review-pending output already exists; refuse overwrite")
    with items_path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    tasks = build(rows)
    output_dir.mkdir(parents=True)
    path = output_dir / "constructed_response_create_tasks_PENDING_REVIEW.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(tasks)
    record = {
        "status": "REVIEW-PENDING DRAFT ONLY",
        "source_item_sha256": original_digest,
        "task_csv_sha256": sha256(path.read_bytes()).hexdigest(),
        "task_count": len(tasks),
        "source_bank_changed": False,
        "current_mc_create_warnings_resolved": False,
        "independent_expert_reviews": 0,
        "human_study_authorized": False,
        "requires_runtime_constructed_response_support": True,
        "requires_independent_rater_training_and_reliability": True,
        "rubric": {
            "criteria": ["domain_accuracy", "original_design_quality", "reasoning_and_justification", "clarity_and_constraints"],
            "levels": {
                "0": "Absent, substantively incorrect, or non-responsive",
                "1": "Partially meets criterion; material ambiguity or omission",
                "2": "Meets criterion with no material conceptual error",
            },
            "total_min": 0, "total_max": 8,
            "note": "Proposed analytic rubric only. Training, double scoring, disagreement adjudication and reliability study are NOT completed. Do not infer mastery from numeric scores until validated.",
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=Path, default=Path("docs/nov2_assessment_revisions_v2_PENDING_REVIEW/authored_items_PENDING_REVIEW.csv"))
    parser.add_argument("--output", type=Path, default=Path("docs/nov2_create_performance_tasks_v1_PENDING_REVIEW"))
    args = parser.parse_args()
    print(json.dumps(generate(args.items, args.output), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
