"""Chronological, prequential evaluation for adapted NeuralCD.

This module performs no model training and reads no dataset partitions.
A separate driver must supply only the intended evaluation histories.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Interaction:
    student_id: str
    source_row: int
    event_order: int
    item_idx: int
    correct: int
    is_primary_target: bool


class StudentAdapter(Protocol):
    observations: int

    def supported(self, item_idx: int) -> bool:
        ...

    def predict(self, item_idx: int) -> float | None:
        ...

    def observe(self, item_idx: int, correct: int) -> bool:
        ...


def evaluate_student(
    events: Sequence[Interaction],
    adapter: StudentAdapter,
) -> tuple[list[dict], dict]:
    """Evaluate one learner without current-response leakage."""

    if not events:
        raise ValueError("Student history is empty")

    student_id = events[0].student_id

    if not student_id:
        raise ValueError("Missing student ID")

    if adapter.observations != 0:
        raise ValueError(
            "Adapter must be newly initialized for this student"
        )

    previous_order = None
    source_rows = set()

    # Validate the entire sequence before mutating any student state.
    for event in events:
        if event.student_id != student_id:
            raise ValueError("Mixed student IDs in one history")

        if event.correct not in (0, 1):
            raise ValueError("Nonbinary response")

        if previous_order is not None:
            if event.event_order <= previous_order:
                raise ValueError(
                    "Events must be in strictly increasing order"
                )

        if event.source_row in source_rows:
            raise ValueError("Duplicate source row")

        source_rows.add(event.source_row)
        previous_order = event.event_order

    predictions = []

    counts = {
        "student_id": student_id,
        "events": len(events),
        "primary_targets": 0,
        "scored_targets": 0,
        "unsupported_targets": 0,
        "supported_history_updates": 0,
        "unsupported_history_events": 0,
    }

    for event in events:
        supported = adapter.supported(event.item_idx)

        if event.is_primary_target:
            counts["primary_targets"] += 1

        if not supported:
            counts["unsupported_history_events"] += 1

            if event.is_primary_target:
                counts["unsupported_targets"] += 1

            # Never adapt using untrained item embeddings.
            continue

        prior_updates = adapter.observations

        # CRITICAL: predict before revealing the current response.
        probability = adapter.predict(event.item_idx)

        if probability is None:
            raise RuntimeError(
                "Supported item unexpectedly returned no prediction"
            )

        if not 0.0 < probability < 1.0:
            raise RuntimeError(
                "Prediction must be a probability in (0, 1)"
            )

        if adapter.observations != prior_updates:
            raise RuntimeError(
                "Prediction unexpectedly changed adaptation state"
            )

        if event.is_primary_target:
            predictions.append({
                "source_row": event.source_row,
                "student_id": student_id,
                "event_order": event.event_order,
                "item_idx": event.item_idx,
                "observed_correct": event.correct,
                "predicted_probability": float(probability),
                "prior_supported_observations": prior_updates,
            })

            counts["scored_targets"] += 1

        # Only NOW is the current outcome supplied to the adapter.
        updated = adapter.observe(event.item_idx, event.correct)

        if not updated:
            raise RuntimeError(
                "Supported item unexpectedly rejected observation"
            )

        if adapter.observations != prior_updates + 1:
            raise RuntimeError(
                "Adapter did not perform exactly one history update"
            )

        counts["supported_history_updates"] += 1

    if (
        counts["scored_targets"]
        + counts["unsupported_targets"]
        != counts["primary_targets"]
    ):
        raise AssertionError("Primary-target accounting failed")

    return predictions, counts


def evaluate_histories(
    histories: Mapping[str, Sequence[Interaction]],
    make_adapter: Callable[[], StudentAdapter],
) -> tuple[list[dict], list[dict]]:
    """Initialize a fresh adapter for every distinct learner."""

    predictions = []
    summaries = []
    global_source_rows = set()

    for student_id, events in histories.items():
        if not events:
            raise ValueError(
                f"Empty history for student {student_id}"
            )

        if str(student_id) != events[0].student_id:
            raise ValueError("History key and student ID disagree")

        # Create an independent local student state.
        adapter = make_adapter()

        student_predictions, summary = evaluate_student(
            events,
            adapter,
        )

        for event in events:
            if event.source_row in global_source_rows:
                raise ValueError(
                    "Source row occurs in multiple student histories"
                )

            global_source_rows.add(event.source_row)

        predictions.extend(student_predictions)
        summaries.append(summary)

    return predictions, summaries
