"""Step 71: provisional study and question-bank validation."""

import pytest

from src.prototype.study_specification import (
    ARMS,
    BLOOM_LEVELS,
    CONCEPTS,
    FORMS,
    MAX_RECOVERY_ATTEMPTS_PER_SESSION,
    POSTTEST_QUESTION_COUNT,
    PRETEST_QUESTION_COUNT,
    RECOVERY_ACTION_ORDER,
    RECOVERY_THRESHOLD,
    SESSION_QUESTION_TARGETS,
    SPEC_VERSION,
    StudyQuestion,
    validate_assessment_selection,
    validate_item_bank,
)


def question(
    item_id="test001",
    form="practice",
    **updates,
):
    fields = dict(
        item_id=item_id,
        form=form,
        concept=CONCEPTS[0],
        bloom_level=BLOOM_LEVELS[0],
        prompt=(
            f"Synthetic fixture {item_id} "
            "(not a study question)"
        ),
        options=(
            ("A", "Fixture A"),
            ("B", "Fixture B"),
            ("C", "Fixture C"),
        ),
        correct_option_id="B",
    )

    fields.update(updates)

    return StudyQuestion(**fields)


def forms():
    pre = [
        question(f"pre{i:03}", "pretest")
        for i in range(16)
    ]

    post = [
        question(f"post{i:03}", "posttest")
        for i in range(16)
    ]

    return (
        pre + post,
        [q.item_id for q in pre],
        [q.item_id for q in post],
    )


def test_historical_specification_is_explicit_and_provisional():
    assert "provisional" in SPEC_VERSION
    assert len(CONCEPTS) == 8
    assert len(BLOOM_LEVELS) == 6

    assert tuple(
        key for key, _ in ARMS
    ) == ("A", "B", "C")

    assert SESSION_QUESTION_TARGETS == (20, 20, 15)

    assert (
        PRETEST_QUESTION_COUNT,
        POSTTEST_QUESTION_COUNT,
    ) == (16, 16)

    assert RECOVERY_THRESHOLD == 0.5
    assert MAX_RECOVERY_ATTEMPTS_PER_SESSION == 2

    assert RECOVERY_ACTION_ORDER == (
        "CONCEPT_SUMMARY",
        "DROP_2",
        "WORKED_EXAMPLE",
        "SOCRATIC_HINT",
    )


def test_valid_draft_bank_is_allowed_without_fake_content():
    counts = validate_item_bank((question(),))

    assert counts["practice"] == 1
    assert all(form in counts for form in FORMS)


@pytest.mark.parametrize(
    "updates",
    [
        {"concept": "Other"},
        {"bloom_level": "invent"},
        {"form": "unknown"},
        {"prompt": "  "},
        {"correct_option_id": "X"},
        {"review_status": "approved"},
        {"item_id": "*"},
        {
            "options": (
                ("A", "a"),
                ("A", "b"),
            )
        },
    ],
)
def test_reject_invalid_items(updates):
    with pytest.raises(ValueError):
        question(**updates)


def test_recovery_drop2_must_have_two_options():
    with pytest.raises(ValueError):
        question(form="recovery_drop2")

    valid = question(
        form="recovery_drop2",
        options=(
            ("A", "a"),
            ("B", "b"),
        ),
    )

    assert valid.form == "recovery_drop2"


def test_duplicate_ids_rejected():
    with pytest.raises(
        ValueError,
        match="duplicate item ID",
    ):
        validate_item_bank(
            [question(), question()]
        )


def test_duplicate_question_wording_rejected_even_if_ids_differ():
    one = question()

    two = question(
        item_id="test002",
        prompt=one.prompt,
    )

    with pytest.raises(
        ValueError,
        match="duplicate question wording",
    ):
        validate_item_bank([one, two])


def test_16_16_distinct_selection_accepted():
    items, pre, post = forms()

    assert validate_assessment_selection(
        items, pre, post
    ) is None


def test_reject_short_pretest():
    items, pre, post = forms()

    with pytest.raises(
        ValueError,
        match="exactly 16",
    ):
        validate_assessment_selection(
            items, pre[:-1], post
        )


def test_reject_duplicate_selected_ids():
    items, pre, post = forms()

    pre[-1] = pre[0]

    with pytest.raises(
        ValueError,
        match="duplicate pretest",
    ):
        validate_assessment_selection(
            items, pre, post
        )


def test_reject_missing_or_wrong_form_item():
    items, pre, post = forms()

    post[0] = pre[0]

    with pytest.raises(
        ValueError,
        match="overlap",
    ):
        validate_assessment_selection(
            items, pre, post
        )

    post[0] = "missing001"

    with pytest.raises(
        ValueError,
        match="missing or wrong-form",
    ):
        validate_assessment_selection(
            items, pre, post
        )
