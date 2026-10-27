"""Versioned, illustrative Behavioral Economics demo item bank.

These items are software-development fixtures, not validated
assessment instruments or approved human-study materials.

The correct answers must remain on the server.
"""

from __future__ import annotations

from dataclasses import dataclass


BANK_VERSION = "loss_aversion_demo_v1"

ALLOWED_KINDS = frozenset({
    "practice",
    "independent_probe",
})


@dataclass(frozen=True)
class QuizItem:
    """Immutable item with separate public and private fields."""

    item_id: str
    kind: str
    concept_id: str
    bloom_level: int
    prompt: str
    choices: tuple[tuple[str, str], ...]
    correct_id: str

    def __post_init__(self) -> None:
        for name in (
            "item_id",
            "kind",
            "concept_id",
            "prompt",
            "correct_id",
        ):
            value = getattr(self, name)

            if type(value) is not str or not value.strip():
                raise ValueError(f"Invalid {name}")

        if self.kind not in ALLOWED_KINDS:
            raise ValueError("Unknown item kind")

        if (
            type(self.bloom_level) is not int
            or not 1 <= self.bloom_level <= 6
        ):
            raise ValueError("Bloom level must be an integer in 1..6")

        if type(self.choices) is not tuple:
            raise TypeError("Choices must be a tuple")

        if len(self.choices) < 2:
            raise ValueError("At least two choices required")

        ids = []

        for choice in self.choices:
            if type(choice) is not tuple or len(choice) != 2:
                raise ValueError("Invalid choice structure")

            choice_id, text = choice

            if (
                type(choice_id) is not str
                or not choice_id.strip()
                or type(text) is not str
                or not text.strip()
            ):
                raise ValueError("Invalid choice")

            ids.append(choice_id)

        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate choice identifiers")

        if self.correct_id not in ids:
            raise ValueError("Answer key not found among choices")

    def public_dict(self) -> dict:
        """Student-facing representation without the answer key."""

        return {
            "id": self.item_id,
            "kind": self.kind,
            "concept_id": self.concept_id,
            "prompt": self.prompt,
            "choices": [
                {"id": choice_id, "text": text}
                for choice_id, text in self.choices
            ],
        }

    def internal_dict(self) -> dict:
        """Legacy API-compatible server-side representation."""

        return {
            **self.public_dict(),
            "correct_id": self.correct_id,
        }


def validate_item_bank(items: tuple[QuizItem, ...]) -> None:
    """Validate IDs, concepts, and practice/probe separation."""

    if type(items) is not tuple or not items:
        raise ValueError("Expected nonempty item tuple")

    if any(type(item) is not QuizItem for item in items):
        raise TypeError("Expected QuizItem instances")

    identifiers = [item.item_id for item in items]
    prompts = [item.prompt.strip().casefold() for item in items]

    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate question identifiers")

    if len(prompts) != len(set(prompts)):
        raise ValueError("Duplicate question prompts")

    practice_concepts = {
        item.concept_id
        for item in items
        if item.kind == "practice"
    }

    probe_concepts = {
        item.concept_id
        for item in items
        if item.kind == "independent_probe"
    }

    if not practice_concepts or not probe_concepts:
        raise ValueError("Both practice and probes are required")

    if not probe_concepts.issubset(practice_concepts):
        raise ValueError("Probe concept lacks practice coverage")


DEMO_ITEMS = (
    QuizItem(
        item_id="demo_main_1",
        kind="practice",
        concept_id="loss_aversion",
        bloom_level=1,
        prompt=(
            "Which concept describes losses being felt more "
            "strongly than equivalent gains?"
        ),
        choices=(
            ("A", "Anchoring"),
            ("B", "Loss aversion"),
            ("C", "Mental accounting"),
        ),
        correct_id="B",
    ),
    QuizItem(
        item_id="demo_probe_1",
        kind="independent_probe",
        concept_id="loss_aversion",
        bloom_level=2,
        prompt=(
            "Which observation is most consistent with "
            "loss aversion?"
        ),
        choices=(
            (
                "A",
                "Avoiding a loss matters more than "
                "an equally sized gain",
            ),
            ("B", "Losses and gains always feel identical"),
            ("C", "Prior prices never affect decisions"),
        ),
        correct_id="A",
    ),
)

validate_item_bank(DEMO_ITEMS)


def demo_items_as_dicts() -> tuple[dict, ...]:
    """Preserve the existing development API's internal format."""

    return tuple(item.internal_dict() for item in DEMO_ITEMS)

# Illustrative multi-practice content, not a validated instrument.
INSTRUCTIONAL_DEMO_VERSION = "loss_aversion_multipractice_demo_v1"

INSTRUCTIONAL_DEMO_ITEMS = (
    DEMO_ITEMS[0],
    QuizItem(
        item_id="demo_main_2",
        kind="practice",
        concept_id="loss_aversion",
        bloom_level=2,
        prompt=(
            "A participant says losing a €20 voucher would "
            "feel more painful than receiving the same voucher "
            "would feel pleasant. Which concept best describes "
            "this pattern?"
        ),
        choices=(
            ("A", "Present bias"),
            ("B", "Loss aversion"),
            ("C", "Base-rate neglect"),
        ),
        correct_id="B",
    ),
    QuizItem(
        item_id="demo_main_3",
        kind="practice",
        concept_id="loss_aversion",
        bloom_level=2,
        prompt="Which pair of reactions is most consistent with loss aversion?",
        choices=(
            ("A", "An unexpected €10 fee feels exactly as bad as a €10 discount feels good"),
            ("B", "An unexpected €10 fee feels more unpleasant than a €10 discount feels pleasant"),
            ("C", "An unexpected €10 discount feels more pleasant than a €10 fee feels unpleasant"),
        ),
        correct_id="B",
    ),
    DEMO_ITEMS[1],
)

validate_item_bank(INSTRUCTIONAL_DEMO_ITEMS)
