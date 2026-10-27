"""Local-only fixed-sequence quiz session engine.

Supports multiple practice items followed by distinct
independent probes, without delivering assistance.

No database, authentication, concurrency guarantees,
human-study permissions, or fitted learning model.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.prototype.item_bank import (
    QuizItem,
    validate_item_bank,
)


@dataclass(frozen=True)
class ResponseRecord:
    """Private record of an accepted quiz response."""

    bank_version: str
    position: int
    item_id: str
    concept_id: str
    kind: str
    choice_id: str
    correct: bool


class FixedQuizSession:
    """One local session following a validated question sequence."""

    def __init__(
        self,
        *,
        items: tuple[QuizItem, ...],
        bank_version: str,
    ) -> None:
        validate_item_bank(items)

        if (
            type(bank_version) is not str
            or not bank_version.strip()
        ):
            raise ValueError("Invalid item-bank version")

        # The initial recovery-assessment protocol requires
        # all practice before all independent probes.
        probe_phase_started = False

        for item in items:
            if item.kind == "independent_probe":
                probe_phase_started = True
            elif probe_phase_started:
                raise ValueError(
                    "Practice cannot follow an independent probe"
                )

        self._items = items
        self._bank_version = bank_version
        self._index = 0
        self._responses: list[ResponseRecord] = []

    @property
    def bank_version(self) -> str:
        return self._bank_version

    @property
    def completed(self) -> bool:
        return self._index >= len(self._items)

    @property
    def position(self) -> int:
        return self._index

    @property
    def responses(self) -> tuple[ResponseRecord, ...]:
        """Return an immutable snapshot of internal responses."""
        return tuple(self._responses)

    @property
    def current_item(self) -> QuizItem | None:
        if self.completed:
            return None

        return self._items[self._index]

    def current_public_question(self) -> dict | None:
        """Return a student-facing question without its answer."""
        item = self.current_item

        if item is None:
            return None

        return item.public_dict()

    def submit(
        self,
        *,
        item_id: str,
        choice_id: str,
    ) -> ResponseRecord:
        """Accept exactly one valid answer for the current item.

        The returned record is private backend data and
        must not be serialized directly to students.
        """
        item = self.current_item

        if item is None:
            raise ValueError("Session already complete")

        if type(item_id) is not str or item_id != item.item_id:
            raise ValueError("Unexpected question ID")

        valid_choices = {
            choice_identifier
            for choice_identifier, _ in item.choices
        }

        if (
            type(choice_id) is not str
            or choice_id not in valid_choices
        ):
            raise ValueError("Invalid answer choice")

        record = ResponseRecord(
            bank_version=self._bank_version,
            position=self._index,
            item_id=item.item_id,
            concept_id=item.concept_id,
            kind=item.kind,
            choice_id=choice_id,
            correct=(choice_id == item.correct_id),
        )

        self._responses.append(record)
        self._index += 1

        return record
