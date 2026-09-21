#!/usr/bin/env python3
"""Test NeuralCDM architecture and reference equivalence."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import torch

from src.models.neuralcd import NeuralCDM


def example():
    torch.manual_seed(7)

    model = NeuralCDM(
        n_students=3,
        n_items=4,
        n_concepts=3,
    )

    model.eval()

    students = torch.tensor([0, 1], dtype=torch.long)
    items = torch.tensor([0, 2], dtype=torch.long)

    q = torch.tensor(
        [[1., 0., 0.],
         [0., 1., 1.]],
    )

    return model, students, items, q


def test_prediction_shape_and_range():
    model, students, items, q = example()

    with torch.no_grad():
        result = model(students, items, q)

    assert result.shape == (2, 1)
    assert torch.isfinite(result).all()
    assert ((result > 0) & (result < 1)).all()


def test_reference_forward_equivalence():
    """Compare against the checked-out authors' reference model."""
    path = (
        Path.home()
        / "research_references/NeuralCD/model.py"
    )

    assert path.is_file(), (
        f"Reference model missing: {path}"
    )

    spec = importlib.util.spec_from_file_location(
        "reference_neuralcd_model",
        path,
    )

    assert spec is not None
    assert spec.loader is not None

    reference_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference_module)

    model, students, items, q = example()

    reference = reference_module.Net(
        student_n=3,
        exer_n=4,
        knowledge_n=3,
    )

    # This verifies equality of the computational architectures,
    # not equality between independently randomized models.
    reference.load_state_dict(model.state_dict())

    model.eval()
    reference.eval()

    with torch.no_grad():
        ours = model(students, items, q)
        theirs = reference(students, items, q)

    torch.testing.assert_close(
        ours,
        theirs,
        rtol=1e-6,
        atol=1e-7,
    )


def test_nonnegative_prediction_weights():
    model, _, _, _ = example()

    for layer in (
        model.prednet_full1,
        model.prednet_full2,
        model.prednet_full3,
    ):
        assert torch.all(layer.weight >= 0)

    with torch.no_grad():
        model.prednet_full1.weight[0, 0] = -5.0

    model.apply_clipper()

    assert torch.all(model.prednet_full1.weight >= 0)
    assert model.prednet_full1.weight[0, 0] == 0


def test_unannotated_questions_are_rejected():
    model, students, items, q = example()

    q[0] = 0.0

    with pytest.raises(ValueError):
        model(students, items, q)


def test_mastery_monotonicity():
    model, _, _, _ = example()

    item = torch.tensor([0], dtype=torch.long)
    q = torch.tensor([[1., 0., 0.]])

    lower = torch.zeros(1, 3)
    higher = lower.clone()
    higher[0, 0] += 4.0

    with torch.no_grad():
        p_lower = model.predict_with_student_logits(
            lower, item, q
        )
        p_higher = model.predict_with_student_logits(
            higher, item, q
        )

    assert p_higher.item() >= p_lower.item() - 1e-7


def test_irrelevant_concept_does_not_change_prediction():
    model, _, _, _ = example()

    item = torch.tensor([0], dtype=torch.long)
    q = torch.tensor([[1., 0., 0.]])

    original = torch.zeros(1, 3)
    changed = original.clone()
    changed[0, 2] += 5.0

    with torch.no_grad():
        first = model.predict_with_student_logits(
            original, item, q
        )
        second = model.predict_with_student_logits(
            changed, item, q
        )

    torch.testing.assert_close(first, second)


def test_local_student_logits_receive_gradients():
    model, _, _, _ = example()

    # Simulate the frozen global model used for cold-start inference.
    model.requires_grad_(False)
    model.eval()

    local_logits = torch.zeros(
        1, 3,
        requires_grad=True,
    )

    item = torch.tensor([0], dtype=torch.long)
    q = torch.tensor([[1., 0., 0.]])

    prediction = model.predict_with_student_logits(
        local_logits,
        item,
        q,
    )

    prediction.sum().backward()

    assert local_logits.grad is not None
    assert torch.isfinite(local_logits.grad).all()

    # The inference graph should not optimize global model weights.
    assert all(
        parameter.grad is None
        for parameter in model.parameters()
    )
