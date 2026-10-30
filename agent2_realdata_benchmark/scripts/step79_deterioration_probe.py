"""Standalone diagnostic: run with python -m scripts.step79_deterioration_probe."""
import json
import random

from src.prototype.step79_deterioration import (
    AnchorWindow, NonstationaryAssumptions,
    nonstationary_transition, paired_response_change,
)
from src.prototype.study_v2 import BKT
from src.prototype.study_v3_pomcp import CONCEPTS, GenerativeAssumptions, PlanningState


def main():
    all_correct = AnchorWindow(0, "synthetic-anchor-v1", tuple((str(i), True) for i in range(8)))
    all_wrong = AnchorWindow(1, "synthetic-anchor-v1", tuple((str(i), False) for i in range(8)))
    change = paired_response_change(all_correct, all_wrong)
    start = PlanningState((True,) * len(CONCEPTS), 2)
    future = nonstationary_transition(
        start, ("QUESTION", CONCEPTS[0]), random.Random(5),
        learning=GenerativeAssumptions(learn_practice=0.0),
        nonstationarity=NonstationaryAssumptions(1.0),
    )
    print(json.dumps({
        "synthetic_only": True,
        "old_v3_true_mastery_is_monotonic": True,
        "belief_can_fall_after_wrong_observation": BKT().update(0.8, False) < 0.8,
        "paired_evidence_only": {
            "observed_drop": change.correct_to_incorrect,
            "one_sided_p": str(change.one_sided_exact_p),
            "signal": change.observed_decline_signal,
            "latent_forgetting_proven": change.latent_forgetting_proven,
        },
        "new_stress_test_lost_concepts": len(CONCEPTS) - sum(future.mastered),
        "warning": "No observed human deterioration or calibrated learning transitions",
    }, indent=2))


if __name__ == "__main__":
    main()
