"""Deterministic, unapproved educational error-remediation scaffolding.

This module is used ONLY in an opt-in synthetic demonstration variant.
It anchors the four recovery types to the latest actually incorrect PRACTICE
item, never an assessment response, and never generates uncontrolled LLM text.
The original source resource remains the versioned concept-level draft.
These prompts are NOT independently reviewed instructional interventions.
"""
from __future__ import annotations

from .pilot_session_flow_draft import PilotSequenceError
from .study_v2 import RECOVERY_ACTIONS, Item


def verify_error_anchor(
    bank: dict[str, Item], anchor: object, concept: str,
    *, session: int,
) -> tuple[Item, str, str]:
    """Validate the persisted, server-derived incorrect practice response."""
    if (type(anchor) is not dict or set(anchor) !=
            {"item_id", "choice_id", "session"}):
        raise PilotSequenceError("no recorded incorrect practice question")
    if type(anchor["session"]) is not int or anchor["session"] != session:
        raise PilotSequenceError("recorded incorrect answer is not from this visit")
    item_id, choice = anchor["item_id"], anchor["choice_id"]
    if type(item_id) is not str or type(choice) is not str:
        raise PilotSequenceError("invalid recorded practice answer")
    item = bank.get(item_id)
    if item is None or item.form != "practice" or item.concept != concept:
        raise PilotSequenceError("recorded incorrect question/concept mismatch")
    option_map = dict(item.options)
    if choice not in option_map or choice == item.answer_id:
        raise PilotSequenceError("target must be a wrong choice from the actual item")
    return item, choice, option_map[choice]


def two_choice_retry(item: Item, choice: str) -> dict:
    """Re-present the SAME practice stem with correct+NEW wrong distractor.

    The learner has already been told the previous choice was incorrect.
    Keeping that known-wrong choice next to the correct answer would make
    the retry solvable by elimination alone. Select a *different* distractor
    from the frozen authored item instead, in original option order.
    Do not identify the correct option in the public payload.
    """
    if choice == item.answer_id or choice not in dict(item.options):
        raise PilotSequenceError("cannot construct a two-option retry")
    different_distractors = [
        option_id for option_id, _ in item.options
        if option_id not in (item.answer_id, choice)
    ]
    if not different_distractors:
        raise PilotSequenceError("two-choice retry requires a different distractor")
    distractor = different_distractors[0]
    question = item.public()
    question["options"] = [
        (option_id, label) for option_id, label in item.options
        if option_id in (item.answer_id, distractor)
    ]
    if len(question["options"]) != 2:
        raise PilotSequenceError("recovery must present exactly two distinct options")
    question["fictional_question_anchored_retry"] = True
    return question


def contextual_resource(
    base: dict, item: Item, choice: str, wrong_text: str,
    *, action: str,
) -> dict:
    """Versioned prompt framing, not a newly expert-authored answer explanation."""
    if action not in RECOVERY_ACTIONS:
        raise PilotSequenceError("unknown recovery resource kind")
    context = {
        "target_item_id": item.item_id,
        "target_question": item.prompt,
        "prior_selected_option": {"id": choice, "text": wrong_text},
        "target_concept": item.concept,
        "source": "MOST_RECENT_INCORRECT_PRACTICE_THIS_VISIT",
        "content_independently_reviewed": False,
    }
    prompts = {
        "SOCRATIC_HINT": (
            "Think again about the scenario you just answered incorrectly. "
            "What assumption led you to your earlier choice? "
            "Which part of the stated concept could you use to test that "
            "assumption? Try reasoning before viewing another worked solution."
        ),
        "CONCEPT_SUMMARY": (
            "Review the concept summary, then return to the specific scenario "
            "above. Identify the relevant evidence, quantity or reference point "
            "and explain how the concept applies, without being given the answer."
        ),
        "WORKED_EXAMPLE": (
            "Study the separate authored worked example below. Compare its "
            "reasoning steps with the earlier question, noting what is similar "
            "and what differs. Then attempt the original reasoning independently."
        ),
        "DROP_2": (
            "Retry the same question with only two choices: the correct "
            "answer and a different, still plausible distractor from the "
            "original authored options. Your already-known incorrect choice "
            "is omitted, so elimination alone does not reveal the answer."
        ),
    }
    return {
        **base,
        "question_anchor": context,
        "application_prompt": prompts[action],
        "question_anchored_demo_only": True,
    }
