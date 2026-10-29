"""Synthetic planning-model sensitivity audit, NOT participant outcomes."""
from __future__ import annotations
from dataclasses import replace
import json
from src.prototype.study_v2 import CONCEPTS
from src.prototype.study_v3_pomcp import EightConceptPOMCP, GenerativeAssumptions


def run(seed=71,simulations=120):
    default=GenerativeAssumptions()
    variations={
        "assumed_nominal":default,
        "assumed_recovery_ineffective":replace(default,learn_summary=0,learn_drop2=0,
                                                learn_worked=0,learn_socratic=0),
        "assumed_practice_ineffective":replace(default,learn_practice=0),
    }
    cases={"low":.1,"medium":.5,"high":.9}
    output=[]
    for scenario,model in variations.items():
        planner=EightConceptPOMCP(simulations=simulations,assumptions=model)
        for label,p in cases.items():
            result=planner.choose(dict.fromkeys(CONCEPTS,p),practice_concepts=CONCEPTS,
                                  resources_left=2,seed=seed)
            output.append(dict(scenario=scenario,belief_label=label,
                chosen_action=result.action,chosen_concept=result.concept,
                model_sha256=result.assumption_hash,simulations=simulations))
    return dict(synthetic=True,human_evidence=False,seed=seed,results=output,
        warning="These are planning ACTIONS under hypothetical models, not observed learning outcomes.")


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--seed",type=int,default=71)
    parser.add_argument("--simulations",type=int,default=120)
    args=parser.parse_args()
    print(json.dumps(run(args.seed,args.simulations),indent=2,sort_keys=True))


if __name__=="__main__":
    main()
