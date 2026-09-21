"""Tests for causal cold-start NeuralCD student adaptation."""

from __future__ import annotations

import copy

import numpy as np
import pytest
import torch

from src.evaluation.neuralcd_online import OnlineStudentAdapter
from src.models.neuralcd import NeuralCDM


def make_adapter():
    torch.manual_seed(7)

    model = NeuralCDM(
        n_students=3,
        n_items=3,
        n_concepts=2,
    )

    q = np.array([
        [1, 0],
        [0, 1],
        [1, 1],
    ], dtype=np.uint8)

    seen = np.array(
        [True, True, False],
        dtype=bool,
    )

    adapter = OnlineStudentAdapter(
        model,
        q,
        seen,
        learning_rate=0.1,
        prior_penalty=0.01,
        device="cpu",
    )

    return model, adapter


def test_initial_state_comes_from_training_embeddings():
    model, adapter = make_adapter()

    expected = (
        model.student_emb.weight
        .detach()
        .mean(dim=0)
    )

    torch.testing.assert_close(
        adapter.local_logits.detach(),
        expected,
    )

    assert adapter.observations == 0


def test_prediction_does_not_update_student():
    _, adapter = make_adapter()

    before = adapter.local_logits.detach().clone()

    prediction = adapter.predict(0)

    assert prediction is not None
    assert 0 < prediction < 1

    torch.testing.assert_close(
        before,
        adapter.local_logits.detach(),
    )

    assert adapter.observations == 0


def test_current_label_cannot_affect_current_prediction():
    model, first = make_adapter()

    # Two separate students begin with the same training prior.
    second = OnlineStudentAdapter(
        model,
        first.q.cpu().numpy(),
        first.seen,
        learning_rate=0.1,
        prior_penalty=0.01,
    )

    p_first = first.predict(0)
    p_second = second.predict(0)

    assert p_first == pytest.approx(p_second)

    # Different observed responses arrive AFTER prediction.
    assert first.observe(0, 1)
    assert second.observe(0, 0)

    assert first.observations == 1
    assert second.observations == 1


def test_global_model_parameters_remain_unchanged():
    model, adapter = make_adapter()

    before = {
        name: value.detach().clone()
        for name, value in model.state_dict().items()
    }

    adapter.predict(0)
    adapter.observe(0, 1)
    adapter.predict(1)
    adapter.observe(1, 0)

    for name, value in model.state_dict().items():
        torch.testing.assert_close(
            before[name],
            value,
        )

    assert all(
        not parameter.requires_grad
        for parameter in model.parameters()
    )

    assert adapter.observations == 2


def test_untrained_item_is_not_used():
    _, adapter = make_adapter()

    before = adapter.local_logits.detach().clone()

    assert adapter.predict(2) is None
    assert adapter.observe(2, 1) is False

    assert adapter.observations == 0

    torch.testing.assert_close(
        before,
        adapter.local_logits.detach(),
    )


def test_invalid_label_is_rejected():
    _, adapter = make_adapter()

    with pytest.raises(ValueError):
        adapter.observe(0, 2)


def test_mastery_proxy_has_correct_shape():
    _, adapter = make_adapter()

    proxy = adapter.mastery_proxy()

    assert proxy.shape == (2,)
    assert np.isfinite(proxy).all()
    assert np.all((proxy > 0) & (proxy < 1))


def test_invalid_q_shape_is_rejected():
    torch.manual_seed(7)

    model = NeuralCDM(3, 3, 2)

    with pytest.raises(ValueError):
        OnlineStudentAdapter(
            model,
            np.zeros((3, 4)),
            np.ones(3, dtype=bool),
        )
