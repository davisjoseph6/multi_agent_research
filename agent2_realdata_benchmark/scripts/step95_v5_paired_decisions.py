"""Matched-input raw-V3 vs guarded-V5 *decision* benchmark (synthetic only).

No simulated test scores or human outcomes. Each planner sees exactly the same
belief, allowed actions, model, search budget and seed. Compares decisions only.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import math

from src.prototype.study_v3_pomcp import CONCEPTS, EightConceptPOMCP
from src.prototype.study_v5_guarded_planner import BeliefSupportGuardedPOMCP


def cases():
    out = [
        ("one_unmastered_nudge", {c: float(c != "Nudge Theory") for c in CONCEPTS}),
        ("all_mastered", dict.fromkeys(CONCEPTS, 1.0)),
        ("all_unmastered", dict.fromkeys(CONCEPTS, 0.0)),
        ("all_uncertain", dict.fromkeys(CONCEPTS, .5)),
        ("graduated", {c: (i + 1) / 9 for i, c in enumerate(CONCEPTS)}),
    ]
    out.extend(
        (f"one_unmastered_{i}", {c: float(j != i) for j, c in enumerate(CONCEPTS)})
        for i in range(len(CONCEPTS))
    )
    return out


def run(*, simulations=80, seeds=(71, 72), budgets=(0, 2)):
    if type(simulations) is not int or simulations < 1:
        raise ValueError("simulations must be positive integer")
    if not seeds or any(type(s) is not int for s in seeds):
        raise ValueError("seeds must be nonempty integer sequence")
    if not budgets or any(type(b) is not int or b < 0 or b > 10 for b in budgets):
        raise ValueError("budgets must be nonempty integer sequence 0..10")
    raw = EightConceptPOMCP(simulations=simulations)
    guarded = BeliefSupportGuardedPOMCP(simulations=simulations)
    summary = Counter()
    rows = []
    for label, belief in cases():
        for budget in budgets:
            for seed in seeds:
                old = raw.choose(
                    belief, practice_concepts=CONCEPTS,
                    resources_left=budget, seed=seed,
                )
                new = guarded.choose(
                    belief, practice_concepts=CONCEPTS,
                    resources_left=budget, seed=seed,
                )
                assert old == type(old)(
                    action=new.raw_action, concept=new.raw_concept,
                    root_visits=new.root_visits, root_values=new.root_values,
                    simulations=new.simulations, horizon=new.horizon,
                    assumption_hash=new.assumption_hash,
                    synthetic_only=True,
                ), "V3 raw planning provenance changed"
                def expected_gain(action, concept):
                    return (1.0-belief[concept])*raw.assumptions.rate(action)/len(CONCEPTS)
                old_gain = expected_gain(old.action, old.concept)
                new_gain = expected_gain(new.action, new.concept)
                if not math.isclose(new_gain, new.expected_mastery_gain, abs_tol=1e-12):
                    raise AssertionError("Incorrect reported guarded gain")
                if new.guard_applied:
                    assert old_gain == 0 and new_gain > 0
                else:
                    assert (old.action, old.concept) == (new.action, new.concept)
                assert new_gain >= old_gain - 1e-12
                summary["cases"] += 1
                summary["interventions"] += int(new.guard_applied)
                summary["raw_zero_gain"] += int(old_gain == 0)
                summary["guarded_zero_gain"] += int(new_gain == 0)
                rows.append({
                    "scenario":label,"budget":budget,"seed":seed,
                    "raw_action":old.action,"raw_concept":old.concept,
                    "guarded_action":new.action,"guarded_concept":new.concept,
                    "raw_expected_gain":round(old_gain,10),
                    "guarded_expected_gain":round(new_gain,10),
                    "guard_applied":new.guard_applied,
                })
    manifest = {
        "synthetic":True, "human_evidence":False,
        "comparison":"paired decision analysis, not an outcome or efficacy comparison",
        "policy_original":"V3 POMCP", "policy_candidate":guarded.policy_id,
        "model_sha256":raw.assumptions.fingerprint,
        "simulations":simulations,"seeds":list(seeds),"budgets":list(budgets),
        "summary":dict(sorted(summary.items())), "rows":rows,
    }
    manifest["manifest_sha256"] = sha256(json.dumps(
        manifest,sort_keys=True,separators=(",", ":")
    ).encode()).hexdigest()
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulations",type=int,default=80)
    parser.add_argument("--seeds",type=int,nargs="+",default=[71,72])
    parser.add_argument("--budgets",type=int,nargs="+",default=[0,2])
    parser.add_argument("--output")
    args = parser.parse_args()
    result = run(simulations=args.simulations,seeds=args.seeds,budgets=args.budgets)
    encoded = json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output:
        from pathlib import Path
        path = Path(args.output)
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("x",encoding="utf-8") as f:
            f.write(encoded)
    print(json.dumps({k:v for k,v in result.items() if k!="rows"},indent=2,sort_keys=True))


if __name__ == "__main__":
    main()
