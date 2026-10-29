"""Provisional study specification from historical supervisor guidance.

This is a research-design/data-validation boundary, not an approved protocol.
No existing prototype policy or trial allocation is changed by this module.
"""

from dataclasses import dataclass
import re
from typing import Sequence

SPEC_VERSION = "historical_supervisor_provisional_v1"

CONCEPTS = (
    "Utility",
    "Loss Aversion",
    "Anchoring",
    "Sunk Cost",
    "Framing",
    "Heuristics",
    "Prospect Theory",
    "Nudge Theory",
)

BLOOM_LEVELS = (
    "remember",
    "understand",
    "apply",
    "analyze",
    "evaluate",
    "create",
)

ARMS = (
    ("A", "self_healing_adaptive"),
    ("B", "greedy_adaptive_without_recovery"),
    ("C", "fixed_sequence_nonadaptive"),
)

SESSION_QUESTION_TARGETS = (20, 20, 15)

PRETEST_QUESTION_COUNT = 16
POSTTEST_QUESTION_COUNT = 16

RECOVERY_ACTION_ORDER = (
    "CONCEPT_SUMMARY",
    "DROP_2",
    "WORKED_EXAMPLE",
    "SOCRATIC_HINT",
)

RECOVERY_THRESHOLD = 0.5
MAX_RECOVERY_ATTEMPTS_PER_SESSION = 2

FORMS = (
    "pretest",
    "practice",
    "posttest",
    "recovery_drop2",
)

REVIEW_STATUSES = (
    "draft",
    "expert_reviewed",
)

_ITEM_ID = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$"
)


@dataclass(frozen=True)
class StudyQuestion:
    """Server-side authoring record.

    Never expose the answer key to browser clients.
    """

    item_id: str
    form: str
    concept: str
    bloom_level: str
    prompt: str
    options: tuple[tuple[str, str], ...]
    correct_option_id: str
    review_status: str = "draft"

    def __post_init__(self):
        if (
            not isinstance(self.item_id, str)
            or not _ITEM_ID.fullmatch(self.item_id)
        ):
            raise ValueError(
                "item_id must be a 3-64 character safe identifier"
            )

        if self.form not in FORMS:
            raise ValueError("unsupported item form")

        if self.concept not in CONCEPTS:
            raise ValueError("unsupported concept")

        if self.bloom_level not in BLOOM_LEVELS:
            raise ValueError("unsupported Bloom level")

        if (
            not isinstance(self.prompt, str)
            or not self.prompt.strip()
        ):
            raise ValueError("prompt must be nonempty")

        if self.review_status not in REVIEW_STATUSES:
            raise ValueError("invalid review status")

        if not isinstance(self.options, tuple):
            raise ValueError("options must be a tuple")

        count = len(self.options)

        if self.form == "recovery_drop2":
            valid_count = count == 2
        else:
            valid_count = 2 <= count <= 6

        if not valid_count:
            raise ValueError(
                "invalid option count for item form"
            )

        ids = []

        for option in self.options:
            if (
                not isinstance(option, tuple)
                or len(option) != 2
                or not all(
                    isinstance(part, str) and part.strip()
                    for part in option
                )
            ):
                raise ValueError(
                    "options must contain nonempty "
                    "(id, text) pairs"
                )

            ids.append(option[0])

        if len(set(ids)) != len(ids):
            raise ValueError("duplicate option ID")

        if self.correct_option_id not in ids:
            raise ValueError(
                "answer key must refer to a listed option"
            )


def validate_item_bank(
    items: Sequence[StudyQuestion],
) -> dict[str, int]:
    """Validate a draft bank, without claiming educational validity."""

    if any(
        not isinstance(item, StudyQuestion)
        for item in items
    ):
        raise ValueError(
            "all items must be StudyQuestion records"
        )

    ids = [item.item_id for item in items]

    if len(set(ids)) != len(ids):
        raise ValueError("duplicate item ID")

    prompts = [
        " ".join(item.prompt.split()).casefold()
        for item in items
    ]

    if len(set(prompts)) != len(prompts):
        raise ValueError("duplicate question wording")

    return {
        form: sum(
            item.form == form
            for item in items
        )
        for form in FORMS
    }


def validate_assessment_selection(
    items: Sequence[StudyQuestion],
    pretest_ids: Sequence[str],
    posttest_ids: Sequence[str],
) -> None:
    """Check selected assessment IDs, not psychometric validity."""

    validate_item_bank(items)

    if len(pretest_ids) != PRETEST_QUESTION_COUNT:
        raise ValueError(
            "pretest must select exactly 16 item IDs"
        )

    if len(posttest_ids) != POSTTEST_QUESTION_COUNT:
        raise ValueError(
            "posttest must select exactly 16 item IDs"
        )

    if len(set(pretest_ids)) != len(pretest_ids):
        raise ValueError("duplicate pretest selection")

    if len(set(posttest_ids)) != len(posttest_ids):
        raise ValueError("duplicate posttest selection")

    if set(pretest_ids) & set(posttest_ids):
        raise ValueError(
            "pretest and posttest item IDs must not overlap"
        )

    lookup = {
        item.item_id: item
        for item in items
    }

    for item_id in pretest_ids:
        if (
            item_id not in lookup
            or lookup[item_id].form != "pretest"
        ):
            raise ValueError(
                "pretest selection refers to "
                "missing or wrong-form item"
            )

    for item_id in posttest_ids:
        if (
            item_id not in lookup
            or lookup[item_id].form != "posttest"
        ):
            raise ValueError(
                "posttest selection refers to "
                "missing or wrong-form item"
            )
