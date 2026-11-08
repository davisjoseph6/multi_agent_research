"""Frozen behavioral-economics item adapter for OFFLINE synthetic pilot tests.

No participant-facing application uses this module. The current item bank
contains DRAFT, not expert-approved content. It must not be used with humans.

This module integrates item identity, answer key and version fingerprint with
the three-session *synthetic* persistence system. All practice items use a
fixed balanced schedule here; it does NOT implement arm-specific adaptive
POMCP/greedy policies or optional recovery-resource actions.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from .rct_candidate_content import file_digest, read_csv
from .study_v2 import CONCEPTS, Item, validate_bank
from .pilot_session_flow_draft import PRACTICE_TARGETS, PilotSequenceError, PilotSessionFlow


class PilotDraftItemBank:
    def __init__(self, items_csv: str | Path):
        path = Path(items_csv)
        rows = read_csv(path)
        counts = Counter(row["form"] for row in rows)
        if counts != {
            "pretest": 16, "posttest": 16, "practice": 55, "recovery_drop2": 8
        }:
            raise ValueError("expected the exact 95-item candidate bank")
        items = [
            Item(
                item_id=r["item_id"], form=r["form"], concept=r["concept"],
                bloom=r["bloom"], prompt=r["prompt"],
                options=tuple(
                    (k, r["option_" + k]) for k in "ABCD" if r["option_" + k].strip()
                ),
                answer_id=r["correct_option_id"],
                difficulty=float(r["difficulty_estimate"]),
                status="draft",  # DO NOT INFER INDEPENDENT EXPERT APPROVAL
            )
            for r in rows
        ]
        validate_bank(items, full=True)
        self.sha256 = file_digest(path)
        self.by_id = {item.item_id: item for item in items}
        self.forms = {
            form: tuple(sorted(
                (item for item in items if item.form == form),
                key=lambda item: item.item_id,
            ))
            for form in ("pretest", "posttest")
        }
        practice = [item for item in items if item.form == "practice"]
        by_concept = {
            concept: sorted(
                (item for item in practice if item.concept == concept),
                key=lambda item: (item.difficulty, item.item_id),
            )
            for concept in CONCEPTS
        }
        self.practice = tuple(
            item
            for offset in range(max(len(group) for group in by_concept.values()))
            for concept in CONCEPTS
            for item in by_concept[concept][offset:offset+1]
        )
        if len(self.practice) != 55 or len(set(q.item_id for q in self.practice)) != 55:
            raise ValueError("unbalanced or duplicated practice schedule")

    def select(self, state: PilotSessionFlow) -> Item:
        if state.stage in ("pretest", "posttest"):
            form = self.forms[state.stage]
            if not 0 <= state.index < len(form):
                raise PilotSequenceError("assessment index outside frozen item bank")
            return form[state.index]
        if state.stage == "practice":
            if state.session not in (1, 2, 3):
                raise PilotSequenceError("invalid practice visit")
            if not 0 <= state.index < PRACTICE_TARGETS[state.session - 1]:
                raise PilotSequenceError("practice index outside session budget")
            offset = sum(PRACTICE_TARGETS[:state.session - 1]) + state.index
            return self.practice[offset]
        raise PilotSequenceError("question item requested outside MCQ stage")
