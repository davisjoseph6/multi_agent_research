"""Tests for chronological NeuralCD evaluation and state isolation."""

import pytest

from src.evaluation.neuralcd_stream import (
    Interaction,
    evaluate_histories,
    evaluate_student,
)


class FakeAdapter:
    """An observable adapter for testing operation order."""

    def __init__(self):
        self.observations = 0
        self.labels = []
        self.trace = []

    def supported(self, item_idx):
        return item_idx in (0, 1)

    def predict(self, item_idx):
        self.trace.append(("predict", item_idx))

        # Depends exclusively on already observed labels.
        return 0.4 + 0.1 * sum(self.labels)

    def observe(self, item_idx, correct):
        self.trace.append(("observe", item_idx, correct))
        self.labels.append(correct)
        self.observations += 1
        return True


def event(
    order,
    label,
    *,
    student="A",
    item=0,
    target=True,
    source=None,
):
    return Interaction(
        student_id=student,
        source_row=order if source is None else source,
        event_order=order,
        item_idx=item,
        correct=label,
        is_primary_target=target,
    )


def test_predict_before_observe():
    adapter = FakeAdapter()

    predictions, summary = evaluate_student(
        [event(1, 1)],
        adapter,
    )

    assert predictions[0]["predicted_probability"] == 0.4
    assert predictions[0]["prior_supported_observations"] == 0

    assert adapter.trace == [
        ("predict", 0),
        ("observe", 0, 1),
    ]

    assert summary["scored_targets"] == 1


def test_scaffolding_updates_history_but_is_not_scored():
    adapter = FakeAdapter()

    predictions, summary = evaluate_student(
        [
            event(1, 1, target=False),
            event(2, 0),
        ],
        adapter,
    )

    assert len(predictions) == 1
    assert predictions[0]["source_row"] == 2
    assert predictions[0]["predicted_probability"] == pytest.approx(0.5)
    assert predictions[0]["prior_supported_observations"] == 1

    assert summary["supported_history_updates"] == 2
    assert summary["scored_targets"] == 1


def test_future_response_cannot_change_previous_prediction():
    first, _ = evaluate_student(
        [event(1, 1), event(2, 1)],
        FakeAdapter(),
    )

    second, _ = evaluate_student(
        [event(1, 0), event(2, 0)],
        FakeAdapter(),
    )

    # Both learners have exactly the same state BEFORE event 1.
    assert first[0]["predicted_probability"] == pytest.approx(0.4)
    assert second[0]["predicted_probability"] == pytest.approx(0.4)

    # Their event-2 predictions may differ, using event-1 history.
    assert first[1]["predicted_probability"] == pytest.approx(0.5)
    assert second[1]["predicted_probability"] == pytest.approx(0.4)


def test_unsupported_items_are_not_scored_or_used_for_adaptation():
    adapter = FakeAdapter()

    predictions, summary = evaluate_student(
        [
            event(1, 1, item=2),
            event(2, 0, item=3, target=False),
            event(3, 1, item=0),
        ],
        adapter,
    )

    assert len(predictions) == 1
    assert predictions[0]["source_row"] == 3
    assert predictions[0]["predicted_probability"] == pytest.approx(0.4)

    assert summary["primary_targets"] == 2
    assert summary["scored_targets"] == 1
    assert summary["unsupported_targets"] == 1
    assert summary["unsupported_history_events"] == 2
    assert adapter.observations == 1


def test_new_student_gets_fresh_adapter():
    adapters = []

    def make_adapter():
        adapter = FakeAdapter()
        adapters.append(adapter)
        return adapter

    histories = {
        "A": [event(1, 1, student="A", source=10)],
        "B": [event(1, 0, student="B", source=20)],
    }

    predictions, summaries = evaluate_histories(
        histories,
        make_adapter,
    )

    assert len(adapters) == 2
    assert adapters[0] is not adapters[1]
    assert len(predictions) == 2
    assert len(summaries) == 2

    assert all(
        row["predicted_probability"] == pytest.approx(0.4)
        for row in predictions
    )


def test_out_of_order_sequence_is_rejected_before_updates():
    adapter = FakeAdapter()

    with pytest.raises(ValueError, match="increasing"):
        evaluate_student(
            [event(2, 1), event(1, 0)],
            adapter,
        )

    assert adapter.trace == []
    assert adapter.observations == 0


def test_duplicate_source_row_across_students_is_rejected():
    histories = {
        "A": [event(1, 1, student="A", source=10)],
        "B": [event(1, 0, student="B", source=10)],
    }

    with pytest.raises(ValueError, match="multiple student"):
        evaluate_histories(
            histories,
            FakeAdapter,
        )


def test_prediction_must_not_change_adaptation_state():
    class FaultyAdapter(FakeAdapter):
        def predict(self, item_idx):
            self.observations += 1
            return 0.5

    with pytest.raises(RuntimeError, match="Prediction unexpectedly"):
        evaluate_student(
            [event(1, 1)],
            FaultyAdapter(),
        )
