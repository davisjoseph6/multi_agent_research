"""Version-pinned, provisional instructional text for the LOCAL fictional preview.

NOT independently reviewed teaching content. Never use for real participants
until the supervisor approves the resources and protocol. This does not
implement the earlier Claude-API runtime generation requirement; no secret
or outbound request is available in the isolated synthetic preview.

Question-specific Socratic reflection precedes (and never replaces) the
bank-question re-attempt controlled by SupervisorTraceEngine. No answer keys.
"""
from __future__ import annotations

CONTENT_VERSION = "fictional_recovery_draft_v1"
REVIEW_STATUS = "DRAFT_REQUIRES_SUPERVISOR_REVIEW"

# A distinct L1 concept explanation and L2 worked example for each topic.
# Worked examples deliberately use illustrative situations; they do not
# reuse pretest/posttest items or expose the grading keys.
_CONTENT = {
    "C1": {
        "name": "Utility",
        "summary": (
            "Utility describes the satisfaction or benefit a person expects "
            "from a choice. It is subjective: two people can value the same "
            "thing differently.",
            "Marginal utility means the extra satisfaction from one additional "
            "unit. It can decrease as more of the same item is consumed.",
        ),
        "example": (
            "Imagine someone receives one free bottle of water after a long "
            "walk. It is extremely useful. A second bottle is still useful; "
            "a fifth bottle may add very little satisfaction.",
            "Step 1: compare the value of each additional bottle, not the "
            "total number owned. Step 2: notice that the next bottle adds "
            "less benefit than the first. Step 3: use that pattern to explain "
            "diminishing marginal utility.",
        ),
        "hints": (
            "Which part of the question is about satisfaction, rather than "
            "money spent or a physical quantity?",
            "Would the same extra unit necessarily be equally valuable to "
            "everyone, or after several units have already been consumed?",
        ),
    },
    "C2": {
        "name": "Loss Aversion",
        "summary": (
            "Loss aversion describes the tendency for a loss to feel more "
            "painful than an equally sized gain feels pleasurable. Whether "
            "an outcome counts as a gain or a loss depends on a reference point.",
            "A person may therefore reject a gamble with a slightly favorable "
            "average payoff, or try hard to avoid losing something already owned.",
        ),
        "example": (
            "Imagine someone is offered a 50–50 coin toss: they could gain "
            "30 credits or lose 20 credits. Its expected monetary payoff is "
            "(0.5 × 30) − (0.5 × 20) = +5 credits.",
            "Step 1: identify the current position as the reference point. "
            "Step 2: compare the feelings attached to the loss and gain, not "
            "only their arithmetic average. Step 3: explain why a loss-averse "
            "person might still refuse this positive-payoff gamble.",
        ),
        "hints": (
            "What reference point makes the outcome feel like a loss or a gain?",
            "If an equal-sized loss and gain were offered, would their "
            "psychological impact necessarily cancel out?",
        ),
    },
    "C3": {
        "name": "Anchoring",
        "summary": (
            "An anchor is an initial number or piece of information that "
            "influences a later estimate or judgment. People often adjust "
            "away from that starting point, but not enough.",
            "An anchor can affect estimates even when it is arbitrary or "
            "has little diagnostic value.",
        ),
        "example": (
            "Imagine two customers judging the price of the same used bicycle. "
            "One first sees an asking price of €300 and the other first sees "
            "€120, even though both inspect the same bicycle.",
            "Step 1: identify each initial listed price as a possible anchor. "
            "Step 2: compare how the later acceptable price might shift. "
            "Step 3: decide which independent facts about the bicycle should "
            "matter more than the first number seen.",
        ),
        "hints": (
            "Which information was encountered first, and could it have "
            "become a starting point for the later judgment?",
            "Is the person evaluating the evidence independently, or "
            "adjusting from an initial value that may be irrelevant?",
        ),
    },
    "C4": {
        "name": "Sunk Cost",
        "summary": (
            "A sunk cost is a past expense of money, time, or effort that "
            "cannot be recovered. The sunk cost fallacy occurs when someone "
            "lets that irrecoverable expense determine what to do next.",
            "A forward-looking decision compares future costs and benefits; "
            "a past payment does not change those future payoffs.",
        ),
        "example": (
            "Imagine a person paid €25 for a non-refundable event ticket, "
            "but on the event day they are unwell and expect no enjoyment.",
            "Step 1: the €25 cannot be recovered whether they attend or not. "
            "Step 2: identify the future costs and benefits of attending. "
            "Step 3: choose based on those future consequences, not on the "
            "desire to justify the ticket price.",
        ),
        "hints": (
            "Which costs in this situation have already been paid and "
            "cannot be changed by the next decision?",
            "If the past expense were forgotten, which future benefit or "
            "cost would actually determine the better option?",
        ),
    },
    "C5": {
        "name": "Framing",
        "summary": (
            "A framing effect occurs when equivalent outcomes produce "
            "different choices because they are described differently. "
            "Gain wording emphasizes what is preserved; loss wording "
            "emphasizes what is lost.",
            "To evaluate a framed choice, rewrite the alternatives in "
            "comparable terms and check whether their actual probabilities "
            "and consequences differ.",
        ),
        "example": (
            "Imagine two descriptions of the same treatment outcome: "
            "'90 people out of 100 survive' and '10 people out of 100 die'. "
            "They describe the same numerical result.",
            "Step 1: convert both statements into the same unit, such as "
            "survival percentage. Step 2: verify that the outcomes are "
            "equivalent. Step 3: notice how positive versus negative wording "
            "could still influence preference.",
        ),
        "hints": (
            "Could two differently worded options describe the same "
            "underlying outcome or probability?",
            "What happens if you rewrite every choice using exactly the "
            "same gain or loss description?",
        ),
    },
    "C6": {
        "name": "Heuristics",
        "summary": (
            "A heuristic is a mental shortcut that helps people make "
            "decisions quickly with limited time or information. It is "
            "sometimes useful but can also introduce systematic bias.",
            "Examples include using ease of recall (availability), "
            "resemblance to a stereotype (representativeness), and "
            "adjustment from a starting value (anchoring).",
        ),
        "example": (
            "Imagine a traveler sees three dramatic news stories about "
            "flight delays, then assumes that most flights are delayed.",
            "Step 1: the memorable stories are easy to recall. Step 2: "
            "ease of recall is not the same as the actual rate of delays. "
            "Step 3: compare the impression with representative statistics "
            "before estimating the risk.",
        ),
        "hints": (
            "Is the judgment based on systematic evidence, or on a quick "
            "rule of thumb that saves mental effort?",
            "Would a vivid example, a familiar stereotype, or an initial "
            "number be influencing the decision?",
        ),
    },
    "C7": {
        "name": "Prospect Theory",
        "summary": (
            "Prospect Theory describes choices under risk using gains and "
            "losses relative to a reference point, rather than only final "
            "wealth. It incorporates loss aversion and non-linear "
            "weighting of perceived probabilities.",
            "The same monetary outcome can therefore feel different "
            "depending on the person's starting point and how the options "
            "are presented.",
        ),
        "example": (
            "Imagine a person choosing between receiving €40 for sure "
            "and a 50% chance of receiving €90 with a 50% chance of €0.",
            "Step 1: compute the risky option's expected monetary gain: "
            "0.5 × €90 = €45. Step 2: identify the reference point and "
            "the certainty of the first option. Step 3: distinguish the "
            "numerical expected gain from how a person may subjectively "
            "value the risky prospect.",
        ),
        "hints": (
            "What is the decision-maker's reference point, and which "
            "outcomes are experienced as gains versus losses?",
            "Is the question asking for an arithmetic expected value, "
            "or for how people psychologically weight outcomes and risks?",
        ),
    },
    "C8": {
        "name": "Nudge Theory",
        "summary": (
            "A nudge changes how choices are presented so that one "
            "decision becomes easier or more salient, while alternatives "
            "remain available. The arrangement of choices is called "
            "choice architecture.",
            "A nudge should not depend on removing options or imposing "
            "a substantial punishment for choosing differently.",
        ),
        "example": (
            "Imagine a cafeteria places fruit at eye level while keeping "
            "desserts on the same shelves and at the same prices.",
            "Step 1: people can still buy either item. Step 2: the layout "
            "makes the fruit more visible and convenient. Step 3: contrast "
            "this arrangement with forbidding desserts or adding a large "
            "penalty, which would not preserve the same freedom of choice.",
        ),
        "hints": (
            "Is the decision environment designed to make an option "
            "more noticeable or easier to select?",
            "Are the other choices still genuinely available, or are "
            "people being forced by a prohibition or major penalty?",
        ),
    },
}


def recovery_resource(concept: str, action: str, *,
                      question_text: str | None = None,
                      language: str = "en") -> dict:
    """Return instructional *draft* material without grading information."""
    if concept not in _CONTENT:
        raise ValueError("unsupported concept")
    if action not in ("CONCEPT_SUMMARY", "WORKED_EXAMPLE", "SOCRATIC_HINT"):
        raise ValueError("no teaching content for this action")
    if language not in ("en", "fr"):
        raise ValueError("unsupported recovery language")
    if language == "fr":
        from .supervisor_fr_resources import FR_RESOURCES
        source = FR_RESOURCES[concept]
    else:
        source = _CONTENT[concept]
    result = {
        "content_id": f"{CONTENT_VERSION}_{concept}_{action}" + (
            "_fr" if language == "fr" else ""
        ),
        "language": language,
        "version": CONTENT_VERSION,
        "review_status": REVIEW_STATUS,
        "concept": concept,
        "concept_name": source["name"],
    }
    if action == "SOCRATIC_HINT":
        if not isinstance(question_text, str) or not question_text.strip():
            raise ValueError("original practice-question stem required")
        result.update({
            "title": ("Guidage socratique avant une nouvelle tentative"
                      if language == "fr"
                      else "Socratic guidance before re-attempt"),
            "intro": (
                "Expliquez votre raisonnement avec vos propres mots. La "
                "question à choix multiples originale apparaîtra après "
                "les deux questions de réflexion. Aucune indication "
                "de la bonne réponse n'est encore donnée."
                if language == "fr" else
                "Write your reasoning in your own words. The original "
                "multiple-choice question will appear only after both "
                "guiding questions. No correctness feedback is provided yet."
            ),
            "prompts": list(source["hints"]),
            "original_question": question_text,
        })
    else:
        result.update({
            "title": (
                ((f"Résumé du concept : {source['name']}"
                  if language == "fr" else
                  f"Concept summary: {source['name']}")
                 if action == "CONCEPT_SUMMARY" else
                 (f"Exemple expliqué : {source['name']}"
                  if language == "fr" else
                  f"Worked example: {source['name']}"))
            ),
            "paragraphs": list(source["summary"] if action == "CONCEPT_SUMMARY"
                               else source["example"]),
        })
    return result
