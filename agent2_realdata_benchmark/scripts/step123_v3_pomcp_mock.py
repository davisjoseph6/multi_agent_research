"""Full synthetic protocol engine rehearsal with an OPT-IN eight-concept planner.

Run from the repository directory with `python -m scripts.step123_v3_pomcp_mock`.
Never call the observations measured student learning or causal effects.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory
from uuid import uuid4

from src.prototype.study_v2 import CONCEPTS, allocate_arms, synthetic_bank
from src.prototype.study_v3_pomcp import EightConceptPOMCP
from src.prototype.study_v3_runtime import SyntheticPOMCPProtocolEngine


def run(n: int = 9, seed: int = 71, simulations: int = 80) -> dict:
    if n < 3 or n % 3:
        raise ValueError("synthetic participants must be a positive multiple of 3")
    rng = random.Random(seed)
    allocations = allocate_arms(n, rng)
    with TemporaryDirectory(prefix="ijcai_v3_synthetic_") as temp:
        engine = SyntheticPOMCPProtocolEngine(
            Path(temp)/"mock.sqlite3", synthetic_bank(),
            planner=EightConceptPOMCP(simulations=simulations))
        per_arm = Counter()
        totals = Counter()
        observed_actions = Counter()
        for index, arm in enumerate(allocations):
            pid = f"SYN_V3_{index:04}"
            latent = {c: .2 + rng.random()*.1 for c in CONCEPTS}
            engine.enroll(pid,arm)
            per_arm[arm] += 1
            for step in range(180):
                choice = engine.next_action(pid)
                typ = choice["action"]
                if typ == "COMPLETE":
                    break
                observed_actions[(arm,typ)] += 1
                if typ in ("QUESTION","DROP_2"):
                    item = engine.bank[choice["item_id"]]
                    correct = rng.random() < (latent[item.concept]*.9+(1-latent[item.concept])*.25)
                    selected = item.answer_id if correct else next(
                        x for x,_ in item.options if x != item.answer_id)
                    payload = {"item_id":item.item_id,"choice_id":selected}
                    if typ == "QUESTION":
                        totals[engine.snapshot(pid)["stage"]] += 1
                    if engine.snapshot(pid)["stage"] == "practice":
                        old = latent[item.concept]
                        latent[item.concept] = old + (1-old)*.03
                elif typ == "FATIGUE":
                    payload = {"values":[rng.randint(1,5) for _ in range(6)]}
                    totals["fatigue"] += 1
                else:
                    payload = {"acknowledged":True}
                    old = latent[choice["concept"]]
                    latent[choice["concept"]] = old + (1-old)*.02
                response = engine.act(pid, f"{pid}_req_{step:04}",payload)
                assert response["accepted"] and not response["replayed"]
            else:
                raise AssertionError("synthetic session did not terminate")
        audit = engine.audit()
        if audit["states"] != [(arm,"complete",n//3) for arm in ("A","B","C")]:
            raise AssertionError(f"unexpected final states: {audit['states']}")
        if (totals["pretest"],totals["practice"],totals["posttest"],totals["fatigue"]) != (
                16*n,55*n,16*n,3*n):
            raise AssertionError(f"wrong synthetic quotas: {totals}")
        return dict(synthetic=True, approved_study=False,
                    warning="SYNTHETIC DATA ONLY; NO CAUSAL LEARNING EVIDENCE",
                    participants=n, per_arm=dict(per_arm),
                    activity_counts=dict(totals),
                    resource_actions_by_arm={arm:sum(count for (a,kind),count in observed_actions.items()
                                                     if a==arm and kind not in ("QUESTION","FATIGUE"))
                                             for arm in ("A","B","C")},
                    audit=audit, planner_simulations=simulations, seed=seed)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--participants",type=int,default=9)
    parser.add_argument("--seed",type=int,default=71)
    parser.add_argument("--simulations",type=int,default=80)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    report=run(args.participants,args.seed,args.simulations)
    encoded=json.dumps(report,indent=2,sort_keys=True)+"\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        # Exclusive creation; never overwrite an old benchmark.
        with args.output.open("x",encoding="utf-8") as handle:
            handle.write(encoded)
    print(encoded)


if __name__=="__main__":
    main()
