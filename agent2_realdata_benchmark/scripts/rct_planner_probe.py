"""Fictional, read-only shadow probe: does frozen V3 POMCP actually choose hints?

This does NOT connect to participant records and does NOT change the planner.
A fixed grid of synthetic BKT beliefs and deterministic seeds is diagnostic,
not an unbiased estimate of RCT treatment frequencies or educational benefits.

From agent2_realdata_benchmark:
python -m scripts.rct_planner_probe --seeds 20 --simulations 240
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from src.prototype.study_v2 import CONCEPTS, RECOVERY_ACTIONS
from src.prototype.study_v3_pomcp import EightConceptPOMCP, PRACTICE


PROFILES = {
    "uniform_low_05": {c: 0.05 for c in CONCEPTS},
    "uniform_prior_20": {c: 0.20 for c in CONCEPTS},
    "mixed_10_to_80": {c: 0.10 * (i + 1) for i, c in enumerate(CONCEPTS)},
    "uniform_mid_50": {c: 0.50 for c in CONCEPTS},
    "uniform_high_85": {c: 0.85 for c in CONCEPTS},
}


def probe(*, seeds=20, simulations=240):
    if type(seeds) is not int or not 1 <= seeds <= 100:
        raise ValueError("seeds must be an integer from 1 to 100")
    if type(simulations) is not int or not 41 <= simulations <= 2000:
        raise ValueError("simulations must be an integer from 41 to 2000")
    planner = EightConceptPOMCP(simulations=simulations)
    report = {}
    for profile, belief in PROFILES.items():
        actions = Counter()
        socratic_root_exploration = 0
        available_socratic = 0
        for i in range(seeds):
            result = planner.choose(
                belief, practice_concepts=CONCEPTS,
                resource_actions=RECOVERY_ACTIONS, resources_left=2,
                seed=71000 + i,
            )
            actions[result.action] += 1
            hints = [v for k, v in result.root_visits.items()
                     if k.startswith("SOCRATIC_HINT::")]
            if len(hints) != len(CONCEPTS):
                raise AssertionError("unexpected Socratic root actions")
            available_socratic += 1
            if sum(hints) > 0:
                socratic_root_exploration += 1
        report[profile] = {
            "choices": {a: actions[a] for a in (PRACTICE,) + RECOVERY_ACTIONS},
            "socratic_choices": actions["SOCRATIC_HINT"],
            "socratic_explored_at_root": socratic_root_exploration,
            "socratic_offered_in_action_set": available_socratic,
        }
        if sum(actions.values()) != seeds:
            raise AssertionError("not all planning decisions accounted for")
    return {
        "evidence": "FROZEN_V3_SYNTHETIC_BELIEF_SHADOW_PROBE",
        "model_changes": False,
        "participant_database_accessed": False,
        "simulations_per_decision": simulations,
        "seeds_per_profile": seeds,
        "profiles": report,
        "interpretation": (
            "Socratic available, explored and selected are distinct. "
            "A zero count is not a proof of unreachable action. "
            "Counts are sensitive to this fixed belief grid, random seeds, "
            "synthetic assumed gains and costs. The live RCT policy is unchanged."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--simulations", type=int, default=240)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = probe(seeds=args.seeds, simulations=args.simulations)
    if args.out is not None:
        if args.out.exists():
            raise FileExistsError("Refusing to overwrite existing evidence")
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
