"""Validated ID-preserving French text for the isolated fictional supervisor quiz.

All 232 questions (8 screening, 16 pretest, 192 practice, 16 posttest)
have provisional French questions and options, provided as C1..C8 TSV.
Correct-answer letters, ordering, concepts, Bloom levels, and calculations
always come from the canonical English CSVs. French text is NOT reviewed
for equivalence by a subject expert and MUST NOT be used for human studies.
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

FR_ROOT = Path(__file__).resolve().parents[2] / "content" / "i18n" / "fr"
LANGUAGES = ("en", "fr")


@lru_cache(maxsize=1)
def french_bank() -> dict[str, dict[str, str]]:
    items = {}
    for concept_index in range(1, 9):
        path = FR_ROOT / f"C{concept_index}.tsv"
        with path.open(encoding="utf-8", newline="") as handle:
            for line_number, fields in enumerate(csv.reader(handle, delimiter="\t"), 1):
                if not fields:
                    continue
                if len(fields) != 6:
                    raise ValueError(
                        f"{path.name}:{line_number}: expected ID, question, and 4 answers"
                    )
                identifier, question, *answers = fields
                if (not identifier.startswith(("SCR_", "PRE_", "QZ_", "POST_"))
                        or f"_C{concept_index}_" not in identifier
                        or identifier in items or not question.strip()
                        or any(not option.strip() for option in answers)):
                    raise ValueError(f"{path.name}:{line_number}: malformed French item")
                items[identifier] = dict(
                    question_text=question,
                    options=dict(zip("ABCD", answers)),
                )
    if len(items) != 232:
        raise ValueError(f"expected 232 French items, got {len(items)}")
    return items


def validate_french_bank(bank) -> None:
    localized = french_bank()
    english_ids = set(bank.by_id)
    if set(localized) != english_ids:
        missing = sorted(english_ids - set(localized))
        extras = sorted(set(localized) - english_ids)
        raise ValueError(
            f"French bank does not match canonical IDs: missing={missing[:4]}, "
            f"extra={extras[:4]}"
        )
    for identifier, french in localized.items():
        english = bank.by_id[identifier]
        if french["question_text"] == english.question_text:
            raise ValueError(f"{identifier}: untranslated question")
        if len(french["options"]) != 4 or set(french["options"]) != set("ABCD"):
            raise ValueError(f"{identifier}: incomplete French options")
        if len(set(x.casefold() for x in french["options"].values())) != 4:
            raise ValueError(f"{identifier}: repeated French option")


def localize_public(item: dict, *, language: str) -> dict:
    """Transform only display text; preserve the original bank's option keys."""
    if language not in LANGUAGES:
        raise ValueError("language must be en or fr")
    if language == "en":
        return item
    translation = french_bank()[item["question_id"]]
    result = dict(item)
    result["question_text"] = translation["question_text"]
    result["options"] = {
        key: translation["options"][key] for key in item["options"]
    }
    result["language"] = "fr"
    result["translation_review_status"] = "UNREVIEWED_RESEARCH_DRAFT"
    return result
