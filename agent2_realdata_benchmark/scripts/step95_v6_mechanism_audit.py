"""Independent DEVELOPMENT-only V6 mechanism and no-recovery ablation audit.

Uses the same five prespecified hypothetical environments and common exogenous
randomness as the existing Step 95 development benchmark. A separate simulator
is intentionally used as a cross-check: the normal V6 arm MUST match its
existing implementation on all tested seeds. No heldout option is exposed.
"""
from __future__ import annotations

import argparse
import json
import math
from statistics import mean

from scripts import step95_nonstationary_heldout as base
from scripts.step95_v6_development import v6_episode
from src.prototype.step95_v6_decline_candidate import ObservationChangeController
from src.prototype.study_v3_pomcp import CONCEPTS, PRACTICE, GenerativeAssumptions

DEFAULT_RISK_CREDIT = 0.012
DEFAULT_COVERAGE_WEIGHT = 0.003


def audited_episode(scenario_name: str, seed: int, *, allow_recovery: bool = True,
                    risk_credit: float = DEFAULT_RISK_CREDIT,
                    coverage_weight: float = DEFAULT_COVERAGE_WEIGHT,
                    lengths: tuple[int, ...] = base.SESSION_LENGTHS) -> dict:
    """Simulate with hidden-truth telemetry; controller observes *only* answers/beliefs.

    `forgotten_and_unmastered_at_trigger` is an oracle diagnostic, NOT available
    to the decision policy. Never call it true-positive rate for 'forgetting'
    without specifying the operational target and its observation window.
    """
    if scenario_name not in base.SCENARIOS or type(seed) is not int or not (base.DEV_START <= seed < base.HELDOUT_START):
        raise ValueError("Only a prespecified development scenario/seed is permitted")
    if type(allow_recovery) is not bool or not lengths or any(type(x) is not int or x < 1 for x in lengths):
        raise ValueError("Invalid experiment configuration")
    if not all(math.isfinite(w) and w >= 0 for w in (risk_credit, coverage_weight)):
        raise ValueError("Weights must be finite and nonnegative")
    conditions = base.scenario(scenario_name)
    a = GenerativeAssumptions()
    controller = ObservationChangeController(a, risk_credit=risk_credit,
                                              coverage_weight=coverage_weight)
    latent = {c: base.uniform(seed, -1, c, "initial") < 0.25 for c in CONCEPTS}
    belief = {c: 0.25 for c in CONCEPTS}
    forgotten_since_learning = {c: False for c in CONCEPTS}
    steps, resources_used, cost, forget_events, observations = 0, 0, 0.0, 0, 0
    resource_signal, unmastered_resource, actual_forget_resource = 0, 0, 0
    false_mastered_resource, unmastered_without_forget_resource = 0, 0
    for session_len in lengths:
        resources_left = 2
        for _ in range(session_len):
            # The no-recovery ablation differs ONLY in access to recovery.
            # It uses the same observation-driven practice-selection controller.
            decision = controller.choose(belief, resources_left if allow_recovery else 0)
            action, target = decision.action, decision.concept
            if action != PRACTICE:
                if not allow_recovery or resources_left < 1:
                    raise AssertionError("Invalid resource use in no-recovery arm")
                resources_left -= 1
                resources_used += 1
            cost += a.cost(action)
            if decision.signal:
                resource_signal += 1
                if not latent[target]:
                    unmastered_resource += 1
                else:
                    false_mastered_resource += 1
                if not latent[target] and forgotten_since_learning[target]:
                    actual_forget_resource += 1
                if not latent[target] and not forgotten_since_learning[target]:
                    unmastered_without_forget_resource += 1
            if action in (PRACTICE, "DROP_2"):
                p = (1 - conditions.slip) if latent[target] else conditions.guess
                correct = base.uniform(seed, steps, target, "observation") < p
                controller.observe(target, correct)
                belief[target] = base.update_belief(belief[target], correct, a.slip, a.guess)
                observations += 1
            for c in CONCEPTS:
                if latent[c] and base.uniform(seed, steps, c, "forget") < conditions.forget:
                    latent[c] = False
                    forgotten_since_learning[c] = True
                    forget_events += 1
            if not latent[target] and base.uniform(seed, steps, target, "learning", action) < min(1., a.rate(action) * conditions.scale):
                latent[target] = True
                forgotten_since_learning[target] = False
            belief[target] += (1 - belief[target]) * a.rate(action)
            steps += 1
    mastered = sum(latent.values())
    return {
        "steps": steps,
        "final_true_mastery_fraction": mastered / len(CONCEPTS),
        "nominal_net_mastery_fraction": round(mastered / len(CONCEPTS) - cost, 12),
        "resource_actions": resources_used,
        "latent_forgetting_events": forget_events,
        "observed_question_responses": observations,
        "signal_onsets": controller.signal_onsets,
        "signal_triggered_resources": resource_signal,
        "unmastered_at_signal_resource": unmastered_resource,
        "mastered_at_signal_resource": false_mastered_resource,
        "forgotten_and_unmastered_at_trigger": actual_forget_resource,
        "unmastered_without_recorded_forgetting_at_trigger": unmastered_without_forget_resource,
        "synthetic_only": True,
    }


def verify_parity(name: str, seed: int, recorded: dict, lengths=base.SESSION_LENGTHS) -> None:
    """Fail closed if the independent simulation diverges from existing V6."""
    old = v6_episode(name, seed, lengths=lengths)
    fields = (
        "steps", "final_true_mastery_fraction", "nominal_net_mastery_fraction",
        "resource_actions", "latent_forgetting_events", "observed_question_responses",
        "signal_onsets", "signal_triggered_resources", "unmastered_at_signal_resource",
    )
    for field in fields:
        if recorded[field] != old[field]:
            raise AssertionError(f"Independent V6 parity failure in {field}: {recorded[field]} != {old[field]}")


def audit(name: str, participants: int = 30, lengths=base.SESSION_LENGTHS) -> dict:
    if name not in base.SCENARIOS or type(participants) is not int or not (1 <= participants <= 1000):
        raise ValueError("Only development scenarios and 1..1000 seeds are supported")
    rows = {k: [] for k in ("v6", "no_recovery", "no_risk_credit", "no_coverage_weight", "fixed", "greedy")}
    for seed in range(base.DEV_START, base.DEV_START + participants):
        original = audited_episode(name, seed, lengths=lengths)
        verify_parity(name, seed, original, lengths)
        rows["v6"].append(original)
        rows["no_recovery"].append(audited_episode(name, seed, allow_recovery=False, lengths=lengths))
        rows["no_risk_credit"].append(audited_episode(name, seed, risk_credit=0, lengths=lengths))
        rows["no_coverage_weight"].append(audited_episode(name, seed, coverage_weight=0, lengths=lengths))
        for comparator in ("fixed", "greedy"):
            rows[comparator].append(base.run_episode(
                comparator, base.scenario(name), seed, session_lengths=lengths,
            ))
    def avg(label: str, field: str) -> float:
        return mean(x[field] for x in rows[label])
    def contrast(comparator: str) -> dict:
        diffs = [a["nominal_net_mastery_fraction"] - b["nominal_net_mastery_fraction"]
                 for a, b in zip(rows["v6"], rows[comparator])]
        return {"mean": mean(diffs), "descriptive_bootstrap_95pct_interval": list(base.bootstrap_interval(
                    diffs, seed=84531, iterations=1000)), "n_paired_seeds": participants,
                "wins": sum(x > 0 for x in diffs), "ties": sum(x == 0 for x in diffs),
                "losses": sum(x < 0 for x in diffs)}
    triggered = sum(r["signal_triggered_resources"] for r in rows["v6"])
    forgotten_triggered = sum(r["forgotten_and_unmastered_at_trigger"] for r in rows["v6"])
    return {
        "manifest": {"scenario": name, "split": "development", "seed_start": base.DEV_START,
                     "seed_end": base.DEV_START + participants - 1, "participants": participants,
                     "session_lengths": list(lengths), "risk_credit": DEFAULT_RISK_CREDIT,
                     "coverage_weight": DEFAULT_COVERAGE_WEIGHT,
                     "v6_replayed_and_parity_verified": True,
                     "no_heldout_seeds_accessed": True},
        "synthetic_only": True, "human_evidence": False,
        "descriptive_means": {label: {
            "true_mastery": avg(label, "final_true_mastery_fraction"),
            "nominal_net_mastery": avg(label, "nominal_net_mastery_fraction"),
            "resource_actions": avg(label, "resource_actions"),
        } for label in rows},
        "paired_v6_minus": {comp: contrast(comp) for comp in rows if comp != "v6"},
        "v6_trigger_diagnostics": {
            "total_triggered_recovery_actions": triggered,
            "total_unmastered_at_trigger": sum(r["unmastered_at_signal_resource"] for r in rows["v6"]),
            "total_mastered_at_trigger": sum(r["mastered_at_signal_resource"] for r in rows["v6"]),
            "total_lost_after_recorded_forgetting_at_trigger": forgotten_triggered,
            "total_unmastered_without_recorded_forgetting": sum(r["unmastered_without_recorded_forgetting_at_trigger"] for r in rows["v6"]),
            "forgetting_association_fraction_of_triggers": (forgotten_triggered / triggered if triggered else None),
            "note": "Ground-truth labels are post-hoc simulation diagnostics; none enter the controller. The fraction is not recall or human diagnostic accuracy.",
        },
        "research_status": "EXPLORATORY development only; no learned efficacy, novelty or human validity established",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scenario", choices=("all", *base.SCENARIOS), default="all")
    p.add_argument("--participants", type=int, default=30)
    args = p.parse_args()
    scenarios = base.SCENARIOS if args.scenario == "all" else (args.scenario,)
    results = {name: audit(name, args.participants) for name in scenarios}
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
