"""Synthetic software stress benchmark. Scores must not be reported as RCT data."""
import argparse
import json
from statistics import mean, stdev
from src.prototype.study_v2 import ARMS, mock_study, OneConceptPOMCP


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--seeds",type=int,default=5)
    p.add_argument("--participants",type=int,default=9)
    args=p.parse_args()
    if not 1 <= args.seeds <= 500:
        p.error("seeds must be 1..500")
    per_arm={arm:[] for arm in ARMS}
    for seed in range(args.seeds):
        result=mock_study(args.participants,seed=seed+100)
        for arm in ARMS:
            group=[sum(x["posttest"]) for x in result["participants"] if x["arm"]==arm]
            per_arm[arm].append(mean(group))
    data={arm:{"synthetic_mean":round(mean(scores),4),
               "between_seed_sd":round(stdev(scores),4) if len(scores)>1 else None}
          for arm,scores in per_arm.items()}
    # The POMCP candidate remains a one-concept simulated proof of concept.
    data["pomcp_one_concept_candidate"]={
        "low_mastery_action":OneConceptPOMCP().choose(.2),
        "high_mastery_action":OneConceptPOMCP().choose(.8)}
    print(json.dumps({"synthetic":True,"not_real_RCT_evidence":True,
                      "seeds":args.seeds,"per_arm":data},indent=2))


if __name__=="__main__":
    main()
