"""V6 observation-change candidate on existing nonstationary DEVELOPMENT split.

Does not provide or expose a held-out option. Comparison uses the existing
benchmark's exogenous event streams, session limits and action costs.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean

from src.prototype.study_v3_pomcp import CONCEPTS, PRACTICE, GenerativeAssumptions
from src.prototype.step95_v6_decline_candidate import ObservationChangeController, POLICY_ID
from scripts import step95_nonstationary_heldout as base

COMPARATORS = ("fixed", "greedy", "heuristic_recovery", "v3", "v5")


def v6_episode(scenario_name: str, seed: int, *, lengths=base.SESSION_LENGTHS):
    conditions = base.scenario(scenario_name)
    a = GenerativeAssumptions()
    ctrl = ObservationChangeController(a)
    latent = {c: base.uniform(seed, -1, c, "initial") < .25 for c in CONCEPTS}
    belief = {c: .25 for c in CONCEPTS}
    step, count, cost, forget_events, observed = 0, 0, 0.0, 0, 0
    signal_actions = 0
    true_unmastered_at_signal = 0
    for n in lengths:
        budget = 2
        for _ in range(n):
            decision = ctrl.choose(belief, budget)
            action, concept = decision.action, decision.concept
            if action != PRACTICE:
                budget -= 1
                count += 1
            cost += a.cost(action)
            if decision.signal:
                signal_actions += 1
                if not latent[concept]:
                    true_unmastered_at_signal += 1
            if action in (PRACTICE, "DROP_2"):
                p = (1 - conditions.slip) if latent[concept] else conditions.guess
                correct = base.uniform(seed, step, concept, "observation") < p
                ctrl.observe(concept, correct)
                belief[concept] = base.update_belief(
                    belief[concept], correct, a.slip, a.guess
                )
                observed += 1
            for c in CONCEPTS:
                if latent[c] and base.uniform(seed, step, c, "forget") < conditions.forget:
                    latent[c] = False
                    forget_events += 1
            if not latent[concept] and base.uniform(seed, step, concept, "learning", action) < min(1., a.rate(action) * conditions.scale):
                latent[concept] = True
            belief[concept] += (1 - belief[concept]) * a.rate(action)
            step += 1
    mastery = sum(latent.values()) / len(CONCEPTS)
    return {
        "policy": POLICY_ID, "seed": seed, "scenario": scenario_name,
        "steps": step, "final_true_mastery_fraction": mastery,
        "nominal_net_mastery_fraction": round(mastery - cost, 12),
        "resource_actions": count, "latent_forgetting_events": forget_events,
        "observed_question_responses": observed,
        "signal_onsets": ctrl.signal_onsets,
        "signal_triggered_resources": signal_actions,
        "unmastered_at_signal_resource": true_unmastered_at_signal,
        "synthetic_only": True,
    }


def compare(scenario_name: str, n: int = 5, simulations: int = 12, *, lengths=base.SESSION_LENGTHS):
    if scenario_name not in base.SCENARIOS or type(n) is not int or not 1 <= n <= 1000:
        raise ValueError("invalid development configuration")
    if type(simulations) is not int or not 1 <= simulations <= 100000:
        raise ValueError("invalid planner budget")
    seeds = range(base.DEV_START, base.DEV_START + n)  # no held-out access
    cases = {p: [] for p in (*COMPARATORS, POLICY_ID)}
    for seed in seeds:
        for p in COMPARATORS:
            cases[p].append(base.run_episode(
                p, base.scenario(scenario_name), seed,
                planner_simulations=simulations, session_lengths=lengths,
            ))
        cases[POLICY_ID].append(v6_episode(scenario_name, seed, lengths=lengths))
    summaries = {
        policy: {
            "mean_raw_true_mastery": mean(r["final_true_mastery_fraction"] for r in rows),
            "mean_nominal_net_mastery": mean(r["nominal_net_mastery_fraction"] for r in rows),
            "mean_resources": mean(r["resource_actions"] for r in rows),
        }
        for policy, rows in cases.items()
    }
    paired = {
        f"v6_minus_{policy}": {
            "mean": mean(
                cases[POLICY_ID][i]["nominal_net_mastery_fraction"]
                - cases[policy][i]["nominal_net_mastery_fraction"]
                for i in range(n)
            ),
            "paired_values": [
                round(cases[POLICY_ID][i]["nominal_net_mastery_fraction"]
                      - cases[policy][i]["nominal_net_mastery_fraction"], 12)
                for i in range(n)
            ],
        }
        for policy in COMPARATORS
    }
    filename = Path(__file__).resolve().parents[1] / "src/prototype/step95_v6_decline_candidate.py"
    manifest = {"scenario": scenario_name, "participants": n,
                "planner_simulations": simulations, "split": "development",
                "seed_start": base.DEV_START, "seed_end": base.DEV_START + n - 1,
                "policy": POLICY_ID, "policy_sha256": sha256(filename.read_bytes()).hexdigest(),
                "session_lengths": list(lengths)}
    return {
        "manifest": manifest,
        "manifest_sha256": sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
        "synthetic_only": True, "human_evidence": False,
        "exploratory_only": True,
        "policies": summaries, "paired_contrasts": paired,
        "v6_detection_diagnostics": {
            "mean_onsets": mean(r["signal_onsets"] for r in cases[POLICY_ID]),
            "mean_resource_triggers": mean(r["signal_triggered_resources"] for r in cases[POLICY_ID]),
            "mean_unmastered_at_trigger": mean(r["unmastered_at_signal_resource"] for r in cases[POLICY_ID]),
            "note": "Latent mastery is used only here, after actions, not by the controller. Signal is not proof of forgetting.",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=tuple(base.SCENARIOS), default="slow_forgetting")
    parser.add_argument("--participants", type=int, default=5)
    parser.add_argument("--simulations", type=int, default=12)
    args = parser.parse_args()
    print(json.dumps(compare(args.scenario, args.participants, args.simulations), indent=2))


if __name__ == "__main__":
    main()
