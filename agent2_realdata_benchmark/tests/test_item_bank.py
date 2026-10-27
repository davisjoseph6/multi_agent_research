"""Structural tests for the illustrative versioned item bank."""

from dataclasses import FrozenInstanceError, replace

import pytest

from src.prototype.item_bank import (
    BANK_VERSION,
    DEMO_ITEMS,
    QuizItem,
    demo_items_as_dicts,
    validate_item_bank,
)


def test_version_is_explicit():
    assert BANK_VERSION == "loss_aversion_demo_v1"


def test_existing_item_sequence_is_preserved():
    assert [item.item_id for item in DEMO_ITEMS] == [
        "demo_main_1",
        "demo_probe_1",
    ]


def test_concept_mapping_and_kinds():
    assert {item.concept_id for item in DEMO_ITEMS} == {
        "loss_aversion"
    }

    assert DEMO_ITEMS[0].kind == "practice"
    assert DEMO_ITEMS[1].kind == "independent_probe"


def test_public_questions_never_expose_answer_keys():
    for item in DEMO_ITEMS:
        public = item.public_dict()

        assert "correct_id" not in public
        assert "correct" not in public
        assert "answer_key" not in public
        assert public["id"] == item.item_id


def test_correctness_keys_remain_internal():
    internal = demo_items_as_dicts()

    assert internal[0]["correct_id"] == "B"
    assert internal[1]["correct_id"] == "A"


def test_duplicate_question_id_rejected():
    duplicate = replace(
        DEMO_ITEMS[1],
        item_id=DEMO_ITEMS[0].item_id,
    )

    with pytest.raises(ValueError, match="Duplicate question"):
        validate_item_bank((DEMO_ITEMS[0], duplicate))


def test_duplicate_prompt_rejected():
    duplicate = replace(
        DEMO_ITEMS[1],
        prompt=DEMO_ITEMS[0].prompt,
    )

    with pytest.raises(ValueError, match="Duplicate question prompts"):
        validate_item_bank((DEMO_ITEMS[0], duplicate))


def test_uncovered_probe_concept_rejected():
    invalid = replace(
        DEMO_ITEMS[1],
        concept_id="unrepresented_concept",
    )

    with pytest.raises(ValueError, match="Probe concept"):
        validate_item_bank((DEMO_ITEMS[0], invalid))


@pytest.mark.parametrize("level", [0, 7, True, 2.5])
def test_invalid_bloom_levels_rejected(level):
    with pytest.raises(ValueError, match="Bloom"):
        replace(DEMO_ITEMS[0], bloom_level=level)


def test_invalid_answer_key_rejected():
    with pytest.raises(ValueError, match="Answer key"):
        replace(DEMO_ITEMS[0], correct_id="Z")


def test_duplicate_choices_rejected():
    with pytest.raises(ValueError, match="Duplicate choice"):
        replace(
            DEMO_ITEMS[0],
            choices=(
                ("A", "First choice"),
                ("A", "Second choice"),
            ),
        )


def test_items_are_immutable():
    with pytest.raises(FrozenInstanceError):
        DEMO_ITEMS[0].correct_id = "A"


def test_bank_requires_practice_and_probe():
    with pytest.raises(ValueError, match="Both practice"):
        validate_item_bank((DEMO_ITEMS[0],))


def test_bank_rejects_wrong_item_types():
    with pytest.raises(TypeError):
        validate_item_bank((DEMO_ITEMS[0], object()))
