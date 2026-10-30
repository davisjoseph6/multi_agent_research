"""Audit the V3 planner against latent-state drift.

Synthetic mathematical model only.
No claims about human learning or clinical outcomes.
"""

from fractions import Fraction
import json

from .study_v3_pomcp import (
    ACTIONS,
    CONCEPTS,
    PRACTICE,
    EightConceptPOMCP,
    GenerativeAssumptions,
    PlanningState,
)


def true_deficit(state: PlanningState) -> Fraction:
    """Fraction of synthetic concepts not mastered."""
    if not isinstance(state, PlanningState):
        raise TypeError("Expected PlanningState")

    return Fraction(
        sum(not mastered for mastered in state.mastered),
        len(CONCEPTS),
    )


def exact_conditional_drift(
    state: PlanningState,
    action: tuple[str, str],
    assumptions: GenerativeAssumptions | None = None,
) -> Fraction:
    """Expected one-step change of true deficit.

    The result conditions on the fully specified
    latent state and executed action.

    Fraction(str(rate)) represents the specified
    decimal model parameter exactly. It does not
    certify floating-point random sampling.
    """
    if not isinstance(state, PlanningState):
        raise TypeError("Expected PlanningState")

    if not isinstance(action, tuple) or len(action) != 2:
        raise ValueError("Expected (action, concept)")

    kind, concept = action

    if kind not in ACTIONS or concept not in CONCEPTS:
        raise ValueError("Invalid V3 action or concept")

    if kind != PRACTICE and state.resources_left == 0:
        raise ValueError(
            "Resource action is not executable"
        )

    model = assumptions or GenerativeAssumptions()
    index = CONCEPTS.index(concept)

    if state.mastered[index]:
        return Fraction(0)

    return (
        -Fraction(str(model.rate(kind)))
        / len(CONCEPTS)
    )


def default_planner_drift_witness() -> dict:
    """A specific finite-budget POMCP counterexample."""
    weak = "Nudge Theory"

    belief = {
        concept: (0.0 if concept == weak else 1.0)
        for concept in CONCEPTS
    }

    state = PlanningState(
        tuple(bool(belief[c]) for c in CONCEPTS),
        2,
    )

    planner = EightConceptPOMCP(
        simulations=240
    )

    result = planner.choose(
        belief,
        practice_concepts=CONCEPTS,
        resources_left=2,
        seed=71,
    )

    drift = exact_conditional_drift(
        state,
        (result.action, result.concept),
        planner.assumptions,
    )

    return {
        "synthetic_only": True,
        "simulations": result.simulations,
        "horizon": result.horizon,
        "seed": 71,
        "resources_left": 2,
        "one_unmastered_concept": weak,
        "selected_action": result.action,
        "selected_concept": result.concept,
        "selected_concept_already_mastered": (
            state.mastered[
                CONCEPTS.index(result.concept)
            ]
        ),
        "initial_true_deficit": str(
            true_deficit(state)
        ),
        "expected_one_step_deficit_change": str(
            drift
        ),
        "strict_positive_uniform_drift_disproved_for_this_configuration": (
            true_deficit(state) > 0
            and drift == 0
        ),
        "root_action_visits": sum(
            result.root_visits.values()
        ),
        "warning": (
            "Synthetic-model counterexample; "
            "not empirical learning evidence"
        ),
    }


if __name__ == "__main__":
    print(
        json.dumps(
            default_planner_drift_witness(),
            indent=2,
        )
    )
