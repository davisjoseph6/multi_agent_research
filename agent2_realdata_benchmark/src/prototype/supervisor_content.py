"""Strict ingestion of the 2026-11-11 supervisor's distinct CSV forms.

The supplied items are NOT automatically expert-approved just because this
schema is valid. The 192-item practice bank alone is eligible for adaptive
selection. Screening, pretest, and posttest must never teach or update BKT.
"""
from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

from .supervisor_trace_engine import CONCEPT_IDS, SESSION_BLOCKS

FORM_FILES = {
    "screening": "screening_test.csv",
    "pretest": "pretest.csv",
    "practice": "quiz_bank_192.csv",
    "posttest": "posttest.csv",
}
KEYS = "ABCD"
COMMON_FIELDS = {
    "question_id", "concept_id", "concept_name", "bloom_level",
    "bloom_label", "question_text", "option_A", "option_B", "option_C",
    "option_D", "correct_answer", "explanation",
}


@dataclass(frozen=True)
class SupervisorItem:
    question_id: str
    concept: str
    level: int
    form: str
    question_text: str
    options: tuple[str, str, str, str]
    correct_answer: str
    explanation: str

    def public(self):
        """Never reveal scoring data or explanations in assessment UI."""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "options": dict(zip(KEYS, self.options)),
        }


class SupervisorBank:
    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        if not self.folder.is_dir():
            raise ValueError("required supervisor bank folder is missing")
        self.forms: dict[str, tuple[SupervisorItem, ...]] = {}
        self.by_id: dict[str, SupervisorItem] = {}
        self.sha256: dict[str, str] = {}
        all_normalized_text: set[str] = set()
        for form, filename in FORM_FILES.items():
            path = self.folder / filename
            raw = path.read_bytes()
            self.sha256[filename] = sha256(raw).hexdigest()
            with path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                if not COMMON_FIELDS.issubset(reader.fieldnames or ()):
                    raise ValueError(f"{filename}: missing required columns")
                rows = list(reader)
            expected_count = {"screening": 8, "pretest": 16,
                              "practice": 192, "posttest": 16}[form]
            if len(rows) != expected_count:
                raise ValueError(f"{filename}: expected {expected_count} rows")
            items = []
            for row in rows:
                identifier = row["question_id"].strip()
                concept = row["concept_id"].strip()
                level_text = row["bloom_level"].strip()
                if concept not in CONCEPT_IDS or level_text not in (
                    "1", "2", "3", "4", "5", "6",
                ):
                    raise ValueError("unknown concept or Bloom level")
                level = int(level_text)
                prefix = {"screening": "SCR", "pretest": "PRE",
                          "practice": "QZ", "posttest": "POST"}[form]
                expected_pattern = (
                    rf"{prefix}_{concept}_L{level}_\d{{2}}"
                )
                if not re.fullmatch(expected_pattern, identifier):
                    raise ValueError(f"question ID/form mismatch: {identifier}")
                answer = row["correct_answer"].strip()
                options = tuple(row[f"option_{key}"].strip() for key in KEYS)
                normalized_options = [x.casefold() for x in options]
                prompt = row["question_text"].strip()
                normalized_prompt = " ".join(prompt.casefold().split())
                if (answer not in KEYS or not prompt
                        or any(not x for x in options)
                        or len(set(normalized_options)) != 4
                        or normalized_prompt in all_normalized_text):
                    raise ValueError(f"invalid or repeated question: {identifier}")
                if identifier in self.by_id:
                    raise ValueError(f"cross-form question ID collision: {identifier}")
                all_normalized_text.add(normalized_prompt)
                item = SupervisorItem(
                    identifier, concept, level, form, prompt, options,
                    answer, row["explanation"].strip(),
                )
                items.append(item)
                self.by_id[identifier] = item
            self.forms[form] = tuple(items)
        self._check_coverage()

    def _check_coverage(self):
        for concept in CONCEPT_IDS:
            for level in range(1, 7):
                count = sum(
                    x.concept == concept and x.level == level
                    for x in self.forms["practice"]
                )
                if count != (6 if level in (1, 2) else 3):
                    raise ValueError("192-item practice bank has invalid coverage")
            screen = [x for x in self.forms["screening"] if x.concept == concept]
            if len(screen) != 1 or screen[0].level != 1:
                raise ValueError("screening must be one L1 item per concept")
            for form in ("pretest", "posttest"):
                levels = sorted(x.level for x in self.forms[form]
                                if x.concept == concept)
                if levels != [2, 3]:
                    raise ValueError(f"{form}: expected L2 and L3 per concept")
        if len(self.forms["practice"]) < sum(SESSION_BLOCKS):
            raise ValueError("insufficient adaptive quiz inventory")

    def get(self, question_id: str, *, form: str) -> SupervisorItem:
        item = self.by_id.get(question_id)
        if item is None or item.form != form:
            raise ValueError("item is not valid for the requested phase")
        return item

    def grade(self, question_id: str, choice: str, *, form: str) -> bool:
        if type(choice) is not str or choice not in KEYS:
            raise ValueError("answer must be one of A, B, C, D")
        return self.get(question_id, form=form).correct_answer == choice

    def initialize_qmatrix(self, answers: dict[str, str]) -> dict[str, float]:
        """Score pretest once; independent pretest does NOT teach."""
        test = self.forms["pretest"]
        if set(answers) != {q.question_id for q in test}:
            raise ValueError("exactly all 16 pretest responses required")
        correct_by_concept = Counter(
            item.concept for item in test
            if self.grade(item.question_id, answers[item.question_id],
                          form="pretest")
        )
        return {
            c: {0: 0.20, 1: 0.50, 2: 0.75}[correct_by_concept[c]]
            for c in CONCEPT_IDS
        }

    def eligible(self, *, econ_course: bool,
                 screening_answers: dict[str, str]) -> tuple[bool, int]:
        """Cutoff is six; ineligible candidates do not consume arm rotation."""
        if type(econ_course) is not bool:
            raise ValueError("economics background must be explicit boolean")
        # Explicit economics course exclusion happens BEFORE screening, as
        # required by Experimentation.pdf's registration instructions.
        if econ_course:
            return False, 0
        screening = self.forms["screening"]
        if set(screening_answers) != {
            q.question_id for q in screening
        }:
            raise ValueError("exactly eight screening responses required")
        score = sum(
            self.grade(q.question_id, screening_answers[q.question_id],
                       form="screening")
            for q in screening
        )
        return (not econ_course and score < 6), score

    def group_c_order(self) -> tuple[str, ...]:
        return tuple(
            f"QZ_C{concept}_L{level}_{i:02d}"
            for level in range(1, 7)
            for concept in range(1, 9)
            for i in range(1, 4)
        )[:sum(SESSION_BLOCKS)]
