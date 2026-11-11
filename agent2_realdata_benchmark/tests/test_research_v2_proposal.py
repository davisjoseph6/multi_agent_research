"""Explicit V2 gates: never silently convert the prior parallel trial."""
from datetime import datetime, timedelta, timezone

import pytest

from src.prototype.research_v2_proposal import (
    CrossoverProgress, EMAIL_TEMPLATES, MIN_DISTINCT_CROSSOVER_ITEMS,
    PauseEpisode, ProposedStudyError, ReviewedItem, TwoWrongRecovery,
    all_sequences, bkt_trace, ordered_arms, validate_cross_language_bank,
    visible_item,
)
from src.prototype.study_v2 import CONCEPTS, RECOVERY_ACTIONS


T0 = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)


def _items(*, all_translated=True):
    rows = []
    for period in range(3):
        for form, count in (("pretest", 16), ("practice", 55), ("posttest", 16)):
            for index in range(count):
                n = f"{period}-{form}-{index}"
                rows.append(ReviewedItem(
                    item_id=n, form=form,
                    concept=CONCEPTS[index % len(CONCEPTS)],
                    english_prompt="English " + n,
                    french_prompt=("Français " + n) if all_translated else "",
                    english_options=("one", "two", "three", "four"),
                    french_options=("un", "deux", "trois", "quatre"),
                    independently_reviewed_en=True, independently_reviewed_fr=True,
                    correct_option_index=0,
                ))
    return rows


def test_three_arm_no_repeat_bank_requires_261_distinct_bilingual_items():
    assert MIN_DISTINCT_CROSSOVER_ITEMS == 261
    bank = _items()
    report = validate_cross_language_bank(bank)
    assert report["distinct_item_count"] == 261
    assert not report["human_enrollment_authorized"]
    fr = visible_item(bank[0], "fr")
    assert fr["lang"] == "fr" and fr["prompt"].startswith("Français")
    en = visible_item(bank[0], "en")
    assert en["lang"] == "en" and en["prompt"].startswith("English")
    assert all("email" not in x.lower() for x in (en["prompt"], fr["prompt"]))


def test_missing_items_translation_review_and_duplicates_fail_closed():
    full = _items()
    with pytest.raises(ProposedStudyError, match="261"):
        validate_cross_language_bank(full[:95])
    with pytest.raises(ProposedStudyError, match="translation missing"):
        validate_cross_language_bank(_items(all_translated=False))
    from dataclasses import replace
    draft = full[:]
    draft[0] = replace(draft[0], independently_reviewed_fr=False)
    with pytest.raises(ProposedStudyError, match="unreviewed"):
        validate_cross_language_bank(draft)
    draft = full[:]
    draft[1] = replace(draft[1], item_id=draft[0].item_id)
    with pytest.raises(ProposedStudyError, match="duplicate"):
        validate_cross_language_bank(draft)
    with pytest.raises(ProposedStudyError, match="unreviewed"):
        visible_item(draft[0], "fr") if False else visible_item(
            replace(full[0], independently_reviewed_fr=False), "fr"
        )
    with pytest.raises(ProposedStudyError, match="unsupported"):
        visible_item(full[0], "de")


def test_bilingual_bank_rejects_missing_keys_duplicate_choices_and_missing_concepts():
    from dataclasses import replace
    complete = _items()
    changed = complete[:]
    changed[0] = replace(changed[0], correct_option_index=None)
    with pytest.raises(ProposedStudyError, match="answer key"):
        validate_cross_language_bank(changed)
    with pytest.raises(ProposedStudyError, match="answer key"):
        visible_item(changed[0], "fr")
    changed = complete[:]
    changed[0] = replace(changed[0], correct_option_index=4)
    with pytest.raises(ProposedStudyError, match="answer key"):
        validate_cross_language_bank(changed)
    changed = complete[:]
    changed[0] = replace(changed[0], english_options=("one", "ONE", "three", "four"))
    with pytest.raises(ProposedStudyError, match="duplicate answer"):
        validate_cross_language_bank(changed)
    changed = [replace(x, concept=CONCEPTS[0]) for x in complete]
    with pytest.raises(ProposedStudyError, match="eight concepts"):
        validate_cross_language_bank(changed)


def test_crossover_rejects_question_forms_out_of_order():
    state = CrossoverProgress(("A", "C", "B"))
    state.issue_next_token(T0, prior_period_complete=True)
    with pytest.raises(ProposedStudyError, match="pretest"):
        state.record_question("early_practice", form="practice")
    with pytest.raises(ProposedStudyError, match="practice"):
        state.record_question("early_posttest", form="posttest")
    for i in range(16):
        state.record_question(f"pre_{i}", form="pretest")
    state.record_question("practice_0", form="practice")
    with pytest.raises(ProposedStudyError, match="practice"):
        state.record_question("early_posttest", form="posttest")


def test_bilingual_welcome_does_not_promise_untrue_complete_anonymity():
    assert "Bienvenue" in EMAIL_TEMPLATES["fr"]["welcome"]
    assert "Welcome" in EMAIL_TEMPLATES["en"]["welcome"]
    assert "pseudonym" in EMAIL_TEMPLATES["en"]["privacy"]
    assert "pseudonym" in EMAIL_TEMPLATES["fr"]["privacy"]
    assert "not completely anonymous" in EMAIL_TEMPLATES["en"]["privacy"]


def test_counterbalanced_period_sequence_and_single_current_arm():
    assert len(all_sequences()) == 6
    assert len(set(all_sequences())) == 6
    with pytest.raises(ProposedStudyError):
        ordered_arms(("A", "A", "C"))
    state = CrossoverProgress(("B", "A", "C"))
    assert state.current_arm == "B"
    first = state.issue_next_token(T0, prior_period_complete=True)
    assert state.authenticate(first, T0 + timedelta(days=13))
    assert state.authenticate(first, T0 + timedelta(days=14))
    assert not state.authenticate(first, T0 + timedelta(days=14, seconds=1))
    with pytest.raises(ProposedStudyError, match="one active token"):
        state.issue_next_token(T0, prior_period_complete=True)
    with pytest.raises(ProposedStudyError, match="verified fictional contact"):
        state.renew_same_arm_token(
            T0 + timedelta(days=13), contact_identity_verified=True,
        )
    state.contact_reference = "SYN_CONTACT_test"
    with pytest.raises(ProposedStudyError):
        state.renew_same_arm_token(
            T0 + timedelta(days=13), contact_identity_verified=False,
        )
    second = state.renew_same_arm_token(
        T0 + timedelta(days=13), contact_identity_verified=True,
    )
    assert not state.authenticate(first, T0 + timedelta(days=13))
    assert state.authenticate(second, T0 + timedelta(days=27))

    for i in range(16):
        state.record_question(f"BASE_{i}", form="pretest")
    state.record_question("ITEM001")
    with pytest.raises(ProposedStudyError, match="cannot repeat"):
        state.record_question("ITEM001")
    with pytest.raises(ProposedStudyError, match="current arm"):
        state.record_question(
            "ITEM001", kind="DROP_2",
            immediately_previous_wrong_id="ITEM001",
        )
    with pytest.raises(ProposedStudyError, match="all independent"):
        state.complete_period(observed_unique_forms={"pretest": 16})


def test_sequential_unlock_disallows_next_arm_and_repeated_questions():
    state = CrossoverProgress(("A", "C", "B"))
    t1 = state.issue_next_token(T0, prior_period_complete=True)
    assert state.authenticate(t1, T0)
    for form, n in (("pretest", 16), ("practice", 55), ("posttest", 16)):
        for i in range(n):
            state.record_question(f"A_{form}_{i}", form=form)
    # An immediate Arm A DROP_2 retry is the explicit one-time exception
    # needed to reconcile the original "never repeat" and "re-present" rules.
    last = "A_practice_54"
    state.record_question(last, kind="DROP_2", immediately_previous_wrong_id=last)
    with pytest.raises(ProposedStudyError):
        state.record_question(last, kind="DROP_2", immediately_previous_wrong_id="other")
    state.complete_period(observed_unique_forms={
        "pretest": 16, "practice": 55, "posttest": 16,
    })
    assert state.current_arm == "C"
    assert not state.authenticate(t1, T0)
    with pytest.raises(ProposedStudyError, match="cannot enter next"):
        state.issue_next_token(T0, prior_period_complete=False)
    t2 = state.issue_next_token(T0 + timedelta(days=1), prior_period_complete=True)
    assert state.authenticate(t2, T0 + timedelta(days=1))
    with pytest.raises(ProposedStudyError, match="cannot repeat"):
        state.record_question(last)
    state.record_question("C_new_question")
    assert state.current_arm == "C"


def test_three_day_then_six_day_inactivity_reminders_and_fourteen_day_pause():
    pause = PauseEpisode(T0, T0, email_opt_in=True)
    assert pause.due(T0 + timedelta(days=2)) == ()
    assert pause.due(T0 + timedelta(days=3)) == (1,)
    pause.claim(1, T0 + timedelta(days=3))
    assert pause.due(T0 + timedelta(days=4)) == ()
    assert pause.due(T0 + timedelta(days=6)) == (2,)
    pause.claim(2, T0 + timedelta(days=6))
    assert pause.due(T0 + timedelta(days=7)) == ()
    assert pause.may_resume(T0 + timedelta(days=14))
    assert not pause.may_resume(T0 + timedelta(days=14, seconds=1))
    assert pause.due(T0 + timedelta(days=15)) == ()
    disabled = PauseEpisode(T0, T0, email_opt_in=False)
    assert disabled.due(T0 + timedelta(days=6)) == ()
    assert not PauseEpisode(T0, T0, withdrawn=True, email_opt_in=True).due(
        T0 + timedelta(days=6)
    )
    resumed = PauseEpisode(T0, T0 + timedelta(days=1), email_opt_in=True)
    assert resumed.due(T0 + timedelta(days=6)) == ()
    # A new drop starts a new clock, not a perpetual reminder queue.
    subsequent = PauseEpisode(T0 + timedelta(days=4),
                              T0 + timedelta(days=4), email_opt_in=True)
    assert subsequent.due(T0 + timedelta(days=7)) == (1,)
    with pytest.raises(ProposedStudyError, match="duplicate"):
        pause.claim(1, T0 + timedelta(days=7))
    late = PauseEpisode(T0, T0, email_opt_in=True)
    assert late.due(T0 + timedelta(days=8)) == (1,)
    late.claim(1, T0 + timedelta(days=8))
    assert late.due(T0 + timedelta(days=8)) == ()
    assert late.due(T0 + timedelta(days=10)) == ()
    assert late.due(T0 + timedelta(days=11)) == (2,)


def test_two_wrong_enforces_resource_before_fatigue_and_only_arm_a():
    rule = TwoWrongRecovery()
    assert not rule.observe_question(arm="B", stage="practice", correct=False)
    assert not rule.observe_question(arm="A", stage="pretest", correct=False)
    assert not rule.observe_question(arm="A", stage="practice", correct=False)
    assert rule.fatigue_allowed()
    assert rule.observe_question(arm="A", stage="practice", correct=False)
    assert not rule.fatigue_allowed()
    first = rule.choose_recovery()
    assert first in RECOVERY_ACTIONS
    with pytest.raises(ProposedStudyError, match="recovery must precede"):
        rule.observe_question(arm="A", stage="practice", correct=False)
    with pytest.raises(ProposedStudyError, match="does not match"):
        rule.acknowledge_recovery(next(a for a in RECOVERY_ACTIONS if a != first))
    rule.acknowledge_recovery(first)
    assert rule.fatigue_allowed()
    assert rule.wrong_streak == 0
    for _ in range(3):
        assert not rule.observe_question(arm="A", stage="practice", correct=False)
        assert rule.observe_question(arm="A", stage="practice", correct=False)
        selected = rule.choose_recovery()
        assert selected == RECOVERY_ACTIONS[rule.offered_in_visit % 4]
        rule.acknowledge_recovery(selected)
    assert rule.offered_in_visit == 4


def test_live_bkt_trace_distinguishes_model_estimate_and_scores():
    result = bkt_trace([
        {"stage": "pretest", "action": "QUESTION",
         "concept": CONCEPTS[0], "correct": False},
        {"stage": "practice", "action": "QUESTION",
         "concept": CONCEPTS[0], "correct": True},
        {"stage": "practice", "action": "CONCEPT_SUMMARY"},
        {"stage": "posttest", "action": "QUESTION",
         "concept": CONCEPTS[0], "correct": False},
    ])
    assert len(result["points"]) == 4
    initial, after_pretest, after_practice, after_posttest = [
        p["mastery"][CONCEPTS[0]] for p in result["points"]
    ]
    assert initial == 0.2
    assert after_pretest < initial
    assert after_practice > after_pretest
    assert after_posttest == after_practice
    assert not result["human_enrollment_authorized"]
    with pytest.raises(ProposedStudyError):
        bkt_trace([{"stage": "practice", "action": "QUESTION",
                    "concept": CONCEPTS[0], "correct": "yes"}])
