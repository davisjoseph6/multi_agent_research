"""Read-only, fail-closed scientific evidence packet for the Nov 2 decision.

Consumes the *existing* aggregate-only outputs from preflight, rehearsal,
and five-scenario V6 development analysis. Does not access participants,
change policies, open sealed evaluations, or grant trial authorization.

Run from agent2_realdata_benchmark:
python -m scripts.ijcai2027_nov02_readonly_gate \
  --preflight /tmp/ijcai2027_preflight_01.json \
  --smoke /tmp/ijcai2027_smoke_01.json \
  --v6 /tmp/ijcai2027_v6_dev_01.json \
  --out /tmp/ijcai2027_nov02_gate_01.json
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path

EXPECTED_SCENARIOS = frozenset({
    "stationary_nominal", "slow_forgetting", "rapid_forgetting",
    "noisy_slow_forgetting", "weak_learning",
})


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def read_object(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    require(type(obj) is dict, f"Expected JSON object: {path}")
    return obj


def build_packet(preflight: dict, smoke: dict, v6: dict, witness: dict) -> dict:
    """Validate source-generated reports; never treat software tests as efficacy."""
    require(preflight.get("mechanical_gate_passed") is False,
            "Expected existing unreleased candidate; inspect changed status manually")
    blockers = preflight.get("blockers")
    require(isinstance(blockers, list) and len(blockers) > 0
            and all(isinstance(x, str) and x for x in blockers),
            "Missing live-enrollment release blockers")
    candidate = preflight.get("candidate_sha256")
    require(isinstance(candidate, str) and len(candidate) == 64,
            "Invalid candidate fingerprint")

    require(smoke.get("software_rehearsal_passed") is True
            and smoke.get("human_enrollment_authorized") is False,
            "Invalid software-only rehearsal status")
    audit = smoke.get("audit", {})
    require(type(audit) is dict and audit.get("candidate_sha256") == candidate,
            "The two reports describe different candidate software")
    require(audit.get("mode") == "rehearsal",
            "Only fictional participant rehearsal is permitted")
    require(isinstance(smoke.get("fictional_completed"), int)
            and smoke["fictional_completed"] >= 1,
            "Missing fictional completions")
    require(isinstance(smoke.get("arm_counts"), dict)
            and set(smoke["arm_counts"]) == {"A", "B", "C"},
            "Missing three-arm allocation summary")
    require(sum(smoke["arm_counts"].values()) == smoke["fictional_completed"],
            "Incorrect fictional allocation count")

    require(v6.get("human_participants") is False
            and v6.get("no_heldout_access") is True,
            "V6 report lacks development-only research boundary")
    require(set(v6.get("scenarios", {})) == EXPECTED_SCENARIOS,
            "Missing or changed original V6 scenario family")
    decision = v6.get("decision", {})
    require(type(decision) is dict
            and decision.get("total_development_scenarios") == 5
            and decision.get("screening_only_no_confirmatory_claim") is True
            and decision.get("real_student_intervention_effect_established") is False
            and decision.get("independent_algorithmic_novelty_established") is False,
            "Invalid V6 screen evidence boundary")

    contrasts = {}
    for name in sorted(EXPECTED_SCENARIOS):
        record = v6["scenarios"][name]
        contrast = record.get("paired_v6_minus", {}).get("no_recovery", {})
        mean = contrast.get("mean")
        interval = contrast.get("descriptive_interval")
        require(type(mean) in (int, float) and math.isfinite(mean),
                f"Invalid development contrast: {name}")
        require(isinstance(interval, list) and len(interval) == 2
                and all(type(x) in (int, float) and math.isfinite(x)
                        for x in interval) and interval[0] <= interval[1],
                f"Invalid descriptive interval: {name}")
        contrasts[name] = {"mean_v6_minus_no_recovery": mean,
                           "descriptive_interval": interval}
    require(sum(r["mean_v6_minus_no_recovery"] > 0 for r in contrasts.values())
            == decision.get("development_scenarios_with_positive_mean_recovery_contrast"),
            "V6 summary disagrees with individual scenario means")
    require((all(r["mean_v6_minus_no_recovery"] > 0 for r in contrasts.values())
             and all(r["descriptive_interval"][0] > 0 for r in contrasts.values()))
            == decision.get("conservative_predeclared_screening_pass"),
            "V6 decision disagrees with the displayed screening criterion")

    require(witness.get("synthetic_only") is True
            and witness.get("strict_positive_uniform_drift_disproved_for_this_configuration") is True
            and witness.get("expected_one_step_deficit_change") == "0",
            "V3 zero-drift counterexample must remain reproducible")
    return {
        "purpose": "IJCAI 2027 November 2 scientific GO/NO-GO packet",
        "claim_scope": "software rehearsal and synthetic development only; NO human efficacy or publication novelty established",
        "candidate_sha256": candidate,
        "software_rehearsal": {
            "passed": True,
            "fictional_completed": smoke["fictional_completed"],
            "arm_counts": smoke["arm_counts"],
            "restart_and_backup_restore_passed": smoke.get("restart_and_backup_restore_passed"),
        },
        "release": {"human_enrollment_authorized": False, "blockers": blockers},
        "v6": {"scenario_contrasts": contrasts,
               "broad_recovery_claim_screen": ("DEVELOPMENT_ONLY_PASS" if
                    decision["conservative_predeclared_screening_pass"] else "NO_GO"),
               "not_a_confirmatory_statistical_test": True},
        "v3": {"counterexample": witness,
               "universal_statewise_negative_drift_claim": "NOT_SUPPORTED"},
        "research_status": {
            "novel_ai_contribution": "NOT_ESTABLISHED",
            "causal_student_recovery_effect": "NOT_ESTABLISHED",
            "approved_human_rct": "NO_GO",
            "independent_mathematical_review": "REQUIRED",
        },
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--preflight", type=Path, required=True)
    p.add_argument("--smoke", type=Path, required=True)
    p.add_argument("--v6", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.out.exists():
        raise FileExistsError("Existing evidence packet will not be overwritten")
    from src.prototype.step94_v3_drift_bridge import default_planner_drift_witness
    witness = default_planner_drift_witness()
    packet = build_packet(read_object(args.preflight), read_object(args.smoke),
                          read_object(args.v6), witness)
    packet["input_sha256"] = {key: digest_file(getattr(args, key))
                              for key in ("preflight", "smoke", "v6")}
    args.out.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Scientific packet written:", args.out)
    print("V6 general recovery screening:", packet["v6"]["broad_recovery_claim_screen"])
    print("Human enrollment:", "NO_GO")
    print("V3 universal drift claim:", "NOT_SUPPORTED")


if __name__ == "__main__":
    main()
