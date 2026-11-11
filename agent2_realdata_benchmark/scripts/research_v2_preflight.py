"""Read-only release gates for the proposed V2 crossover and FR/EN RCT.

No human use, enrollment or infrastructure changes. Reports why the existing
95-question, English-only pilot CANNOT safely meet a 261-distinct-item,
three-period bilingual requirement.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "docs" / "rct_candidate_v1"
REQUIRED_FORMS = {"pretest": 48, "practice": 165, "posttest": 48}
ALLOWED_LANGUAGES = ("en", "fr")


def preflight(bank_csv: Path, fr_csv: Path | None = None) -> dict:
    """Identify incomplete source content; cannot grant human-study approval."""
    if not bank_csv.exists():
        raise FileNotFoundError(bank_csv)
    with bank_csv.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    by_form = Counter(r["form"] for r in rows)
    ids = [r["item_id"] for r in rows]
    blockers = []
    if len(rows) < 261 or len(ids) != len(set(ids)):
        blockers.append("Need >=261 distinct question IDs for three periods of 87 normal items")
    for form, needed in REQUIRED_FORMS.items():
        if by_form[form] < needed:
            blockers.append(f"Need >= {needed} unique {form} items; found {by_form[form]}")
    if not rows or any(not r.get("prompt", "").strip() for r in rows):
        blockers.append("English question prompt missing")
    if any(r.get("review_decision") != "approved" for r in rows):
        blockers.append("English items lack independently signed educational review")
    if fr_csv is None or not fr_csv.is_file():
        blockers.append("Missing independent, fully translated and reviewed French question bank")
        french_count = 0
    else:
        with fr_csv.open(newline="", encoding="utf-8-sig") as stream:
            translations = list(csv.DictReader(stream))
        # Require exactly one approved translation per English item. A
        # duplicated approved row must not hide a missing French translation.
        source_ids = set(ids)
        translation_counts = Counter(r.get("item_id") for r in translations)
        french_count = sum(
            r.get("item_id") in source_ids
            and bool(r.get("prompt_fr", "").strip())
            and r.get("review_decision_fr") == "approved"
            and all(r.get(f"option_{c}_fr", "").strip() for c in "ABCD")
            for r in translations
        )
        if (french_count != len(rows) or len(translations) != len(rows)
                or translation_counts != Counter(ids)):
            blockers.append("Missing, duplicated, or unreviewed French item/option translations")
    blockers.extend([
        "Parallel A/B/C design not approved for within-person crossover with period/carryover control",
        "New 3-period power analysis, estimand, and per-period scoring not approved",
        "Email notice, identity separation, security, retention and opt-out not approved",
        "No verified participant-email sender or opt-in reminder delivery service",
        "No approved and validated fatigue questionnaire, English and French",
        "No independently validated French recovery resource translations",
        "No institutional/ethics authorization for human enrollment",
    ])
    return {
        "kind": "RESEARCH_V2_CROSSOVER_BILINGUAL_RELEASE_GATE",
        "result": "BLOCKED_NOT_APPROVED" if blockers else "NEEDS_EXTERNAL_APPROVAL",
        "english_bank_question_rows": len(rows),
        "english_bank_forms": {key: by_form[key] for key in sorted(by_form)},
        "english_bank_distinct_ids": len(set(ids)),
        "french_bank_fully_reviewed_rows": french_count,
        "minimum_distinct_question_rows": 261,
        "one_same_question_retry_exception": "Only immediate DROP_2 is an instruction retry",
        "blockers": blockers,
        "human_enrollment_authorized": False,
        "changes_to_vps_services": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, default=ROOT / "items.csv")
    parser.add_argument("--french", type=Path)
    args = parser.parse_args()
    result = preflight(args.bank, args.french)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["blockers"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
